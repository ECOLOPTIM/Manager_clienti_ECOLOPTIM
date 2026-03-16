import streamlit as st
import db.db as db
import pandas as pd
import io
from datetime import datetime

TIPURI_LUCRARE = [
    "Instalatie termica noua",
    "Modificare instalatie termica",
    "Instalatie termica in pardoseala",
    "Instalatie sanitara noua",
    "Modificare/reparatie instalatie sanitara",
    "Montaj obiecte sanitare",
    "Instalatie de utilizare noua",
    "Suplimentare debit instalat",
    "Bransament nou prin DGSR",
    "Bransament nou cu OE client",
    "Extindere retea",
    "Extindere retea cu bransament",
    "Montat AC 9-12000",
    "Montat AC 18-24000",
    "Instalatie climatizare complexa",
    "Ventilatie rezidentiala",
    "Ventilatie industriala",
    "Bransament AR",
    "Proiect IUGN"
]
STATUS_OPTIONS = ["OFERTAT", "PROGRAMAT", "CONTRACTAT", "EXECUTAT", "FINALIZAT", "ÎNCHIS"]
RESPONSABILI = ["RESPONSABIL1", "RESPONSABIL2", "RESPONSABIL3", "RESPONSABIL4"]
PREFIX = "lucrari_client_"

