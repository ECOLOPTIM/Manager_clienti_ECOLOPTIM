import sqlite3
import datetime
import os
import hashlib
import hmac
import secrets
import re
import unicodedata
import math
from contextlib import closing
from pathlib import Path
import pandas as pd

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DATABASE_SCHEMA = os.getenv("DATABASE_SCHEMA", "public")

DB_PATH = os.getenv("DB_PATH", "manager_clienti_modern.db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
PBKDF2_ITERATIONS = 600_000
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))  # 20 MB default


class ConcurrentWorkEditError(ValueError):
    """The work changed or disappeared after its edit form was opened."""


def _connect():
    if not DATABASE_URL:
        return sqlite3.connect(DB_PATH)
    if not DATABASE_URL.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL trebuie sa fie o adresa PostgreSQL valida.")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", DATABASE_SCHEMA):
        raise ValueError("Nume de schema PostgreSQL invalid.")
    import psycopg
    return psycopg.connect(DATABASE_URL, connect_timeout=10,
                           options=f"-c search_path={DATABASE_SCHEMA}")


def _execute(cursor, query: str, params=None):
    if DATABASE_URL:
        # All SQL templates in this module use ? only for bind markers.
        # Percent signs in SQL literals are escaped for psycopg, not in values.
        if params is not None:
            query = query.replace("%", "%%").replace("?", "%s")
        query = query.replace(" LIKE ", " ILIKE ")
    return cursor.execute(query, params) if params is not None else cursor.execute(query)


def _read_frame(query: str, conn, params=None) -> pd.DataFrame:
    with closing(conn.cursor()) as cur:
        _execute(cur, query, params)
        return pd.DataFrame.from_records(cur.fetchall(),
                                        columns=[col[0] for col in cur.description],
                                        coerce_float=True)


def _init_postgres():
    with closing(_connect()) as conn, conn:
        with conn.cursor() as cur:
            # Serialize initialization across browser sessions and processes.
            cur.execute("SELECT pg_advisory_xact_lock(452601021)")
            _execute(cur, "SELECT to_regclass(?)", (f"{DATABASE_SCHEMA}.ecoloptim_schema_version",))
            if cur.fetchone()[0] is None:
                _execute(cur, "SELECT tablename FROM pg_tables WHERE schemaname=?", (DATABASE_SCHEMA,))
                if cur.fetchone() is not None:
                    raise ValueError("Baza PostgreSQL nu este goala. Foloseste o baza noua de test.")
                schema = Path(__file__).with_name("schema_postgres.sql").read_text(encoding="utf-8")
                cur.execute(schema)
                cur.execute("CREATE TABLE ecoloptim_schema_version (version INTEGER PRIMARY KEY)")
                cur.execute("INSERT INTO ecoloptim_schema_version VALUES (1)")
                cur.execute("INSERT INTO utilizatori "
                            "(username, parola, rol, activ, must_change_password, created_at) "
                            "VALUES (%s, %s, 'admin', 1, 1, %s)",
                            ("admin", hash_password(DEFAULT_ADMIN_PASSWORD), str(datetime.datetime.now())))
            else:
                cur.execute("SELECT version FROM ecoloptim_schema_version")
                if cur.fetchall() not in ([(1,)], [(2,)]):
                    raise ValueError("Versiune de schema PostgreSQL incompatibila.")
            from db.iugn import migrate
            migrate(conn)
            from db.company import migrate as migrate_company
            migrate_company(conn)
            from db.iugn_documents import migrate as migrate_contracts
            migrate_contracts(conn)
            cur.execute('UPDATE ecoloptim_schema_version SET version=2 WHERE version=1')


def _ensure_parent_dir(file_path: str):
    parent = os.path.dirname(file_path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${PBKDF2_ITERATIONS}${salt}${dk.hex()}"


def verify_password(password: str, stored_value: str) -> bool:
    if not stored_value:
        return False

    if not stored_value.startswith("pbkdf2_sha256$"):
        return hmac.compare_digest(password, stored_value)

    try:
        _, iterations_str, salt, stored_hash = stored_value.split("$", 3)
        iterations = int(iterations_str)
        dk = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            iterations,
        )
        return hmac.compare_digest(dk.hex(), stored_hash)
    except Exception:
        return False


