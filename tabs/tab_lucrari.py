import streamlit as st
import db.db as db
import pandas as pd
import io


def status_badge(status: str) -> str:
    s = str(status or "").upper().strip()
    if s == "PROGRAMAT":
        return "<span class='badge badge-in'>PROGRAMAT</span>"
    if s == "CONTRACTAT":
        return "<span class='badge badge-fin'>CONTRACTAT</span>"
    if s == "EXECUTAT":
        return "<span class='badge badge-in'>EXECUTAT</span>"
    if s == "FINALIZAT":
        return "<span class='badge badge-fin'>FINALIZAT</span>"
    if s == "ÎNCHIS" or s == "INCHIS":
        return "<span class='badge badge-bl'>ÎNCHIS</span>"
    return "<span class='badge badge-nou'>OFERTAT</span>"


def show(user):
    st.header("📊 RAPORT LUCRĂRI – Toți clienții")

    clienti = db.lista_clienti()
    lucrari = db.lista_lucrari()

    if lucrari is None or lucrari.empty:
        st.info("Nu există lucrări.")
        return

    df = lucrari.copy()

    if clienti is not None and not clienti.empty:
        df = df.merge(
            clienti[["id", "nume"]],
            left_on="client_id",
            right_on="id",
            how="left",
            suffixes=("", "_client"),
        )
        df = df.rename(columns={"nume": "Client"})

    df = df.rename(
        columns={
            "tip_lucrare": "Tip lucrare",
            "valoare_contractata": "Valoare (RON cu TVA)",
            "status": "Status",
            "observatii": "Observații",
        }
    )

    # ---------------- Filter bar ----------------
    if "lucrari_filters_reset" not in st.session_state:
        st.session_state["lucrari_filters_reset"] = 0
    rid = st.session_state["lucrari_filters_reset"]

    st.markdown("<div class='eco-filters'>", unsafe_allow_html=True)
    col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 2, 1.7, 2.4, 2.4, 2.2, 1.1])

    clienti_nume = sorted(df["Client"].dropna().unique().tolist()) if "Client" in df.columns else []
    tipuri = sorted(df["Tip lucrare"].dropna().unique().tolist()) if "Tip lucrare" in df.columns else []
    statusuri = sorted(df["Status"].dropna().unique().tolist()) if "Status" in df.columns else []
    echipe = sorted(df["echipa"].dropna().astype(str).unique().tolist()) if "echipa" in df.columns else []

    filtr_client = col1.selectbox("Client", ["Toți"] + clienti_nume, key=f"raport_client_{rid}")
    filtr_tip = col2.multiselect("Tip lucrare", tipuri, default=[], key=f"raport_tip_{rid}")
    filtr_status = col3.selectbox("Status", ["Toate"] + statusuri, key=f"raport_status_{rid}")
    filtr_echipa = col4.selectbox("Echipă", ["Toate"] + echipe, key=f"raport_echipa_{rid}")

    min_valoare = int(df["Valoare (RON cu TVA)"].min()) if "Valoare (RON cu TVA)" in df.columns else 0
    max_valoare = int(df["Valoare (RON cu TVA)"].max()) if "Valoare (RON cu TVA)" in df.columns else 10000
    filtru_suma = col5.slider(
        "Interval valoare (RON cu TVA)",
        min_value=min_valoare,
        max_value=max_valoare,
        value=(min_valoare, max_valoare),
        step=100,
        key=f"raport_suma_{rid}",
    )
    filtru_cauta = col6.text_input("Căutare", key=f"raport_search_{rid}")

    if col7.button("Reset", key=f"raport_reset_{rid}"):
        st.session_state["lucrari_filters_reset"] += 1
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    filtru_df = df.copy()
    if filtr_client != "Toți":
        filtru_df = filtru_df[filtru_df["Client"] == filtr_client]
    if filtr_tip:
        filtru_df = filtru_df[filtru_df["Tip lucrare"].isin(filtr_tip)]
    if filtr_status != "Toate":
        filtru_df = filtru_df[filtru_df["Status"] == filtr_status]
    if filtr_echipa != "Toate" and "echipa" in filtru_df.columns:
        filtru_df = filtru_df[filtru_df["echipa"].astype(str) == filtr_echipa]

    if "Valoare (RON cu TVA)" in filtru_df.columns:
        filtru_df = filtru_df[
            (filtru_df["Valoare (RON cu TVA)"] >= filtru_suma[0])
            & (filtru_df["Valoare (RON cu TVA)"] <= filtru_suma[1])
        ]

    if filtru_cauta:
        t = filtru_cauta.lower().strip()
        mask = filtru_df.apply(lambda x: t in str(x).lower(), axis=1)
        filtru_df = filtru_df[mask]

    if filtru_df.empty:
        st.info("Nu există lucrări pentru filtrele selectate.")
        return

    # NR (id-ul lucrării)
    filtru_df = filtru_df.copy()
    if "id" in filtru_df.columns and "NR" not in filtru_df.columns:
        filtru_df.insert(0, "NR", filtru_df["id"].astype(int))

    st.markdown(f"#### {len(filtru_df)} lucrări găsite")

    viz_cols = [
        "NR",
        "Client",
        "Tip lucrare",
        "Valoare (RON cu TVA)",
        "Status",
        "data_contract",
        "data_programare",
        "responsabil",
        "echipa",
        "Observații",
        "descriere",
    ]
    viz_cols = [c for c in viz_cols if c in filtru_df.columns]

    df_display = filtru_df.copy()
    if "Status" in df_display.columns:
        df_display["Status"] = df_display["Status"].apply(status_badge)

    st.markdown(df_display[viz_cols].to_html(escape=False, index=False, classes="eco-table"), unsafe_allow_html=True)

    if not filtru_df.empty and "Valoare (RON cu TVA)" in filtru_df.columns:
        suma_total = filtru_df["Valoare (RON cu TVA)"].sum()
        st.success(f"Suma totală a lucrărilor: {suma_total:,.2f} RON cu TVA")

    # Export
    buffer = io.BytesIO()
    filtru_df[viz_cols].to_excel(buffer, index=False)
    buffer.seek(0)

    ex = st.columns(2)
    ex[0].download_button(
        "💾 Export Excel",
        data=buffer,
        file_name="Raport_lucrari.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="export_rap_lucrari_xls",
    )
    ex[1].download_button(
        "💾 Export CSV",
        data=filtru_df[viz_cols].to_csv(index=False).encode("utf-8"),
        file_name="Raport_lucrari.csv",
        mime="text/csv",
        key="export_rap_lucrari_csv",
    )