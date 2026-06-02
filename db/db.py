import sqlite3
import datetime
import os
import hashlib
import hmac
import secrets
import pandas as pd

DB_PATH = os.getenv("DB_PATH", "manager_clienti_modern.db")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin")
PBKDF2_ITERATIONS = 600_000


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
    cur.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cur.fetchall()}


def _add_column_if_missing(conn: sqlite3.Connection, table_name: str, col_name: str, col_type: str):
    cols = _table_columns(conn, table_name)
    if col_name in cols:
        return
    cur = conn.cursor()
    cur.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")


def _migrate_schema(conn: sqlite3.Connection):
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS documente_seq (
            an INTEGER PRIMARY KEY,
            last_os INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS contracte_seq (
            an INTEGER PRIMARY KEY,
            last_ctr INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS registru_seq_client (
            client_id INTEGER PRIMARY KEY,
            last_nr INTEGER NOT NULL DEFAULT 0
        )
    """)

    cur.execute("""
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

    cur.execute("""
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

    cur.execute("UPDATE utilizatori SET rol='birou' WHERE rol IS NULL OR TRIM(rol)=''")
    cur.execute("UPDATE utilizatori SET activ=1 WHERE activ IS NULL")
    cur.execute("UPDATE utilizatori SET must_change_password=0 WHERE must_change_password IS NULL")
    cur.execute("UPDATE utilizatori SET rol='admin' WHERE username='admin'")

    conn.commit()


def init_db():
    _ensure_parent_dir(DB_PATH)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("""
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

        c.execute("""
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

        c.execute("""
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

        c.execute("""
            CREATE TABLE IF NOT EXISTS atasamente (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER NOT NULL,
                filename TEXT NOT NULL,
                path TEXT NOT NULL,
                uploaded_by TEXT,
                upload_date TEXT
            )
        """)

        c.execute("""
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

        c.execute("""
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

        c.execute("SELECT COUNT(*) FROM utilizatori")
        if c.fetchone()[0] == 0:
            c.execute(
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
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
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


def genereaza_nr_os(an: int | None = None) -> str:
    if an is None:
        an = datetime.datetime.now().year

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT last_os FROM documente_seq WHERE an=?", (int(an),))
        row = cur.fetchone()
        if row is None:
            last = 0
            cur.execute("INSERT INTO documente_seq (an, last_os) VALUES (?, ?)", (int(an), 0))
        else:
            last = int(row[0] or 0)

        new_val = last + 1
        cur.execute("UPDATE documente_seq SET last_os=? WHERE an=?", (new_val, int(an)))
        conn.commit()

    return f"OS-{int(an)}-{new_val:04d}"


def genereaza_nr_contract(an: int | None = None) -> str:
    if an is None:
        an = datetime.datetime.now().year

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT last_ctr FROM contracte_seq WHERE an=?", (int(an),))
        row = cur.fetchone()

        if row is None:
            last = 0
            cur.execute("INSERT INTO contracte_seq (an, last_ctr) VALUES (?, ?)", (int(an), 0))
        else:
            last = int(row[0] or 0)

        new_val = last + 1
        cur.execute("UPDATE contracte_seq SET last_ctr=? WHERE an=?", (new_val, int(an)))
        conn.commit()

    return f"CTR-{int(an)}-{new_val:04d}"


def genereaza_nr_inregistrare_client(client_id: int, an: int | None = None) -> str:
    if an is None:
        an = datetime.datetime.now().year

    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE")
        cur.execute("SELECT last_nr FROM registru_seq_client WHERE client_id=?", (int(client_id),))
        row = cur.fetchone()
        if row is None:
            last = 0
            cur.execute("INSERT INTO registru_seq_client (client_id, last_nr) VALUES (?, ?)", (int(client_id), 0))
        else:
            last = int(row[0] or 0)

        new_val = last + 1
        cur.execute("UPDATE registru_seq_client SET last_nr=? WHERE client_id=?", (new_val, int(client_id)))
        conn.commit()

    return f"REG-{int(client_id)}-{int(an)}-{new_val:04d}"


def adauga_inregistrare(client_id: int, lucrare_id: int, sarcina_id: int | None, descriere: str, created_by: str) -> str:
    nr = genereaza_nr_inregistrare_client(int(client_id))
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
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

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(q, conn, params=params)


def adauga_client(valori: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
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
    with sqlite3.connect(DB_PATH) as conn:
        if filtru:
            return pd.read_sql_query(
                "SELECT * FROM clienti WHERE nume LIKE ? OR email LIKE ? ORDER BY data_adaugarii DESC, id DESC",
                conn, params=[f"%{filtru}%", f"%{filtru}%"]
            )
        return pd.read_sql_query("SELECT * FROM clienti ORDER BY data_adaugarii DESC, id DESC", conn)


def modifica_client(id_cli: int, valori: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""UPDATE clienti SET 
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

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM lucrari WHERE client_id=?", (client_id,))
        nr_lucrari = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM facturi WHERE client_id=?", (client_id,))
        nr_facturi = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM plati WHERE client_id=?", (client_id,))
        nr_plati = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM atasamente WHERE client_id=?", (client_id,))
        nr_atasamente = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM inregistrari WHERE client_id=?", (client_id,))
        nr_inregistrari = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM sarcini WHERE client_id=?", (client_id,))
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

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM clienti WHERE id=?", (client_id,))
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

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(q, conn, params=params)


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
    upload_dir = os.path.join(UPLOAD_DIR, str(int(client_id)))
    os.makedirs(upload_dir, exist_ok=True)

    filepath, final_filename = _unique_filepath(upload_dir, filename)

    with open(filepath, "wb") as f:
        f.write(content_bytes)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
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
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT path FROM atasamente WHERE id=?", (int(atas_id),))
        row = c.fetchone()
        if row and row[0] and os.path.exists(row[0]):
            try:
                os.remove(row[0])
            except Exception:
                pass
        c.execute("DELETE FROM atasamente WHERE id=?", (int(atas_id),))
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
    c = conn.cursor()
    steps = flux_sarcini_pentru_tip_lucrare(tip_lucrare)
    now = str(datetime.datetime.now())
    for i, tip in enumerate(steps, start=1):
        c.execute("""
            INSERT INTO sarcini (client_id, lucrare_id, ordine, tip_sarcina, status, created_at, created_by)
            VALUES (?, ?, ?, ?, 'NOU', ?, ?)
        """, (int(client_id), int(lucrare_id), int(i), str(tip), now, created_by or ""))


def adauga_lucrare(valori: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO lucrari (
                client_id, tip_lucrare, valoare_contractata, avans, responsabil,
                status, data_contract, data_programare, observatii, descriere,
                adresa_judet, adresa_localitate, adresa_strada, adresa_numar, adresa_bloc, adresa_apartament,
                interval_orar, echipa, sef_echipa,
                cod_atr, executant, element_sda, comanda_aprovizionare,
                diriginte_santier, contract_prestari_servicii, numar_conventie_tehnica,
                data_programare_pif, interval_orar_pif, echipa_pif, sef_echipa_pif
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
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
        ))

        lucrare_id = int(c.lastrowid)
        _creeaza_flux_birou_pentru_lucrare(
            conn=conn,
            client_id=int(valori["client_id"]),
            lucrare_id=lucrare_id,
            tip_lucrare=str(valori.get("tip_lucrare", "")),
            created_by=str(valori.get("created_by", "")),
        )

        conn.commit()


def lista_lucrari() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM lucrari ORDER BY data_contract DESC, id DESC", conn)


def lista_lucrari_client(client_id: int) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT * FROM lucrari WHERE client_id=? ORDER BY data_contract DESC, id DESC",
            conn,
            params=[int(client_id)],
        )


def get_lucrare(lucrare_id: int) -> dict | None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM lucrari WHERE id=?", (int(lucrare_id),))
        row = cur.fetchone()
        return dict(row) if row else None


def modifica_lucrare(lucrare_id: int, valori: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE lucrari SET
                client_id=?, tip_lucrare=?, valoare_contractata=?, avans=?, responsabil=?,
                status=?, data_contract=?, data_programare=?, observatii=?, descriere=?,
                adresa_judet=?, adresa_localitate=?, adresa_strada=?, adresa_numar=?, adresa_bloc=?, adresa_apartament=?,
                interval_orar=?, echipa=?, sef_echipa=?,
                cod_atr=?, executant=?, element_sda=?, comanda_aprovizionare=?,
                diriginte_santier=?, contract_prestari_servicii=?, numar_conventie_tehnica=?,
                data_programare_pif=?, interval_orar_pif=?, echipa_pif=?, sef_echipa_pif=?
            WHERE id=?
        """, (
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
            int(lucrare_id),
        ))
        conn.commit()


def dependinte_lucrare(lucrare_id: int) -> dict:
    lid = int(lucrare_id)

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT COUNT(*) FROM sarcini WHERE lucrare_id=?", (lid,))
        nr_sarcini = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM inregistrari WHERE lucrare_id=?", (lid,))
        nr_inregistrari = int(c.fetchone()[0] or 0)

        c.execute("SELECT COUNT(*) FROM atasamente WHERE lucrare_id=?", (lid,))
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

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM lucrari WHERE id=?", (lid,))
        conn.commit()


def lista_sarcini_lucrare(lucrare_id: int) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
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

    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(q, conn, params=params)


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

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(f"UPDATE sarcini SET {', '.join(fields)} WHERE id=?", params)
        conn.commit()


def lista_facturi(client_id: int) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT * FROM facturi WHERE client_id=? ORDER BY data_emiterii DESC, id DESC",
            conn,
            params=[int(client_id)],
        )


def adauga_factura(valori: dict):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO facturi (
                client_id, numar, data_emiterii, data_scadenta, total, moneda, status,
                observatii, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(valori["client_id"]),
            valori.get("numar", ""),
            valori.get("data_emiterii", ""),
            valori.get("data_scadenta", ""),
            float(valori.get("total", 0) or 0),
            valori.get("moneda", "RON"),
            valori.get("status", "NEINCASATA"),
            valori.get("observatii", ""),
            str(datetime.datetime.now()),
            valori.get("created_by", ""),
        ))
        conn.commit()


def anuleaza_factura(factura_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("UPDATE facturi SET status='ANULATA' WHERE id=?", (int(factura_id),))
        conn.commit()


def sterge_factura(factura_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM plati WHERE factura_id=?", (int(factura_id),))
        c.execute("DELETE FROM facturi WHERE id=?", (int(factura_id),))
        conn.commit()


def lista_plati(client_id: int) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query(
            "SELECT * FROM plati WHERE client_id=? ORDER BY data_platii DESC, id DESC",
            conn,
            params=[int(client_id)],
        )


def recalculeaza_status_factura(factura_id: int):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT COALESCE(total, 0), status FROM facturi WHERE id=?", (int(factura_id),))
        row = c.fetchone()
        if not row:
            return
        total, status_curent = float(row[0] or 0), str(row[1] or "NEINCASATA")

        if status_curent == "ANULATA":
            return

        c.execute("SELECT COALESCE(SUM(suma), 0) FROM plati WHERE factura_id=?", (int(factura_id),))
        incasat = float(c.fetchone()[0] or 0)

        if total <= 0:
            status_nou = "NEINCASATA"
        elif incasat <= 0:
            status_nou = "NEINCASATA"
        elif incasat + 1e-9 < total:
            status_nou = "PARTIAL"
        else:
            status_nou = "INCASATA"

        c.execute("UPDATE facturi SET status=? WHERE id=?", (status_nou, int(factura_id)))
        conn.commit()


def adauga_plata(valori: dict):
    factura_id = valori.get("factura_id", None)
    if factura_id is None:
        raise ValueError("factura_id este obligatoriu pentru o plată.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("SELECT status FROM facturi WHERE id=?", (int(factura_id),))
        row = c.fetchone()
        if not row:
            raise ValueError("Factura nu există.")
        if str(row[0]) == "ANULATA":
            raise ValueError("Nu poți adăuga plată pe o factură ANULATĂ.")

        c.execute("""
            INSERT INTO plati (
                client_id, factura_id, data_platii, suma, metoda, observatii, created_at, created_by
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            int(valori["client_id"]),
            int(factura_id),
            valori.get("data_platii", ""),
            float(valori.get("suma", 0) or 0),
            valori.get("metoda", ""),
            valori.get("observatii", ""),
            str(datetime.datetime.now()),
            valori.get("created_by", ""),
        ))
        conn.commit()

    recalculeaza_status_factura(int(factura_id))


def sterge_plata(plata_id: int):
    factura_id = None
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT factura_id FROM plati WHERE id=?", (int(plata_id),))
        row = c.fetchone()
        if row:
            factura_id = row[0]
        c.execute("DELETE FROM plati WHERE id=?", (int(plata_id),))
        conn.commit()

    if factura_id is not None:
        recalculeaza_status_factura(int(factura_id))


def rezumat_facturi_client(client_id: int) -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("""
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
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT COALESCE(SUM(total), 0) FROM facturi WHERE client_id=? AND status!='ANULATA'", (int(client_id),))
        total_facturi = float(c.fetchone()[0] or 0)
        c.execute("SELECT COALESCE(SUM(suma), 0) FROM plati WHERE client_id=?", (int(client_id),))
        total_plati = float(c.fetchone()[0] or 0)
        return total_facturi - total_plati


def solduri_pe_clienti() -> dict:
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()

        c.execute("""
            SELECT client_id, COALESCE(SUM(total), 0)
            FROM facturi
            WHERE status != 'ANULATA'
            GROUP BY client_id
        """)
        facturi = {int(cid): float(total or 0) for cid, total in c.fetchall()}

        c.execute("""
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
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            SELECT client_id, COALESCE(SUM(total), 0)
            FROM facturi
            WHERE status != 'ANULATA'
            GROUP BY client_id
        """)
        return {int(cid): float(total or 0) for cid, total in c.fetchall()}


def lista_utilizatori() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("""
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
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
        return dict(row) if row else None


def adauga_utilizator(username: str, parola: str, rol: str = "birou", activ: int = 1, must_change_password: int = 1):
    username = str(username or "").strip()
    parola = str(parola or "")

    if not username:
        raise ValueError("Username-ul este obligatoriu.")
    if not parola:
        raise ValueError("Parola este obligatorie.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM utilizatori WHERE username=?", (username,))
        if c.fetchone():
            raise ValueError("Există deja un utilizator cu acest username.")

        c.execute("""
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
    if not parola_noua:
        raise ValueError("Parola nouă este obligatorie.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT parola FROM utilizatori WHERE username=?", (username,))
        row = c.fetchone()
        if not row:
            raise ValueError("Utilizatorul nu există.")

        stored_password = row[0]
        if not verify_password(str(parola_veche or ""), stored_password):
            raise ValueError("Parola veche este incorectă.")

        c.execute("""
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
    if not parola_noua:
        raise ValueError("Parola nouă este obligatorie.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        c.execute("""
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
    if not rol:
        raise ValueError("Rolul este obligatoriu.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        c.execute("UPDATE utilizatori SET rol=? WHERE username=?", (rol, username))
        conn.commit()


def seteaza_activ_utilizator(username: str, activ: int):
    username = str(username or "").strip()

    if not username:
        raise ValueError("Username invalid.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        c.execute("UPDATE utilizatori SET activ=? WHERE username=?", (int(1 if activ else 0), username))
        conn.commit()


def sterge_utilizator(username: str):
    username = str(username or "").strip()

    if not username:
        raise ValueError("Username invalid.")
    if username.lower() == "admin":
        raise ValueError("Utilizatorul admin nu poate fi șters.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM utilizatori WHERE username=?", (username,))
        conn.commit()


def seteaza_must_change_password(username: str, must_change_password: int):
    username = str(username or "").strip()

    if not username:
        raise ValueError("Username invalid.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        c.execute(
            "UPDATE utilizatori SET must_change_password=? WHERE username=?",
            (int(1 if must_change_password else 0), username),
        )
        conn.commit()


def schimba_parola_fara_verificare_admin(username: str, parola_noua: str, must_change_password: int = 0):
    username = str(username or "").strip()
    parola_noua = str(parola_noua or "")

    if not username:
        raise ValueError("Username invalid.")
    if not parola_noua:
        raise ValueError("Parola nouă este obligatorie.")

    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT id FROM utilizatori WHERE username=?", (username,))
        if not c.fetchone():
            raise ValueError("Utilizatorul nu există.")

        c.execute("""
            UPDATE utilizatori
            SET parola=?, must_change_password=?
            WHERE username=?
        """, (
            hash_password(parola_noua),
            int(1 if must_change_password else 0),
            username,
        ))
        conn.commit()