def _table_columns(conn: sqlite3.Connection, table_name: str) -> set:
    cur = conn.cursor()
    _execute(cur, f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, col_name: str, col_type: str):
    cols = _table_columns(conn, table_name)
    if col_name in cols:
        return
    cur = conn.cursor()
    _execute(cur, f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")


def _migrate_schema(conn: sqlite3.Connection):
    cur = conn.cursor()

    _execute(cur, """
        CREATE TABLE IF NOT EXISTS documente_seq (
            an INTEGER PRIMARY KEY,
            last_os INTEGER NOT NULL DEFAULT 0
        )
    """)

    _execute(cur, """
        CREATE TABLE IF NOT EXISTS contracte_seq (
            an INTEGER PRIMARY KEY,
            last_ctr INTEGER NOT NULL DEFAULT 0
        )
    """)

    _execute(cur, """
        CREATE TABLE IF NOT EXISTS registru_seq_client (
            client_id INTEGER PRIMARY KEY,
            last_nr INTEGER NOT NULL DEFAULT 0
        )
    """)

    _execute(cur, """
        CREATE TABLE IF NOT EXISTS sarcini (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            lucrare_id INTEGER NOT NULL,
            tip_sarcina TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'NOU',
            responsabil TEXT,
            data_scadenta TEXT,
            observatii TEXT,
            created_at TEXT,
            created_by TEXT,
            closed_at TEXT,
            ordine INTEGER
        )
    """)

    _execute(cur, """
        CREATE TABLE IF NOT EXISTS inregistrari (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            lucrare_id INTEGER NOT NULL,
            sarcina_id INTEGER,
            nr_inregistrare TEXT NOT NULL,
            data TEXT,
            descriere TEXT,
            created_at TEXT,
            created_by TEXT
        )
    """)

    _add_column_if_missing(conn, "lucrari", "adresa_judet", "TEXT")
    _add_column_if_missing(conn, "lucrari", "adresa_localitate", "TEXT")
    _add_column_if_missing(conn, "lucrari", "adresa_strada", "TEXT")
    _add_column_if_missing(conn, "lucrari", "revision", "INTEGER NOT NULL DEFAULT 0")
    _add_column_if_missing(conn, "lucrari", "adresa_numar", "TEXT")
    _add_column_if_missing(conn, "lucrari", "adresa_bloc", "TEXT")
    _add_column_if_missing(conn, "lucrari", "adresa_apartament", "TEXT")
    _add_column_if_missing(conn, "lucrari", "interval_orar", "TEXT")
    _add_column_if_missing(conn, "lucrari", "echipa", "TEXT")
    _add_column_if_missing(conn, "lucrari", "sef_echipa", "TEXT")
    _add_column_if_missing(conn, "lucrari", "avans", "REAL")
    _add_column_if_missing(conn, "lucrari", "cod_atr", "TEXT")
    _add_column_if_missing(conn, "lucrari", "executant", "TEXT")
    _add_column_if_missing(conn, "lucrari", "element_sda", "TEXT")
    _add_column_if_missing(conn, "lucrari", "comanda_aprovizionare", "TEXT")
    _add_column_if_missing(conn, "lucrari", "diriginte_santier", "TEXT")
    _add_column_if_missing(conn, "lucrari", "contract_prestari_servicii", "TEXT")
    _add_column_if_missing(conn, "lucrari", "numar_conventie_tehnica", "TEXT")

    _add_column_if_missing(conn, "lucrari", "data_programare_pif", "TEXT")
    _add_column_if_missing(conn, "lucrari", "interval_orar_pif", "TEXT")
    _add_column_if_missing(conn, "lucrari", "echipa_pif", "TEXT")
    _add_column_if_missing(conn, "lucrari", "sef_echipa_pif", "TEXT")

    _add_column_if_missing(conn, "atasamente", "lucrare_id", "INTEGER")
    _add_column_if_missing(conn, "atasamente", "sarcina_id", "INTEGER")

    _add_column_if_missing(conn, "clienti", "cnp", "TEXT")
    _add_column_if_missing(conn, "clienti", "ci_serie", "TEXT")
    _add_column_if_missing(conn, "clienti", "ci_numar", "TEXT")
    _add_column_if_missing(conn, "clienti", "ci_emitent", "TEXT")
    _add_column_if_missing(conn, "clienti", "ci_data", "TEXT")
    _add_column_if_missing(conn, "clienti", "domiciliu_scara", "TEXT")
    _add_column_if_missing(conn, "clienti", "domiciliu_etaj", "TEXT")

    _add_column_if_missing(conn, "utilizatori", "rol", "TEXT")
    _add_column_if_missing(conn, "utilizatori", "activ", "INTEGER DEFAULT 1")
    _add_column_if_missing(conn, "utilizatori", "must_change_password", "INTEGER DEFAULT 0")
    _add_column_if_missing(conn, "utilizatori", "created_at", "TEXT")

    _execute(cur, "UPDATE utilizatori SET rol='birou' WHERE rol IS NULL OR TRIM(rol)=''")
    _execute(cur, "UPDATE utilizatori SET activ=1 WHERE activ IS NULL")
    _execute(cur, "UPDATE utilizatori SET must_change_password=0 WHERE must_change_password IS NULL")
    _execute(cur, "UPDATE utilizatori SET rol='admin' WHERE username='admin'")

    from db.iugn import migrate
    migrate(conn)
    from db.company import migrate as migrate_company
    migrate_company(conn)
    from db.iugn_documents import migrate as migrate_contracts
    migrate_contracts(conn)

    conn.commit()


def init_db():
    if DATABASE_URL:
        _init_postgres()
        return
    _ensure_parent_dir(DB_PATH)

    with closing(_connect()) as conn, conn:
        c = conn.cursor()

        _execute(c, """
            CREATE TABLE IF NOT EXISTS utilizatori (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                parola TEXT NOT NULL,
                rol TEXT NOT NULL DEFAULT 'birou',
                activ INTEGER NOT NULL DEFAULT 1,
                must_change_password INTEGER NOT NULL DEFAULT 0,
                created_at TEXT
            )
        """)

        _execute(c, """
            CREATE TABLE IF NOT EXISTS clienti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nume TEXT,
                email TEXT,
                telefon TEXT,
                firma TEXT,
                status TEXT,
                observatii TEXT,
                data_adaugarii TEXT,
                cod_intern TEXT,
                scor INTEGER,
                remark TEXT,
                domiciliu_judet TEXT,
                domiciliu_localitate TEXT,
                domiciliu_strada TEXT,
                domiciliu_numar TEXT,
                domiciliu_bloc TEXT,
                domiciliu_apartament TEXT,
                consum_judet TEXT,
                consum_localitate TEXT,
                consum_strada TEXT,
                consum_numar TEXT,
                consum_bloc TEXT,
                consum_apartament TEXT
            )
        """)

        _execute(c, """
            CREATE TABLE IF NOT EXISTS lucrari (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER,
                tip_lucrare TEXT,
                valoare_contractata REAL,
                responsabil TEXT,
                status TEXT,
                data_contract TEXT,
                data_programare TEXT,
                observatii TEXT,
                descriere TEXT
            )
        """)

        _execute(c, """
            CREATE TABLE IF NOT EXISTS atasamente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                uploaded_by TEXT,
                upload_date TEXT
            )
        """)

        _execute(c, """
            CREATE TABLE IF NOT EXISTS facturi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                numar TEXT,
                data_emiterii TEXT,
                data_scadenta TEXT,
                total REAL NOT NULL DEFAULT 0,
                moneda TEXT NOT NULL DEFAULT 'RON',
                status TEXT NOT NULL DEFAULT 'NEINCASATA',
                observatii TEXT,
                created_at TEXT,
                created_by TEXT
            )
        """)

        _execute(c, """
            CREATE TABLE IF NOT EXISTS plati (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                factura_id INTEGER NOT NULL,
                data_platii TEXT,
                suma REAL NOT NULL DEFAULT 0,
                metoda TEXT,
                observatii TEXT,
                created_at TEXT,
                created_by TEXT
            )
        """)

        _migrate_schema(conn)

        _execute(c, "SELECT COUNT(*) FROM utilizatori")
        if c.fetchone()[0] == 0:
            _execute(c,
                """
                INSERT INTO utilizatori (username, parola, rol, activ, must_change_password, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "admin",
                    hash_password(DEFAULT_ADMIN_PASSWORD),
                    "admin",
                    1,
                    1,
                    str(datetime.datetime.now()),
                )
            )

        conn.commit()


def login(user, pwd):
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, """
            SELECT id, username, parola, rol, activ, must_change_password, created_at
            FROM utilizatori
            WHERE username=?
        """, (user,))
        row = c.fetchone()

        if not row:
            return None

        stored_password = row[2]
        activ = int(row[4] or 0)

        if activ != 1:
            return None

        if verify_password(pwd, stored_password):
            return row

        return None


def _next_document_number(table: str, key_name: str, counter: str, key: int) -> int:
    allowed = {("documente_seq", "an", "last_os"),
               ("contracte_seq", "an", "last_ctr"),
               ("registru_seq_client", "client_id", "last_nr")}
    if (table, key_name, counter) not in allowed:
        raise ValueError("Contor necunoscut.")
    with closing(_connect()) as conn, conn:
        cur = conn.cursor()
        _execute(cur, f"INSERT INTO {table} ({key_name}, {counter}) VALUES (?, 1) "
                      f"ON CONFLICT ({key_name}) DO UPDATE SET {counter}={table}.{counter}+1 "
                      f"RETURNING {counter}", (int(key),))
        return int(cur.fetchone()[0])


def genereaza_nr_os(an: int | None = None) -> str:
    year = int(an if an is not None else datetime.datetime.now().year)
    value = _next_document_number("documente_seq", "an", "last_os", year)
    return f"OS-{year}-{value:04d}"


def genereaza_nr_contract(an: int | None = None) -> str:
    year = int(an if an is not None else datetime.datetime.now().year)
    value = _next_document_number("contracte_seq", "an", "last_ctr", year)
    return f"CTR-{year}-{value:04d}"


def genereaza_nr_inregistrare_client(client_id: int, an: int | None = None) -> str:
    year = int(an if an is not None else datetime.datetime.now().year)
    value = _next_document_number("registru_seq_client", "client_id", "last_nr", int(client_id))
    return f"REG-{int(client_id)}-{year}-{value:04d}"


def adauga_inregistrare(client_id: int, lucrare_id: int, sarcina_id: int | None, descriere: str, created_by: str) -> str:
    nr = genereaza_nr_inregistrare_client(int(client_id))
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, """
            INSERT INTO inregistrari (
                client_id, lucrare_id, sarcina_id, nr_inregistrare, data, descriere, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(client_id),
            int(lucrare_id),
            int(sarcina_id) if sarcina_id is not None else None,
            nr,
            str(datetime.datetime.now().date()),
            descriere or "",
            str(datetime.datetime.now()),
            created_by or "",
        ))
        conn.commit()
    return nr


def lista_inregistrari(client_id: int, lucrare_id: int | None = None, sarcina_id: int | None = None) -> pd.DataFrame:
    q = "SELECT * FROM inregistrari WHERE client_id=?"
    params: list = [int(client_id)]

    if lucrare_id is not None:
        q += " AND lucrare_id=?"
        params.append(int(lucrare_id))
    if sarcina_id is not None:
        q += " AND sarcina_id=?"
        params.append(int(sarcina_id))

    q += " ORDER BY created_at DESC, id DESC"

    with closing(_connect()) as conn, conn:
        return _read_frame(q, conn, params=params)


def _require_client(conn: sqlite3.Connection, client_id: int):
    if _execute(conn, "SELECT 1 FROM clienti WHERE id=?", (int(client_id),)).fetchone() is None:
        raise ValueError("Clientul nu exista.")


def _positive_amount(value, label: str) -> float:
    try:
        amount = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"{label} trebuie sa fie un numar pozitiv finit.") from exc
    if not math.isfinite(amount) or amount <= 0:
        raise ValueError(f"{label} trebuie sa fie un numar pozitiv finit.")
    return amount


