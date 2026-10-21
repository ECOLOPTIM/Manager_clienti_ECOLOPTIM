"""Back up the local test DB and restore ONLY into a newly created test DB.

No source records, application configuration, existing databases or roles are changed.
The archive contains database data, not external attachments/Drive documents.
"""
from datetime import datetime, timezone
import getpass
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from tools.local_pg_config import DB_NAME, ROOT, load_config


class BackupTestError(Exception):
    pass


def tool_path(name):
    candidates = []
    if os.getenv('POSTGRES_BIN'):
        candidates.append(Path(os.environ['POSTGRES_BIN']) / (name + '.exe' if os.name == 'nt' else name))
    candidates.append(Path(r'C:\Program Files\PostgreSQL\18\bin') / (name + '.exe'))
    installed = shutil.which(name)
    if installed:
        candidates.append(Path(installed))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise BackupTestError(f'Nu gasesc {name}. Verifica instalarea PostgreSQL sau POSTGRES_BIN.')


def source_parameters():
    params = conninfo_to_dict(load_config()['DATABASE_URL'])
    if params.get('host') not in ('127.0.0.1', 'localhost', '::1') or params.get('dbname') != DB_NAME:
        raise BackupTestError('Configuratia nu indica baza locala de test.')
    # Use only the validated local connection fields. Do not inherit service/options.
    return {key: params[key] for key in ('host', 'port', 'dbname', 'user', 'password') if key in params}


def cli_environment(params):
    env = dict(os.environ)
    for name in list(env):
        if name.startswith('PG'):
            del env[name]
    env.update(PGHOST=params['host'], PGPORT=params.get('port', '5432'),
               PGUSER=params['user'], PGPASSWORD=params.get('password', ''),
               PGCLIENTENCODING='UTF8', PGCONNECT_TIMEOUT='10', PGAPPNAME='ecoloptim_backup_test')
    return env


def run_tool(args, env, label):
    result = subprocess.run(args, env=env, capture_output=True, text=True,
                            encoding='utf-8', errors='replace', timeout=180)
    if result.returncode:
        # Server SQL traces may contain row data. Print a code, not data or credentials.
        raise BackupTestError(f'{label}: esec, cod {result.returncode}. Arhiva si baza de test sunt pastrate.')
    return result.stdout


def rows_digest(rows):
    digest = hashlib.sha256()
    for value in sorted(rows):
        encoded = value.encode('utf-8')
        digest.update(len(encoded).to_bytes(8, 'big'))
        digest.update(encoded)
    return digest.hexdigest()


