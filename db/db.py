import sqlite3
import datetime
import pandas as pd
import os

DB_PATH = "manager_clienti_modern.db"

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        # !!! ATENȚIE: adaugă aici și noile coloane la creare, dacă vrei să folosești funcția asta!
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
        # ... celelalte create table rămân la fel ...
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
        conn.commit()

def login(user, pwd):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT * FROM utilizatori WHERE username=? AND parola=?", (user, pwd))
        return c.fetchone()

# ----------- CLIENTI (cu JUDET) ------------

def adauga_client(valori):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO clienti (
                nume, email, telefon, firma, status, observatii, data_adaugarii, cod_intern, scor, remark,
                domiciliu_judet, domiciliu_localitate, domiciliu_strada, domiciliu_numar, domiciliu_bloc, domiciliu_apartament,
                consum_judet, consum_localitate, consum_strada, consum_numar, consum_bloc, consum_apartament
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            valori.get("nume", ""), valori.get("email", ""), valori.get("telefon", ""), valori.get("firma", ""),
            valori.get("status", ""), valori.get("observatii", ""), str(datetime.datetime.now()), valori.get("cod_intern", ""),
            valori.get("scor", 0), valori.get("remark", ""),
            valori.get("domiciliu_judet", ""),
            valori.get("domiciliu_localitate", ""), valori.get("domiciliu_strada", ""), valori.get("domiciliu_numar", ""),
            valori.get("domiciliu_bloc", ""), valori.get("domiciliu_apartament", ""),
            valori.get("consum_judet", ""),
            valori.get("consum_localitate", ""), valori.get("consum_strada", ""), valori.get("consum_numar", ""),
            valori.get("consum_bloc", ""), valori.get("consum_apartament", "")
        ])
        conn.commit()

def lista_clienti(filtru=""):
    with sqlite3.connect(DB_PATH) as conn:
        if filtru:
            df = pd.read_sql_query(
                "SELECT * FROM clienti WHERE nume LIKE ? OR email LIKE ? ORDER BY data_adaugarii DESC, id DESC",
                conn, params=[f"%{filtru}%", f"%{filtru}%"]
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM clienti ORDER BY data_adaugarii DESC, id DESC", conn
            )
        return df

def modifica_client(id_cli, valori):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""UPDATE clienti SET 
            nume=?, email=?, telefon=?, firma=?, status=?, observatii=?, cod_intern=?, scor=?, remark=?,
            domiciliu_judet=?, domiciliu_localitate=?, domiciliu_strada=?, domiciliu_numar=?, domiciliu_bloc=?, domiciliu_apartament=?,
            consum_judet=?, consum_localitate=?, consum_strada=?, consum_numar=?, consum_bloc=?, consum_apartament=?
            WHERE id=?""",
            [
                valori.get("nume", ""), valori.get("email", ""), valori.get("telefon", ""), valori.get("firma", ""),
                valori.get("status", ""), valori.get("observatii", ""), valori.get("cod_intern", ""),
                valori.get("scor", 0), valori.get("remark", ""),
                valori.get("domiciliu_judet", ""),
                valori.get("domiciliu_localitate", ""), valori.get("domiciliu_strada", ""), valori.get("domiciliu_numar", ""),
                valori.get("domiciliu_bloc", ""), valori.get("domiciliu_apartament", ""),
                valori.get("consum_judet", ""),
                valori.get("consum_localitate", ""), valori.get("consum_strada", ""), valori.get("consum_numar", ""),
                valori.get("consum_bloc", ""), valori.get("consum_apartament", ""),
                id_cli
            ])
        conn.commit()

def sterge_client(id_cli):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM clienti WHERE id=?", (id_cli,))
        conn.commit()

# ----------- restul funcțiilor rămân la fel ------------

def lista_atasamente(client_id):
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query(
            "SELECT * FROM atasamente WHERE client_id=? ORDER BY upload_date DESC, id DESC",
            conn, params=[client_id]
        )
        return df

def save_atasament(client_id, filename, uploaded_by, content_bytes):
    upload_dir = os.path.join("uploads", str(client_id))
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(content_bytes)
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute(
            "INSERT INTO atasamente (client_id, filename, path, uploaded_by, upload_date) VALUES (?, ?, ?, ?, ?)",
            (client_id, filename, filepath, uploaded_by, str(datetime.datetime.now()))
        )
        conn.commit()

def sterge_atasament(atas_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("SELECT path FROM atasamente WHERE id=?", (atas_id,))
        row = c.fetchone()
        if row and row[0] and os.path.exists(row[0]):
            os.remove(row[0])
        c.execute("DELETE FROM atasamente WHERE id=?", (atas_id,))
        conn.commit()

def adauga_lucrare(valori):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            INSERT INTO lucrari (
                client_id, tip_lucrare, valoare_contractata, responsabil,
                status, data_contract, data_programare, observatii, descriere
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, [
            valori["client_id"], valori["tip_lucrare"], valori["valoare_contractata"],
            valori["responsabil"], valori["status"], valori["data_contract"], valori["data_programare"],
            valori.get("observatii", ""), valori.get("descriere", "")
        ])
        conn.commit()

def lista_lucrari():
    with sqlite3.connect(DB_PATH) as conn:
        df = pd.read_sql_query("SELECT * FROM lucrari ORDER BY data_contract DESC, id DESC", conn)
        return df

def modifica_lucrare(lucrare_id, valori):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("""
            UPDATE lucrari SET client_id=?, tip_lucrare=?, valoare_contractata=?, responsabil=?,
                status=?, data_contract=?, data_programare=?, observatii=?, descriere=?
            WHERE id=?
        """, [
            valori["client_id"], valori["tip_lucrare"], valori["valoare_contractata"], valori["responsabil"],
            valori["status"], valori["data_contract"], valori["data_programare"],
            valori.get("observatii", ""), valori.get("descriere", ""), lucrare_id
        ])
        conn.commit()

def sterge_lucrare(lucrare_id):
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM lucrari WHERE id=?", (lucrare_id,))
        conn.commit()