def adauga_client(valori: dict):
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, """
            INSERT INTO clienti (
                nume, email, telefon, firma, status, observatii, data_adaugarii, cod_intern, scor, remark,
                domiciliu_judet, domiciliu_localitate, domiciliu_strada, domiciliu_numar, domiciliu_bloc, domiciliu_scara, domiciliu_etaj, domiciliu_apartament,
                consum_judet, consum_localitate, consum_strada, consum_numar, consum_bloc, consum_apartament,
                cnp, ci_serie, ci_numar, ci_emitent, ci_data
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            valori.get("nume", ""), valori.get("email", ""), valori.get("telefon", ""), valori.get("firma", ""),
            valori.get("status", ""), valori.get("observatii", ""), str(datetime.datetime.now()),
            valori.get("cod_intern", ""), int(valori.get("scor", 0) or 0), valori.get("remark", ""),
            valori.get("domiciliu_judet", ""),
            valori.get("domiciliu_localitate", ""), valori.get("domiciliu_strada", ""), valori.get("domiciliu_numar", ""),
            valori.get("domiciliu_bloc", ""), valori.get("domiciliu_scara", ""), valori.get("domiciliu_etaj", ""), valori.get("domiciliu_apartament", ""),
            valori.get("consum_judet", ""),
            valori.get("consum_localitate", ""), valori.get("consum_strada", ""), valori.get("consum_numar", ""),
            valori.get("consum_bloc", ""), valori.get("consum_apartament", ""),
            valori.get("cnp", ""),
            valori.get("ci_serie", ""),
            valori.get("ci_numar", ""),
            valori.get("ci_emitent", ""),
            valori.get("ci_data", ""),
        ])
        conn.commit()


def lista_clienti(filtru: str = "") -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        if filtru:
            like = f"%{str(filtru).strip()}%"
            return _read_frame(
                """
                SELECT * FROM clienti
                WHERE
                    nume LIKE ?
                    OR email LIKE ?
                    OR telefon LIKE ?
                    OR firma LIKE ?
                    OR cod_intern LIKE ?
                ORDER BY data_adaugarii DESC, id DESC
                """,
                conn,
                params=[like, like, like, like, like],
            )
        return _read_frame("SELECT * FROM clienti ORDER BY data_adaugarii DESC, id DESC", conn)


def modifica_client(id_cli: int, valori: dict):
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, """UPDATE clienti SET
            nume=?, email=?, telefon=?, firma=?, status=?, observatii=?, cod_intern=?, scor=?, remark=?,
            domiciliu_judet=?, domiciliu_localitate=?, domiciliu_strada=?, domiciliu_numar=?, domiciliu_bloc=?, domiciliu_scara=?, domiciliu_etaj=?, domiciliu_apartament=?,
            consum_judet=?, consum_localitate=?, consum_strada=?, consum_numar=?, consum_bloc=?, consum_apartament=?,
            cnp=?, ci_serie=?, ci_numar=?, ci_emitent=?, ci_data=?
            WHERE id=?""",
                  [
                      valori.get("nume", ""), valori.get("email", ""), valori.get("telefon", ""), valori.get("firma", ""),
                      valori.get("status", ""), valori.get("observatii", ""), valori.get("cod_intern", ""),
                      int(valori.get("scor", 0) or 0), valori.get("remark", ""),
                      valori.get("domiciliu_judet", ""),
                      valori.get("domiciliu_localitate", ""), valori.get("domiciliu_strada", ""),
                      valori.get("domiciliu_numar", ""),
                      valori.get("domiciliu_bloc", ""), valori.get("domiciliu_scara", ""), valori.get("domiciliu_etaj", ""), valori.get("domiciliu_apartament", ""),
                      valori.get("consum_judet", ""),
                      valori.get("consum_localitate", ""), valori.get("consum_strada", ""), valori.get("consum_numar", ""),
                      valori.get("consum_bloc", ""), valori.get("consum_apartament", ""),
                      valori.get("cnp", ""),
                      valori.get("ci_serie", ""),
                      valori.get("ci_numar", ""),
                      valori.get("ci_emitent", ""),
                      valori.get("ci_data", ""),
                      int(id_cli)
                  ])
        conn.commit()


def dependinte_client(id_cli: int) -> dict:
    client_id = int(id_cli)

    with closing(_connect()) as conn, conn:
        c = conn.cursor()

        _execute(c, "SELECT COUNT(*) FROM lucrari WHERE client_id=?", (client_id,))
        nr_lucrari = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM facturi WHERE client_id=?", (client_id,))
        nr_facturi = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM plati WHERE client_id=?", (client_id,))
        nr_plati = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM atasamente WHERE client_id=?", (client_id,))
        nr_atasamente = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM inregistrari WHERE client_id=?", (client_id,))
        nr_inregistrari = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM sarcini WHERE client_id=?", (client_id,))
        nr_sarcini = int(c.fetchone()[0] or 0)

    return {
        "lucrari": nr_lucrari,
        "facturi": nr_facturi,
        "plati": nr_plati,
        "atasamente": nr_atasamente,
        "inregistrari": nr_inregistrari,
        "sarcini": nr_sarcini,
    }


def sterge_client(id_cli: int):
    client_id = int(id_cli)
    deps = dependinte_client(client_id)

    exista_dependinte = any(int(v or 0) > 0 for v in deps.values())
    if exista_dependinte:
        parts = []
        for label, count in deps.items():
            if int(count or 0) > 0:
                parts.append(f"{label}: {count}")
        raise ValueError(
            "Clientul nu poate fi șters deoarece are date asociate: " + ", ".join(parts) + "."
        )

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "DELETE FROM clienti WHERE id=?", (client_id,))
        conn.commit()


def lista_atasamente(client_id: int, lucrare_id: int | None = None, sarcina_id: int | None = None) -> pd.DataFrame:
    q = "SELECT * FROM atasamente WHERE client_id=?"
    params: list = [int(client_id)]

    if lucrare_id is not None:
        q += " AND lucrare_id=?"
        params.append(int(lucrare_id))
    if sarcina_id is not None:
        q += " AND sarcina_id=?"
        params.append(int(sarcina_id))

    q += " ORDER BY upload_date DESC, id DESC"

    with closing(_connect()) as conn, conn:
        return _read_frame(q, conn, params=params)


def _sanitize_filename(filename: str) -> str:
    name = os.path.basename(str(filename or "")).strip()
    if not name:
        raise ValueError("Nume fișier invalid.")

    # normalize unicode -> ascii fallback
    norm = unicodedata.normalize("NFKD", name)
    ascii_name = norm.encode("ascii", "ignore").decode("ascii")

    # keep safe chars only
    ascii_name = re.sub(r"[^A-Za-z0-9._\- ]+", "_", ascii_name)
    ascii_name = ascii_name.strip(" .")
    if not ascii_name:
        raise ValueError("Nume fișier invalid după sanitizare.")

    # avoid hidden or reserved-like names
    if ascii_name.startswith("."):
        ascii_name = f"file{ascii_name}"

    # hard cap length
    if len(ascii_name) > 180:
        base, ext = os.path.splitext(ascii_name)
        ascii_name = base[:150] + ext[:30]

    return ascii_name


def _unique_filepath(folder: str, filename: str) -> tuple[str, str]:
    base, ext = os.path.splitext(filename)
    candidate_name = filename
    candidate_path = os.path.join(folder, candidate_name)

    if not os.path.exists(candidate_path):
        return candidate_path, candidate_name

    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    candidate_name = f"{base}_{ts}{ext}"
    candidate_path = os.path.join(folder, candidate_name)

    counter = 1
    while os.path.exists(candidate_path):
        candidate_name = f"{base}_{ts}_{counter}{ext}"
        candidate_path = os.path.join(folder, candidate_name)
        counter += 1

    return candidate_path, candidate_name


def save_atasament(
    client_id: int,
    filename: str,
    uploaded_by: str,
    content_bytes: bytes,
    lucrare_id: int | None = None,
    sarcina_id: int | None = None
):
    if content_bytes is None:
        raise ValueError("Conținut fișier lipsă.")
    if len(content_bytes) == 0:
        raise ValueError("Fișierul este gol.")
    if len(content_bytes) > MAX_UPLOAD_BYTES:
        mb = MAX_UPLOAD_BYTES / (1024 * 1024)
        raise ValueError(f"Fișier prea mare. Maxim permis: {mb:.0f} MB.")

    safe_filename = _sanitize_filename(filename)

    upload_dir = os.path.join(UPLOAD_DIR, str(int(client_id)))
    os.makedirs(upload_dir, exist_ok=True)

    filepath, final_filename = _unique_filepath(upload_dir, safe_filename)

    with open(filepath, "wb") as f:
        f.write(content_bytes)

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, """
            INSERT INTO atasamente (client_id, filename, path, uploaded_by, upload_date, lucrare_id, sarcina_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            int(client_id),
            final_filename,
            filepath,
            uploaded_by or "",
            str(datetime.datetime.now()),
            int(lucrare_id) if lucrare_id is not None else None,
            int(sarcina_id) if sarcina_id is not None else None,
        ))
        conn.commit()


