"""Create a NEW local test database with its own application role."""
import getpass
import secrets
from urllib.parse import quote

import psycopg
from psycopg import sql
from db import db
from tools.local_pg_config import CONFIG, ROOT, DB_NAME, ROLE_NAME, write_config


def main():
    if CONFIG.exists():
        raise ValueError('Configuratia exista deja. Foloseste tools.start_postgres_test.')
    port = int(input('Port PostgreSQL [5432]: ').strip() or '5432')
    if not 1 <= port <= 65535:
        raise ValueError('Port invalid.')
    user = input('Utilizator administrator PostgreSQL [postgres]: ').strip() or 'postgres'
    password = getpass.getpass('Parola administratorului PostgreSQL (nu se afiseaza): ')
    admin_password = getpass.getpass('Alege parola admin pentru aplicatia noua (minimum 8 caractere): ')
    if len(admin_password) < 8:
        raise ValueError('Parola aplicatiei trebuie sa aiba minimum 8 caractere.')
    if admin_password != getpass.getpass('Repeta parola admin a aplicatiei: '):
        raise ValueError('Parolele aplicatiei nu coincid.')
    role_password = secrets.token_urlsafe(32)
    role_created = database_created = False
    with psycopg.connect(host='127.0.0.1', port=port, dbname='postgres', user=user,
                         password=password, autocommit=True, connect_timeout=10) as conn:
        if conn.execute('SELECT 1 FROM pg_database WHERE datname=%s', (DB_NAME,)).fetchone():
            raise ValueError('Baza de test exista deja. Nu am modificat-o.')
        if conn.execute('SELECT 1 FROM pg_roles WHERE rolname=%s', (ROLE_NAME,)).fetchone():
            raise ValueError('Rolul de test exista deja. Nu am modificat nimic.')
        try:
            conn.execute(sql.SQL('CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD {}')
                         .format(sql.Identifier(ROLE_NAME), sql.Literal(role_password)))
            role_created = True
            conn.execute(sql.SQL('CREATE DATABASE {} OWNER {} TEMPLATE template0 ENCODING {}')
                         .format(sql.Identifier(DB_NAME), sql.Identifier(ROLE_NAME), sql.Literal('UTF8')))
            database_created = True
            conn.execute(sql.SQL('REVOKE CONNECT ON DATABASE {} FROM PUBLIC').format(sql.Identifier(DB_NAME)))
            url = f'postgresql://{ROLE_NAME}:{quote(role_password, safe="")}@127.0.0.1:{port}/{DB_NAME}'
            db.DATABASE_URL = url
            db.DATABASE_SCHEMA = "public"
            db.DEFAULT_ADMIN_PASSWORD = admin_password
            db.init_db()
            write_config({'DATABASE_URL': url, 'UPLOAD_DIR': str(ROOT / 'uploads_pg_test')})
        except Exception:
            # Keep a successfully created database for diagnosis; never delete data here.
            if role_created and not database_created:
                conn.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(ROLE_NAME)))
            raise
    print('Baza noua de test este pregatita. Adminul aplicatiei foloseste parola aleasa de tine.')
    print('Pornire: .venv\\Scripts\\python.exe -m tools.start_postgres_test')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, psycopg.Error) as exc:
        # Do not render connection strings, generated role passwords, or raw server traces.
        print('Configurarea nu s-a terminat. ' + (str(exc) if isinstance(exc, ValueError)
                                                 else 'Verifica serverul local, portul si datele de autentificare.'))
        raise SystemExit(1)