def fingerprint(conn):
    tables = [row[0] for row in conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    result = {}
    for table in tables:
        query = sql.SQL('SELECT row_to_json(t)::text FROM {}.{} AS t').format(
            sql.Identifier('public'), sql.Identifier(table))
        rows = [row[0] for row in conn.execute(query)]
        result[table] = {'rows': len(rows), 'sha256': rows_digest(rows)}
    columns = conn.execute("""
        SELECT table_name, column_name, data_type, udt_name, is_nullable,
               column_default, is_identity, identity_generation, numeric_precision, numeric_scale
        FROM information_schema.columns WHERE table_schema='public'
        ORDER BY table_name, ordinal_position
    """).fetchall()
    constraints = conn.execute("""
        SELECT t.relname, c.conname, c.contype, pg_get_constraintdef(c.oid)
        FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid
        JOIN pg_namespace n ON n.oid=t.relnamespace
        WHERE n.nspname='public' ORDER BY t.relname, c.conname
    """).fetchall()
    indexes = conn.execute("SELECT tablename, indexname, indexdef FROM pg_indexes "
                           "WHERE schemaname='public' ORDER BY tablename,indexname").fetchall()
    return {'tables': result, 'columns': columns, 'constraints': constraints, 'indexes': indexes}


def compare_fingerprints(source, restored):
    if source != restored:
        raise BackupTestError('Datele sau structura restaurata difera de copia sursei. Verificarea NU a trecut.')


def check_identity_counters(conn):
    identities = conn.execute("SELECT table_name,column_name FROM information_schema.columns "
                              "WHERE table_schema='public' AND is_identity='YES'").fetchall()
    for table, column in identities:
        sequence = conn.execute('SELECT pg_get_serial_sequence(%s,%s)',
                                (f'public.{table}', column)).fetchone()[0]
        schema, sequence_name = conn.execute(
            'SELECT n.nspname,c.relname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
            'WHERE c.oid=%s::regclass', (sequence,)).fetchone()
        last, called = conn.execute(sql.SQL('SELECT last_value,is_called FROM {}.{}').format(
            sql.Identifier(schema), sql.Identifier(sequence_name))).fetchone()
        maximum = conn.execute(sql.SQL('SELECT MAX({}) FROM public.{}').format(
            sql.Identifier(column), sql.Identifier(table))).fetchone()[0]
        # All identity sequences in the application increment by one.
        if maximum is not None and (last + (1 if called else 0)) <= maximum:
            raise BackupTestError(f'Contorul pentru {table} nu este sigur dupa restaurare.')


def restore_arguments(binary, target_name, backup):
    if target_name == DB_NAME or not re.fullmatch(r'ecoloptim_restore_[0-9]{14}_[a-f0-9]{8}_test', target_name):
        raise BackupTestError('Restaurarea este permisa numai intr-o baza noua generata de acest script.')
    # --clean addresses the pre-existing public schema in a NEW template0 database.
    # This function refuses the source name and any pre-existing user-supplied name.
    return [binary, '--dbname', target_name, '--no-password', '--no-owner', '--no-privileges',
            '--clean', '--if-exists', '--single-transaction', '--exit-on-error', str(backup)]


def main():
    source = source_parameters()
    dump_bin, restore_bin = tool_path('pg_dump'), tool_path('pg_restore')
    env = cli_environment(source)
    stamp = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
    token = secrets.token_hex(4)
    folder = ROOT / 'backups'
    folder.mkdir(exist_ok=True)
    backup = folder / f'{DB_NAME}_{stamp}_{token}.dump'
    report_path = folder / f'{DB_NAME}_{stamp}_{token}_verificare.json'
    target_name = f'ecoloptim_restore_{stamp}_{token}_test'

    print('1/4 Creez backupul bazei locale de test...')
    # Keep the exported snapshot open until pg_dump finishes. Manifest and archive
    # see the same committed rows even if another session saves a change meanwhile.
    with psycopg.connect(**source, connect_timeout=10, options='-c search_path=public') as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        snapshot = conn.execute('SELECT pg_export_snapshot()').fetchone()[0]
        source_manifest = fingerprint(conn)
        run_tool([dump_bin, '--dbname', DB_NAME, '--no-password', '--format=custom',
                  '--schema=public', '--no-owner', '--no-privileges', '--snapshot', snapshot,
                  '--file', str(backup)], env, 'Backup')
    if not backup.is_file() or not backup.stat().st_size:
        raise BackupTestError('Nu a fost creat un backup valid.')
    if os.name != 'nt':
        backup.chmod(0o600)
    print('BACKUP OK:', backup)

    print('2/4 Creez o baza noua pentru proba de restaurare...')
    admin_user = input('Utilizator administrator PostgreSQL [postgres]: ').strip() or 'postgres'
    admin_password = getpass.getpass('Parola administratorului PostgreSQL (nu se afiseaza): ')
    admin_params = dict(source, dbname='postgres', user=admin_user, password=admin_password)
    with psycopg.connect(**admin_params, autocommit=True, connect_timeout=10) as admin:
        if admin.execute('SELECT 1 FROM pg_database WHERE datname=%s', (target_name,)).fetchone():
            raise BackupTestError('Numele bazei de restaurare exista deja. Nu am modificat-o.')
        admin.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING {}').format(
            sql.Identifier(target_name), sql.Identifier(source['user']), sql.Literal('UTF8')))
        admin.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(target_name)))
    print('Baza pentru restaurare:', target_name)
    print('3/4 Restaurez backupul in baza noua...')
    run_tool(restore_arguments(restore_bin, target_name, backup), env, 'Restaurare')
    print('RESTAURARE OK')

    print('4/4 Compar datele, structura si contoarele...')
    target = dict(source, dbname=target_name)
    with psycopg.connect(**target, connect_timeout=10, options='-c search_path=public') as conn:
        conn.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        restored_manifest = fingerprint(conn)
        compare_fingerprints(source_manifest, restored_manifest)
        check_identity_counters(conn)
    # Report contains counts/hashes only. No source rows, passwords or connection URLs.
    report = {'source_database': DB_NAME, 'restored_database': target_name,
              'backup_file': str(backup), 'verified_at_utc': datetime.now(timezone.utc).isoformat(),
              'verified': True, 'tables': source_manifest['tables']}
    report_path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print('VERIFICARE DATE SI STRUCTURA: OK')
    for table in ('clienti', 'lucrari', 'facturi', 'plati'):
        print(f"  {table}: {source_manifest['tables'][table]['rows']}")
    print('Raport:', report_path)
    print('PROBA BACKUP SI RESTAURARE: OK')
    print('Aplicatia continua sa foloseasca baza initiala. Baza restaurata este pastrata separat.')
    print('Acest backup include baza de date; documentele externe nu sunt incluse.')


if __name__ == '__main__':
    try:
        main()
    except (BackupTestError, OSError, ValueError, KeyError, subprocess.TimeoutExpired, psycopg.Error) as exc:
        print('PROBA BACKUP SI RESTAURARE: NEFINALIZATA')
        if isinstance(exc, BackupTestError):
            print(str(exc))
        elif isinstance(exc, psycopg.Error):
            print('Etapa PostgreSQL a esuat. Cod SQL:', exc.sqlstate or 'conexiune')
        elif isinstance(exc, subprocess.TimeoutExpired):
            print('Utilitarul a depasit limita de timp. Fisierele create sunt pastrate.')
        else:
            print('Verifica fisierele locale, configuratia si accesul la folderul backups.')
        raise SystemExit(1)