def sterge_atasament(atas_id: int):
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT path FROM atasamente WHERE id=?", (int(atas_id),))
        row = c.fetchone()
        if row and row[0] and os.path.exists(row[0]):
            try:
                os.remove(row[0])
            except Exception:
                pass
        _execute(c, "DELETE FROM atasamente WHERE id=?", (int(atas_id),))
        conn.commit()


def flux_sarcini_pentru_tip_lucrare(tip_lucrare: str) -> list[str]:
    base = [
        "Preluare / verificare date",
        "Pregătire documente",
        "Depunere / trimitere",
        "Urmărire răspuns",
        "Închidere dosar",
    ]
    return base


def _creeaza_flux_birou_pentru_lucrare(conn: sqlite3.Connection, client_id: int, lucrare_id: int, tip_lucrare: str, created_by: str):
    from db import iugn, iugn_rules
    from config.workflow_catalog import template_for
    template = template_for(tip_lucrare)
    if template and template['template'] == 'iugn01':
        iugn._initialize(conn, lucrare_id, client_id)
        return
    c = conn.cursor()
    steps = flux_sarcini_pentru_tip_lucrare(tip_lucrare)
    now = str(datetime.datetime.now())
    for i, tip in enumerate(steps, start=1):
        _execute(c, """
            INSERT INTO sarcini (client_id, lucrare_id, ordine, tip_sarcina, status, created_at, created_by)
            VALUES (?, ?, ?, ?, 'NOU', ?, ?)
        """, (int(client_id), int(lucrare_id), int(i), str(tip), now, created_by or ""))