def show(user, client_id):
    clienti = db.lista_clienti()
    client = clienti[clienti["id"] == client_id].iloc[0]
    st.header(f"🔨 LUCRĂRI pentru: {client['nume']}")

    df = db.lista_lucrari()
    df = df[df["client_id"] == client_id].copy()

    tipuri_unice = sorted(df["tip_lucrare"].dropna().unique().tolist())
    tip_selectat = st.selectbox("Filtrează după tip lucrare", ["Toate"] + tipuri_unice, key=f"{PREFIX}filtru_tip_{client_id}")
    if tip_selectat != "Toate":
        df = df[df["tip_lucrare"] == tip_selectat]

    PAGE_SIZE = 10
    pagekey = f"{PREFIX}page_{client_id}"
    if pagekey not in st.session_state:
        st.session_state[pagekey] = 1
    total_pages = ((len(df)-1)//PAGE_SIZE)+1 if not df.empty else 1

    nav = st.columns([2,1,2])
    if nav[0].button("⏮️ Pagina anterioară", key=f"{PREFIX}prev_{client_id}"):
        if st.session_state[pagekey] > 1:
            st.session_state[pagekey] -= 1
    nav[1].markdown(f"<div style='text-align:center; font-weight:bold;'>Pagina {st.session_state[pagekey]} din {total_pages}</div>", unsafe_allow_html=True)
    if nav[2].button("Pagina următoare ⏭️", key=f"{PREFIX}next_{client_id}"):
        if st.session_state[pagekey] < total_pages:
            st.session_state[pagekey] += 1
    if st.session_state[pagekey] > total_pages:
        st.session_state[pagekey] = total_pages
    if st.session_state[pagekey] < 1:
        st.session_state[pagekey] = 1

    st.markdown("#### Toate lucrările acestui client")
    if df.empty:
        st.info("Nu există lucrări pentru acest client/filtru.")
    else:
        start, stop = (st.session_state[pagekey]-1)*PAGE_SIZE, (st.session_state[pagekey])*PAGE_SIZE
        df_page = df.iloc[start:stop]
        head = st.columns([3,2,2,2,2,2,1,1])
        header = ["TIP LUCRARE", "STATUS", "RESPONSABIL", "VALOARE (RON cu TVA)", "PERIOADĂ", "OBSERVAȚII", "✏️", "🗑️"]
        for h, txt in zip(head, header):
            h.write(f"**{txt}**")
        for i, row in df_page.iterrows():
            c = st.columns([3,2,2,2,2,2,1,1])
            c[0].write(row["tip_lucrare"])
            c[1].write(row["status"])
            c[2].write(row.get("responsabil", ""))
            val = row.get("valoare_contractata", "")
            val = f"{val:,.2f}" if pd.notnull(val) and val != "" else ""
            c[3].write(val)
            perioada = ""
            if pd.notnull(row.get("data_contract", "")):
                perioada += str(row.get("data_contract", ""))
            if pd.notnull(row.get("data_programare", "")):
                perioada += " → " + str(row.get("data_programare", ""))
            c[4].write(perioada)
            c[5].write(row.get("observatii", ""))
            if c[6].button("✏️", key=f"{PREFIX}edit_{row['id']}"):
                st.session_state[f"{PREFIX}edit_lucrare_id_{client_id}"] = row["id"]
            if c[7].button("🗑️", key=f"{PREFIX}del_{row['id']}"):
                st.session_state[f"{PREFIX}del_lucrare_id_{client_id}"] = row["id"]

    

    # --- ADĂUGARE LUCRARE ---
    if st.button("➕ Adaugă lucrare", key=f"{PREFIX}add_{client_id}"):
        st.session_state[f"{PREFIX}add_open_{client_id}"] = True

    if st.session_state.get(f"{PREFIX}add_open_{client_id}"):
        with st.form(f"{PREFIX}form_add_{client_id}", clear_on_submit=True):
            valori = {}
            tip_sel = st.selectbox("Tip lucrare", TIPURI_LUCRARE, key=f"{PREFIX}add_tip_{client_id}")
            valori["tip_lucrare"] = tip_sel
            valori["valoare_contractata"] = st.number_input("Valoare contractată (RON cu TVA)", min_value=0.0, step=100.0, key=f"{PREFIX}add_val_contract_{client_id}")
            responsabil_sel = st.selectbox("Responsabil", RESPONSABILI, key=f"{PREFIX}add_responsabil_{client_id}")
            valori["responsabil"] = responsabil_sel
            status_sel = st.selectbox("Status", STATUS_OPTIONS, key=f"{PREFIX}add_status_{client_id}")
            valori["status"] = status_sel

            col1, col2 = st.columns(2)
            data_contract = col1.date_input("Dată contract", value=datetime.now().date(), key=f"{PREFIX}add_data_contract_{client_id}")
            data_programare = col2.date_input("Dată programare", value=datetime.now().date(), key=f"{PREFIX}add_data_programare_{client_id}")
            valori["data_contract"] = str(data_contract)
            valori["data_programare"] = str(data_programare)
            valori["observatii"] = st.text_area("Observații", key=f"{PREFIX}add_obs_{client_id}")
            valori["descriere"] = st.text_area("Descriere lucrare", key=f"{PREFIX}add_descriere_{client_id}")
            submit = st.form_submit_button("Salvează lucrarea", key=f"{PREFIX}submit_add_{client_id}")
            if submit:
                valori["client_id"] = client_id
                db.adauga_lucrare(valori)
                st.success("Lucrare adăugată cu succes!")
                st.session_state[f"{PREFIX}add_open_{client_id}"] = False
                st.rerun()

    # --- EDITARE LUCRARE ---
    edit_key = f"{PREFIX}edit_lucrare_id_{client_id}"
    if st.session_state.get(edit_key):
        lucrare_id = st.session_state[edit_key]
        row = df[df["id"] == lucrare_id].iloc[0]
        with st.form(f"{PREFIX}form_edit_{lucrare_id}_{client_id}", clear_on_submit=False):
            valori = {}
            tip_sel = st.selectbox("Tip lucrare", TIPURI_LUCRARE,
                                   index=TIPURI_LUCRARE.index(row["tip_lucrare"]) if row["tip_lucrare"] in TIPURI_LUCRARE else 0,
                                   key=f"{PREFIX}edit_tip_{lucrare_id}_{client_id}")
            valori["tip_lucrare"] = tip_sel
            valori["valoare_contractata"] = st.number_input(
                "Valoare contractată (RON cu TVA)",
                min_value=0.0,
                step=100.0,
                value=float(row.get("valoare_contractata", 0)),
                key=f"{PREFIX}edit_val_contract_{lucrare_id}_{client_id}"
            )
            responsabil_sel = st.selectbox("Responsabil", RESPONSABILI,
                                           index=RESPONSABILI.index(row.get("responsabil", RESPONSABILI[0])),
                                           key=f"{PREFIX}edit_responsabil_{lucrare_id}_{client_id}")
            valori["responsabil"] = responsabil_sel
            status_sel = st.selectbox("Status", STATUS_OPTIONS,
                                      index=STATUS_OPTIONS.index(row["status"]) if row["status"] in STATUS_OPTIONS else 0,
                                      key=f"{PREFIX}edit_status_{lucrare_id}_{client_id}")
            valori["status"] = status_sel

            col1, col2 = st.columns(2)
            data_contract = col1.date_input(
                "Dată contract",
                value=pd.to_datetime(row["data_contract"]).date() if pd.notnull(row["data_contract"]) else datetime.now().date(),
                key=f"{PREFIX}edit_data_contract_{lucrare_id}_{client_id}")
            data_programare = col2.date_input(
                "Dată programare",
                value=pd.to_datetime(row["data_programare"]).date() if pd.notnull(row["data_programare"]) else datetime.now().date(),
                key=f"{PREFIX}edit_data_programare_{lucrare_id}_{client_id}"
            )
            valori["data_contract"] = str(data_contract)
            valori["data_programare"] = str(data_programare)
            valori["observatii"] = st.text_area("Observații", value=row.get("observatii") or "", key=f"{PREFIX}edit_obs_{lucrare_id}_{client_id}")
            valori["descriere"] = st.text_area("Descriere lucrare", value=row.get("descriere") or "", key=f"{PREFIX}edit_descriere_{lucrare_id}_{client_id}")
            submit = st.form_submit_button("Salvează modificările", key=f"{PREFIX}submit_edit_{lucrare_id}_{client_id}")
            valori["client_id"] = client_id
            if submit:
                db.modifica_lucrare(lucrare_id, valori)
                st.success("Modificare salvată.")
                del st.session_state[edit_key]
                st.rerun()
        if st.button("⛔ Închide editarea", key=f"{PREFIX}close_edit_{lucrare_id}_{client_id}"):
            del st.session_state[edit_key]
            st.rerun()

    # --- ȘTERGERE LUCRARE ---
    del_key = f"{PREFIX}del_lucrare_id_{client_id}"
    if st.session_state.get(del_key):
        lucrare_id = st.session_state[del_key]
        row = df[df["id"] == lucrare_id].iloc[0]
        st.error(f"EȘTI SIGUR CĂ VREI SĂ ȘTERGI LUCRAREA '{row['tip_lucrare']}' ({row['data_contract']} → {row['data_programare']})?")
        conf, canc = st.columns([1,1])
        if conf.button("Confirmă ștergerea", key=f"{PREFIX}conf_del_{lucrare_id}_{client_id}"):
            db.sterge_lucrare(lucrare_id)
            st.success("Lucrare ștearsă!")
            del st.session_state[del_key]
            st.rerun()
        if canc.button("Anulează", key=f"{PREFIX}cancel_del_{lucrare_id}_{client_id}"):
            del st.session_state[del_key]
            st.rerun()