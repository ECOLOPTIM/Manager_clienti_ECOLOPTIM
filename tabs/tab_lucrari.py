import streamlit as st
import db.db as db
import pandas as pd
import io

STATUS_COLORS = {
    "OFERTAT": ("🟡", "#e6b800"),
    "PROGRAMAT": ("🟣", "#a259d9"),
    "CONTRACTAT": ("🟢", "#6bc000"),
    "EXECUTAT": ("🔵", "#0090ff"),
    "FINALIZAT": ("⚪", "#b0b0b0"),
    "ÎNCHIS": ("🔴", "#d01a1a"),
}

def status_display(status):
    emoji, color = STATUS_COLORS.get(str(status).upper(), ("⚪", "#b0b0b0"))
    # Bulina mică + text normal, ambele aliniate
    return f"<span style='color:{color}; font-size:14px; vertical-align:middle;'>{emoji}</span> <span style='vertical-align:middle;'>{str(status)}</span>"

# ... cod inițial de import și setup ...

def show(user):
    st.header("📊 RAPORT LUCRĂRI – Toți clienții")

    clienti = db.lista_clienti()
    lucrari = db.lista_lucrari()

    df = lucrari.merge(
        clienti[["id", "nume"]],
        left_on="client_id", right_on="id", how="left", suffixes=("", "_client")
    )
    df = df.rename(columns={
        "nume": "Client",
        "tip_lucrare": "Tip lucrare",
        "valoare_contractata": "Valoare (RON cu TVA)",
        "status": "Status",
        "observatii": "Observații"
    })

    # ---- FILTRE ----
    col1, col2, col3, col4, col5 = st.columns([2,2,2,2,2])
    clienti_nume = sorted(df["Client"].dropna().unique().tolist())
    tipuri = sorted(set(df["Tip lucrare"].dropna().unique().tolist() + ["Bransament AR", "Proiect IUGN"]))
    statusuri = sorted(df["Status"].dropna().unique().tolist())

    filtr_client = col1.selectbox("Client", ["Toți"] + clienti_nume, key="raport_client")
    filtr_tip = col2.selectbox("Tip lucrare", ["Toate"] + tipuri, key="raport_tip")
    filtr_status = col3.selectbox("Status", ["Toate"] + statusuri, key="raport_status")
    min_valoare = int(df["Valoare (RON cu TVA)"].min()) if not df.empty else 0
    max_valoare = int(df["Valoare (RON cu TVA)"].max()) if not df.empty else 10000
    filtru_suma = col4.slider("Interval valoare (RON cu TVA)", min_value=min_valoare, max_value=max_valoare, value=(min_valoare, max_valoare), step=100)
    filtru_cauta = col5.text_input("Căutare rapidă", key="raport_search")

    filtru_df = df.copy()
    if filtr_client != "Toți":
        filtru_df = filtru_df[filtru_df["Client"] == filtr_client]
    if filtr_tip != "Toate":
        filtru_df = filtru_df[filtru_df["Tip lucrare"] == filtr_tip]
    if filtr_status != "Toate":
        filtru_df = filtru_df[filtru_df["Status"] == filtr_status]
    filtru_df = filtru_df[(filtru_df["Valoare (RON cu TVA)"] >= filtru_suma[0]) & (filtru_df["Valoare (RON cu TVA)"] <= filtru_suma[1])]
    if filtru_cauta:
        mask = filtru_df.apply(lambda x: filtru_cauta.lower() in str(x).lower(), axis=1)
        filtru_df = filtru_df[mask]

    st.markdown(f"#### {len(filtru_df)} lucrări găsite")
    viz_cols = [
        "Client", "Tip lucrare", "Valoare (RON cu TVA)", "Status",
        "data_contract", "data_programare", "responsabil", "Observații", "descriere"
    ]
    viz_cols = [c for c in viz_cols if c in filtru_df.columns]

    # ---- TABEL COLORAT ----
    df_display = filtru_df.copy()
    if "Status" in df_display.columns:
        df_display["Status"] = df_display["Status"].apply(status_display)
    st.write(df_display[viz_cols].to_html(escape=False, index=False), unsafe_allow_html=True)

    # SUMĂ TOTALĂ
    if not filtru_df.empty:
        suma_total = filtru_df["Valoare (RON cu TVA)"].sum()
        st.success(f"Suma totală a lucrărilor: {suma_total:,.2f} RON cu TVA")

    # ----- EXPORT -----
    buffer = io.BytesIO()
    filtru_df[viz_cols].to_excel(buffer, index=False)
    buffer.seek(0)
    st.download_button(
        "💾 Export Excel",
        data=buffer,
        file_name="Raport_lucrari.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="export_rap_lucrari_xls"
    )
    st.download_button(
        "💾 Export CSV",
        data=filtru_df[viz_cols].to_csv(index=False).encode('utf-8'),
        file_name="Raport_lucrari.csv",
        mime="text/csv",
        key="export_rap_lucrari_csv"
    )