def adauga_lucrare(valori: dict):
    from db.iugn_rules import WORK_TYPE
    if valori.get('tip_lucrare') == WORK_TYPE:
        # Operational facts start unconfirmed; importing a form is not confirmation.
        valori = dict(valori, status='OFERTAT', responsabil='', data_contract='',
                      data_programare='', echipa='', data_programare_pif='', echipa_pif='')
    columns = [
        "client_id",
        "tip_lucrare",
        "valoare_contractata",
        "avans",
        "responsabil",
        "status",
        "data_contract",
        "data_programare",
        "observatii",
        "descriere",
        "adresa_judet",
        "adresa_localitate",
        "adresa_strada",
        "adresa_numar",
        "adresa_bloc",
        "adresa_apartament",
        "interval_orar",
        "echipa",
        "sef_echipa",
        "cod_atr",
        "executant",
        "element_sda",
        "comanda_aprovizionare",
        "diriginte_santier",
        "contract_prestari_servicii",
        "numar_conventie_tehnica",
        "data_programare_pif",
        "interval_orar_pif",
        "echipa_pif",
        "sef_echipa_pif",
    ]

    values = (
        int(valori["client_id"]),
        valori.get("tip_lucrare", ""),
        float(valori.get("valoare_contractata", 0) or 0),
        float(valori.get("avans", 0) or 0),
        valori.get("responsabil", ""),
        valori.get("status", ""),
        valori.get("data_contract", ""),
        valori.get("data_programare", ""),
        valori.get("observatii", ""),
        valori.get("descriere", ""),
        valori.get("adresa_judet", ""),
        valori.get("adresa_localitate", ""),
        valori.get("adresa_strada", ""),
        valori.get("adresa_numar", ""),
        valori.get("adresa_bloc", ""),
        valori.get("adresa_apartament", ""),
        valori.get("interval_orar", ""),
        valori.get("echipa", ""),
        valori.get("sef_echipa", ""),
        valori.get("cod_atr", ""),
        valori.get("executant", ""),
        valori.get("element_sda", ""),
        valori.get("comanda_aprovizionare", ""),
        valori.get("diriginte_santier", ""),
        valori.get("contract_prestari_servicii", ""),
        valori.get("numar_conventie_tehnica", ""),
        valori.get("data_programare_pif", ""),
        valori.get("interval_orar_pif", ""),
        valori.get("echipa_pif", ""),
        valori.get("sef_echipa_pif", ""),
    )

    # --- SELF-CHECK anti "X values for Y columns"
    if len(columns) != len(values):
        raise ValueError(
            f"[adauga_lucrare] Mismatch coloane/valori: {len(columns)} coloane vs {len(values)} valori."
        )

    placeholders = ", ".join(["?"] * len(columns))
    cols_sql = ", ".join(columns)

    with closing(_connect()) as conn, conn:
        _require_client(conn, int(valori["client_id"]))
        c = conn.cursor()
        _execute(c,
            f"INSERT INTO lucrari ({cols_sql}) VALUES ({placeholders}) RETURNING id",
            values
        )

        lucrare_id = int(c.fetchone()[0])
        _creeaza_flux_birou_pentru_lucrare(
            conn=conn,
            client_id=int(valori["client_id"]),
            lucrare_id=lucrare_id,
            tip_lucrare=str(valori.get("tip_lucrare", "")),
            created_by=str(valori.get("created_by", "")),
        )

        conn.commit()


def lista_lucrari() -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame("SELECT * FROM lucrari ORDER BY data_contract DESC, id DESC", conn)


def lista_lucrari_client(client_id: int) -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame(
            "SELECT * FROM lucrari WHERE client_id=? ORDER BY data_contract DESC, id DESC",
            conn,
            params=[int(client_id)],
        )


def get_lucrare(lucrare_id: int) -> dict | None:
    with closing(_connect()) as conn, conn:
        cur = conn.cursor()
        _execute(cur, "SELECT * FROM lucrari WHERE id=?", (int(lucrare_id),))
        row = cur.fetchone()
        return dict(zip([col[0] for col in cur.description], row)) if row else None


def modifica_lucrare(lucrare_id: int, valori: dict, *, expected_revision: int):
    # Require the revision captured when opening the form, never a fresh read.
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Versiunea lucrarii este invalida. Redeschide editarea.")
    set_columns = [
        "client_id",
        "tip_lucrare",
        "valoare_contractata",
        "avans",
        "responsabil",
        "status",
        "data_contract",
        "data_programare",
        "observatii",
        "descriere",
        "adresa_judet",
        "adresa_localitate",
        "adresa_strada",
        "adresa_numar",
        "adresa_bloc",
        "adresa_apartament",
        "interval_orar",
        "echipa",
        "sef_echipa",
        "cod_atr",
        "executant",
        "element_sda",
        "comanda_aprovizionare",
        "diriginte_santier",
        "contract_prestari_servicii",
        "numar_conventie_tehnica",
        "data_programare_pif",
        "interval_orar_pif",
        "echipa_pif",
        "sef_echipa_pif",
    ]

    set_values = (
        int(valori["client_id"]),
        valori.get("tip_lucrare", ""),
        float(valori.get("valoare_contractata", 0) or 0),
        float(valori.get("avans", 0) or 0),
        valori.get("responsabil", ""),
        valori.get("status", ""),
        valori.get("data_contract", ""),
        valori.get("data_programare", ""),
        valori.get("observatii", ""),
        valori.get("descriere", ""),
        valori.get("adresa_judet", ""),
        valori.get("adresa_localitate", ""),
        valori.get("adresa_strada", ""),
        valori.get("adresa_numar", ""),
        valori.get("adresa_bloc", ""),
        valori.get("adresa_apartament", ""),
        valori.get("interval_orar", ""),
        valori.get("echipa", ""),
        valori.get("sef_echipa", ""),
        valori.get("cod_atr", ""),
        valori.get("executant", ""),
        valori.get("element_sda", ""),
        valori.get("comanda_aprovizionare", ""),
        valori.get("diriginte_santier", ""),
        valori.get("contract_prestari_servicii", ""),
        valori.get("numar_conventie_tehnica", ""),
        valori.get("data_programare_pif", ""),
        valori.get("interval_orar_pif", ""),
        valori.get("echipa_pif", ""),
        valori.get("sef_echipa_pif", ""),
    )

    # --- SELF-CHECK anti mismatch
    if len(set_columns) != len(set_values):
        raise ValueError(
            f"[modifica_lucrare] Mismatch coloane/valori: {len(set_columns)} coloane vs {len(set_values)} valori."
        )

    set_sql = ", ".join([f"{col}=?" for col in set_columns])
    params = set_values + (int(lucrare_id), expected_revision)

    with closing(_connect()) as conn, conn:
        _require_client(conn, int(valori["client_id"]))
        c = conn.cursor()
        _execute(c, 'SELECT 1 FROM iugn_flux WHERE lucrare_id=?', (int(lucrare_id),))
        if c.fetchone():
            old = _read_frame('SELECT * FROM lucrari WHERE id=?', conn, [int(lucrare_id)]).iloc[0]
            controlled = ('client_id', 'tip_lucrare', 'responsabil', 'status', 'data_contract',
                          'data_programare', 'echipa', 'data_programare_pif', 'echipa_pif')
            if any(str(valori.get(k) or '') != str(old[k] or '') for k in controlled):
                raise ValueError('Pentru aceasta lucrare, modifica rolurile, etapele si programarile din fluxul IUGN.')
        # One conditional write makes the check atomic even across processes.
        _execute(c,
            f"UPDATE lucrari SET {set_sql}, revision=revision+1 WHERE id=? AND revision=?",
            params,
        )
        if c.rowcount != 1:
            raise ConcurrentWorkEditError(
                "Lucrarea a fost modificată în altă sesiune sau a fost ștearsă. "
                "Modificările tale nu au fost salvate. Copiază textul pe care vrei "
                "să-l păstrezi, apoi reîncarcă lucrarea."
            )
        conn.commit()
    return expected_revision + 1


def dependinte_lucrare(lucrare_id: int) -> dict:
    lid = int(lucrare_id)

    with closing(_connect()) as conn, conn:
        c = conn.cursor()

        _execute(c, "SELECT COUNT(*) FROM sarcini WHERE lucrare_id=?", (lid,))
        nr_sarcini = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM inregistrari WHERE lucrare_id=?", (lid,))
        nr_inregistrari = int(c.fetchone()[0] or 0)

        _execute(c, "SELECT COUNT(*) FROM atasamente WHERE lucrare_id=?", (lid,))
        nr_atasamente = int(c.fetchone()[0] or 0)

    return {
        "sarcini": nr_sarcini,
        "inregistrari": nr_inregistrari,
        "atasamente": nr_atasamente,
    }


def sterge_lucrare(lucrare_id: int):
    lid = int(lucrare_id)
    deps = dependinte_lucrare(lid)

    exista_dependinte = any(int(v or 0) > 0 for v in deps.values())
    if exista_dependinte:
        parts = []
        for label, count in deps.items():
            if int(count or 0) > 0:
                parts.append(f"{label}: {count}")
        raise ValueError(
            "Lucrarea nu poate fi ștearsă deoarece are date asociate: " + ", ".join(parts) + "."
        )

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "DELETE FROM lucrari WHERE id=?", (lid,))
        conn.commit()


def lista_sarcini_lucrare(lucrare_id: int) -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame(
            "SELECT * FROM sarcini WHERE lucrare_id=? ORDER BY COALESCE(ordine, id) ASC",
            conn,
            params=[int(lucrare_id)],
        )


def lista_sarcini_all(filtru_status: str = "", filtru_text: str = "") -> pd.DataFrame:
    q = """
        SELECT
            s.*,
            l.tip_lucrare AS lucrare_tip,
            l.status AS lucrare_status,
            l.data_contract AS lucrare_data_contract,
            l.data_programare AS lucrare_data_programare,
            c.nume AS client_nume
        FROM sarcini s
        LEFT JOIN lucrari l ON l.id = s.lucrare_id
        LEFT JOIN clienti c ON c.id = s.client_id
        WHERE 1=1
    """
    params: list = []

    if filtru_status:
        q += " AND s.status=?"
        params.append(str(filtru_status))

    if filtru_text:
        q += " AND (c.nume LIKE ? OR l.tip_lucrare LIKE ? OR s.tip_sarcina LIKE ?)"
        like = f"%{filtru_text}%"
        params.extend([like, like, like])

    q += " ORDER BY s.created_at DESC, s.id DESC"

    with closing(_connect()) as conn, conn:
        return _read_frame(q, conn, params=params)


def update_sarcina(
    sarcina_id: int,
    status: str | None = None,
    responsabil: str | None = None,
    data_scadenta: str | None = None,
    observatii: str | None = None
):
    fields = []
    params: list = []

    if status is not None:
        fields.append("status=?")
        params.append(str(status))
        if str(status).upper() in ("FINALIZAT", "INCHIS", "ÎNCHIS"):
            fields.append("closed_at=?")
            params.append(str(datetime.datetime.now()))
        else:
            fields.append("closed_at=?")
            params.append(None)

    if responsabil is not None:
        fields.append("responsabil=?")
        params.append(str(responsabil))

    if data_scadenta is not None:
        fields.append("data_scadenta=?")
        params.append(str(data_scadenta))

    if observatii is not None:
        fields.append("observatii=?")
        params.append(str(observatii))

    if not fields:
        return

    params.append(int(sarcina_id))

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, 'SELECT cod_flux FROM sarcini WHERE id=?', (int(sarcina_id),))
        task = c.fetchone()
        if task and task[0]:
            raise ValueError('Sarcina IUGN se actualizeaza prin evenimentul corespunzator din fluxul lucrarii.')
        _execute(c, f"UPDATE sarcini SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()


def lista_facturi(client_id: int) -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame(
            "SELECT * FROM facturi WHERE client_id=? ORDER BY data_emiterii DESC, id DESC",
            conn,
            params=[int(client_id)],
        )


def adauga_factura(valori: dict):
    total = _positive_amount(valori.get("total"), "Totalul facturii")
    with closing(_connect()) as conn, conn:
        _require_client(conn, int(valori["client_id"]))
        c = conn.cursor()
        _execute(c, """
            INSERT INTO facturi (
                client_id, numar, data_emiterii, data_scadenta, total, moneda, status,
                observatii, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(valori["client_id"]),
            valori.get("numar", ""),
            valori.get("data_emiterii", ""),
            valori.get("data_scadenta", ""),
            total,
            valori.get("moneda", "RON"),
            valori.get("status", "NEINCASATA"),
            valori.get("observatii", ""),
            str(datetime.datetime.now()),
            valori.get("created_by", ""),
        ))
        conn.commit()


def anuleaza_factura(factura_id: int):
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "UPDATE facturi SET status='ANULATA' WHERE id=?", (int(factura_id),))
        conn.commit()


def sterge_factura(factura_id: int):
    with closing(_connect()) as conn, conn:
        _lock_invoice(conn, int(factura_id))
        c = conn.cursor()
        _execute(c, "DELETE FROM plati WHERE factura_id=?", (int(factura_id),))
        _execute(c, "DELETE FROM facturi WHERE id=?", (int(factura_id),))
        conn.commit()


def lista_plati(client_id: int) -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame(
            "SELECT * FROM plati WHERE client_id=? ORDER BY data_platii DESC, id DESC",
            conn,
            params=[int(client_id)],
        )


def _lock_invoice(conn, factura_id: int):
    if DATABASE_URL:
        _execute(conn, "SELECT id FROM facturi WHERE id=? FOR UPDATE", (int(factura_id),))
    else:
        _execute(conn, "BEGIN IMMEDIATE")


def _recalculate_invoice(conn, factura_id: int):
    cur = conn.cursor()
    _execute(cur, "SELECT COALESCE(total, 0), status FROM facturi WHERE id=?", (int(factura_id),))
    row = cur.fetchone()
    if not row or row[1] == "ANULATA":
        return
    total = row[0]
    _execute(cur, "SELECT COALESCE(SUM(suma), 0) FROM plati WHERE factura_id=?", (int(factura_id),))
    paid = cur.fetchone()[0]
    status = "NEINCASATA" if paid <= 0 else ("PARTIAL" if paid < total else "INCASATA")
    _execute(cur, "UPDATE facturi SET status=? WHERE id=?", (status, int(factura_id)))


def recalculeaza_status_factura(factura_id: int):
    with closing(_connect()) as conn, conn:
        _lock_invoice(conn, int(factura_id))
        _recalculate_invoice(conn, int(factura_id))


def adauga_plata(valori: dict):
    factura_id = valori.get("factura_id", None)
    if factura_id is None:
        raise ValueError("factura_id este obligatoriu pentru o plată.")
    suma = _positive_amount(valori.get("suma"), "Suma platii")

    with closing(_connect()) as conn, conn:
        _lock_invoice(conn, int(factura_id))
        _require_client(conn, int(valori["client_id"]))
        c = conn.cursor()

        _execute(c, "SELECT status, client_id FROM facturi WHERE id=?", (int(factura_id),))
        row = c.fetchone()
        if not row:
            raise ValueError("Factura nu există.")
        if str(row[0]) == "ANULATA":
            raise ValueError("Nu poți adăuga plată pe o factură ANULATĂ.")
        if int(row[1]) != int(valori["client_id"]):
            raise ValueError("Clientul platii nu corespunde clientului facturii.")

        _execute(c, """
            INSERT INTO plati (
                client_id, factura_id, data_platii, suma, metoda, observatii, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(valori["client_id"]),
            int(factura_id),
            valori.get("data_platii", ""),
            suma,
            valori.get("metoda", ""),
            valori.get("observatii", ""),
            str(datetime.datetime.now()),
            valori.get("created_by", ""),
        ))
        _recalculate_invoice(conn, int(factura_id))
        conn.commit()


def sterge_plata(plata_id: int):
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        if not DATABASE_URL:
            _execute(c, "BEGIN IMMEDIATE")
        _execute(c, "SELECT factura_id FROM plati WHERE id=?", (int(plata_id),))
        row = c.fetchone()
        if row is None:
            return
        factura_id = int(row[0])
        if DATABASE_URL:
            _lock_invoice(conn, factura_id)
        _execute(c, "DELETE FROM plati WHERE id=?", (int(plata_id),))
        _recalculate_invoice(conn, factura_id)


def rezumat_facturi_client(client_id: int) -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame("""
            SELECT
                f.id,
                f.client_id,
                f.numar,
                f.data_emiterii,
                f.data_scadenta,
                f.total,
                f.moneda,
                f.status,
                f.observatii,
                COALESCE(SUM(p.suma), 0) AS incasat,
                (COALESCE(f.total, 0) - COALESCE(SUM(p.suma), 0)) AS rest
            FROM facturi f
            LEFT JOIN plati p ON p.factura_id = f.id
            WHERE f.client_id = ?
            GROUP BY f.id
            ORDER BY f.data_emiterii DESC, f.id DESC
        """, conn, params=[int(client_id)])


def calculeaza_sold_client(client_id: int) -> float:
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT COALESCE(SUM(total), 0) FROM facturi WHERE client_id=? AND status!='ANULATA'", (int(client_id),))
        total_facturi = float(c.fetchone()[0] or 0)
        _execute(c, "SELECT COALESCE(SUM(suma), 0) FROM plati WHERE client_id=?", (int(client_id),))
        total_plati = float(c.fetchone()[0] or 0)
        return total_facturi - total_plati


def solduri_pe_clienti() -> dict:
    with closing(_connect()) as conn, conn:
        c = conn.cursor()

        _execute(c, """
            SELECT client_id, COALESCE(SUM(total), 0)
            FROM facturi
            WHERE status != 'ANULATA'
            GROUP BY client_id
        """)
        facturi = {int(cid): float(total or 0) for cid, total in c.fetchall()}

        _execute(c, """
            SELECT client_id, COALESCE(SUM(suma), 0)
            FROM plati
            GROUP BY client_id
        """)
        plati = {int(cid): float(total or 0) for cid, total in c.fetchall()}

    client_ids = set(facturi.keys()) | set(plati.keys())
    solduri = {}
    for cid in client_ids:
        solduri[cid] = facturi.get(cid, 0.0) - plati.get(cid, 0.0)
    return solduri


def facturat_pe_clienti() -> dict:
    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, """
            SELECT client_id, COALESCE(SUM(total), 0)
            FROM facturi
            WHERE status != 'ANULATA'
            GROUP BY client_id
        """)
        return {int(cid): float(total or 0) for cid, total in c.fetchall()}


def agregate_financiare_clienti() -> pd.DataFrame:
    """
    Returnează un DataFrame cu:
      client_id, valoare_contract, facturat, platit, sold
    - valoare_contract: SUM(lucrari.valoare_contractata)
    - facturat: SUM(facturi.total) pentru facturi != ANULATA
    - platit: SUM(plati.suma)
    - sold: facturat - platit
    """
    q = """
    WITH
    c_lucrari AS (
        SELECT client_id, COALESCE(SUM(valoare_contractata), 0) AS valoare_contract
        FROM lucrari
        GROUP BY client_id
    ),
    c_facturi AS (
        SELECT client_id, COALESCE(SUM(total), 0) AS facturat
        FROM facturi
        WHERE status != 'ANULATA'
        GROUP BY client_id
    ),
    c_plati AS (
        SELECT client_id, COALESCE(SUM(suma), 0) AS platit
        FROM plati
        GROUP BY client_id
    ),
    ids AS (
        SELECT id AS client_id FROM clienti
    )
    SELECT
        ids.client_id,
        COALESCE(c_lucrari.valoare_contract, 0) AS valoare_contract,
        COALESCE(c_facturi.facturat, 0) AS facturat,
        COALESCE(c_plati.platit, 0) AS platit,
        (COALESCE(c_facturi.facturat, 0) - COALESCE(c_plati.platit, 0)) AS sold
    FROM ids
    LEFT JOIN c_lucrari ON c_lucrari.client_id = ids.client_id
    LEFT JOIN c_facturi ON c_facturi.client_id = ids.client_id
    LEFT JOIN c_plati ON c_plati.client_id = ids.client_id
    """

    with closing(_connect()) as conn, conn:
        return _read_frame(q, conn)


def lista_utilizatori() -> pd.DataFrame:
    with closing(_connect()) as conn, conn:
        return _read_frame("""
            SELECT
                id,
                username,
                rol,
                activ,
                must_change_password,
                created_at
            FROM utilizatori
            ORDER BY username ASC
        """, conn)


def get_utilizator(username: str) -> dict | None:
    with closing(_connect()) as conn, conn:
        cur = conn.cursor()
        _execute(cur, """
            SELECT
                id,
                username,
                parola,
                rol,
                activ,
                must_change_password,
                created_at
            FROM utilizatori
            WHERE username=?
        """, (username,))
        row = cur.fetchone()
        return dict(zip([col[0] for col in cur.description], row)) if row else None


def adauga_utilizator(username: str, parola: str, rol: str = "birou", activ: int = 1, must_change_password: int = 1):
    username = str(username or "").strip()
    parola = str(parola or "")

    if not username:
        raise ValueError("Username-ul este obligatoriu.")
    if len(parola) < 8:
        raise ValueError("Parola trebuie sa aiba minimum 8 caractere.")
    if rol not in {"admin", "birou", "vizualizare"}:
        raise ValueError("Rol invalid.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT id FROM utilizatori WHERE username=?", (username,))
        if c.fetchone():
            raise ValueError("Există deja un utilizator cu acest username.")

        _execute(c, """
            INSERT INTO utilizatori (username, parola, rol, activ, must_change_password, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            username,
            hash_password(parola),
            str(rol or "birou"),
            int(1 if activ else 0),
            int(1 if must_change_password else 0),
            str(datetime.datetime.now()),
        ))
        conn.commit()


def schimba_parola(username: str, parola_veche: str, parola_noua: str):
    username = str(username or "").strip()
    parola_noua = str(parola_noua or "")

    if not username:
        raise ValueError("Username invalid.")
    if len(parola_noua) < 8:
        raise ValueError("Parola noua trebuie sa aiba minimum 8 caractere.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT parola FROM utilizatori WHERE username=?", (username,))
        row = c.fetchone()
        if not row:
            raise ValueError("Utilizatorul nu există.")

        stored_password = row[0]
        if not verify_password(str(parola_veche or ""), stored_password):
            raise ValueError("Parola veche este incorectă.")

        _execute(c, """
            UPDATE utilizatori
            SET parola=?, must_change_password=0
            WHERE username=?
        """, (
            hash_password(parola_noua),
            username,
        ))
        conn.commit()


def reseteaza_parola_admin(username: str, parola_noua: str, must_change_password: int = 1):
    username = str(username or "").strip()
    parola_noua = str(parola_noua or "")

    if not username:
        raise ValueError("Username invalid.")
    if len(parola_noua) < 8:
        raise ValueError("Parola noua trebuie sa aiba minimum 8 caractere.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        _execute(c, """
            UPDATE utilizatori
            SET parola=?, must_change_password=?
            WHERE username=?
        """, (
            hash_password(parola_noua),
            int(1 if must_change_password else 0),
            username,
        ))
        conn.commit()


def seteaza_rol_utilizator(username: str, rol: str):
    username = str(username or "").strip()
    rol = str(rol or "").strip()

    if not username:
        raise ValueError("Username invalid.")
    if rol not in {"admin", "birou", "vizualizare"}:
        raise ValueError("Rol invalid.")
    if username.lower() == "admin" and rol != "admin":
        raise ValueError("Contul admin trebuie sa pastreze rolul admin.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        _execute(c, "UPDATE utilizatori SET rol=? WHERE username=?", (rol, username))
        conn.commit()


def seteaza_activ_utilizator(username: str, activ: int):
    username = str(username or "").strip()
    if username.lower() == "admin" and not activ:
        raise ValueError("Contul admin nu poate fi dezactivat.")

    if not username:
        raise ValueError("Username invalid.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        _execute(c, "UPDATE utilizatori SET activ=? WHERE username=?", (int(1 if activ else 0), username))
        conn.commit()


def sterge_utilizator(username: str):
    username = str(username or "").strip()

    if not username:
        raise ValueError("Username invalid.")
    if username.lower() == "admin":
        raise ValueError("Utilizatorul admin nu poate fi șters.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "DELETE FROM utilizatori WHERE username=?", (username,))
        conn.commit()


def seteaza_must_change_password(username: str, must_change_password: int):
    username = str(username or "").strip()

    if not username:
        raise ValueError("Username invalid.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        _execute(c,
            "UPDATE utilizatori SET must_change_password=? WHERE username=?",
            (int(1 if must_change_password else 0), username),
        )
        conn.commit()


def schimba_parola_fara_verificare_admin(username: str, parola_noua: str, must_change_password: int = 0):
    username = str(username or "").strip()
    parola_noua = str(parola_noua or "")

    if not username:
        raise ValueError("Username invalid.")
    if len(parola_noua) < 8:
        raise ValueError("Parola noua trebuie sa aiba minimum 8 caractere.")

    with closing(_connect()) as conn, conn:
        c = conn.cursor()
        _execute(c, "SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        _execute(c, """
            UPDATE utilizatori
            SET parola=?, must_change_password=?
            WHERE username=?
        """, (
            hash_password(parola_noua),
            int(1 if must_change_password else 0),
            username,
        ))
        conn.commit()


# Enforce application permissions before any mutation, including stale forms.
from db.permissions import protect_functions as _protect_functions
_protect_functions(globals())
