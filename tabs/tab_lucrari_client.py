import streamlit as st
import db.db as db

from tabs.components.lucrari_client_components import (
    PREFIX,
    render_lucrari_list,
    render_flux_birou_panel,
    render_add_lucrare_form,
    render_edit_lucrare_form,
    render_delete_lucrare_panel,
)
from tabs.components.iugn_contract_dispatch import render_documente_panel


def _ensure_nr_ordin_for_lucrare(lucrare_id: int) -> str:
    os_nr_key = f"{PREFIX}os_nr_{lucrare_id}"
    nr_ordin = st.session_state.get(os_nr_key, None)
    if not nr_ordin:
        nr_ordin = db.genereaza_nr_os()
        st.session_state[os_nr_key] = nr_ordin
    return nr_ordin


def _ensure_nr_contract_for_lucrare(lucrare_id: int) -> str:
    ctr_nr_key = f"{PREFIX}ctr_nr_{lucrare_id}"
    nr_ctr = st.session_state.get(ctr_nr_key, None)
    if not nr_ctr:
        nr_ctr = db.genereaza_nr_contract()
        st.session_state[ctr_nr_key] = nr_ctr
    return nr_ctr


def build_adresa_obiectiv(lucrare: dict) -> str:
    from utils.utils_documents import safe_str
    adresa = (
        f"Localitatea {safe_str(lucrare.get('adresa_localitate')).upper()}, "
        f"Strada {safe_str(lucrare.get('adresa_strada')).upper()}, "
        f"Nr. {safe_str(lucrare.get('adresa_numar'))}"
    )
    if safe_str(lucrare.get("adresa_bloc")).strip():
        adresa += f", Bl. {safe_str(lucrare.get('adresa_bloc'))}"
    if safe_str(lucrare.get("adresa_apartament")).strip():
        adresa += f", Ap. {safe_str(lucrare.get('adresa_apartament'))}"
    return adresa


def validate_excel_lucrare_fields(lucrare: dict) -> list[str]:
    from utils.utils_documents import safe_str
    campuri_obligatorii = [
        ("Cod ATR", safe_str(lucrare.get("cod_atr"))),
        ("Executant", safe_str(lucrare.get("executant") or "ECOLOPTIM S.R.L.")),
        ("Element SDA", safe_str(lucrare.get("element_sda"))),
        ("Comandă aprovizionare", safe_str(lucrare.get("comanda_aprovizionare"))),
        ("Nr. contract prestări servicii", safe_str(lucrare.get("contract_prestari_servicii"))),
        ("Diriginte de șantier", safe_str(lucrare.get("diriginte_santier"))),
    ]
    return [label for label, value in campuri_obligatorii if not str(value or "").strip()]


def build_situatie_plata_cell_values(client: dict, lucrare: dict, adresa_obiectiv: str, pret1: float, pret2: float, pret3: float) -> dict:
    from utils.utils_documents import safe_str
    from config.excel_mappings import SITUATIE_PLATA_BRANSAMENT_CONFIG
    cfg = SITUATIE_PLATA_BRANSAMENT_CONFIG["cells"]
    return {
        cfg["client"]: f"Client: {safe_str(client.get('nume')).upper()}",
        cfg["adresa_obiectiv"]: f"Adresa obiectiv:{adresa_obiectiv}",
        cfg["judet"]: f"Judet (sector): {safe_str(lucrare.get('adresa_judet')).upper()}",
        cfg["cod_atr"]: f"Cod ATR: {safe_str(lucrare.get('cod_atr'))}",
        cfg["executant"]: f"Executant: {safe_str(lucrare.get('executant') or 'ECOLOPTIM S.R.L.')}",
        cfg["element_sda"]: f"Element SDA bransament: {safe_str(lucrare.get('element_sda'))}",
        cfg["comanda_aprovizionare"]: f"Comanda aprovizionare: {safe_str(lucrare.get('comanda_aprovizionare'))}",
        cfg["pret_1"]: float(pret1 or 0.0),
        cfg["pret_2"]: float(pret2 or 0.0),
        cfg["pret_3"]: float(pret3 or 0.0),
        cfg["contract_prestari_servicii"]: (
            f"Valorile corespund notificarii transmise OSD si contractului de prestari servicii "
            f"nr.{safe_str(lucrare.get('contract_prestari_servicii'))}"
        ),
        cfg["diriginte_santier"]: safe_str(lucrare.get("diriginte_santier")),
    }


def show(user, client_id):
    clienti = db.lista_clienti()
    client = clienti[clienti["id"] == client_id].iloc[0]
    st.header(f"🔨 LUCRĂRI pentru: {client['nume']}")

    df = db.lista_lucrari_client(int(client_id))

    st.markdown("<div class='eco-filters'>", unsafe_allow_html=True)
    f1, f2, f3, f4, f5 = st.columns([2.2, 1.6, 2.2, 2.2, 1.2])

    tipuri_unice = sorted(df["tip_lucrare"].dropna().unique().tolist()) if not df.empty else []
    status_order = ["OFERTAT", "CONTRACTAT", "PROGRAMAT", "EXECUTAT", "FINALIZAT", "ÎNCHIS"]
    statusuri_existente = df["status"].dropna().astype(str).unique().tolist() if not df.empty else []
    statusuri_unice = [s for s in status_order if s in statusuri_existente]

    tip_selectat = f1.selectbox("Tip lucrare", ["Toate"] + tipuri_unice, key=f"{PREFIX}filtru_tip_{client_id}")
    status_selectat = f2.selectbox("Status", ["Toate"] + statusuri_unice, key=f"{PREFIX}filtru_status_{client_id}")
    cautare = f3.text_input("Căutare", placeholder="tip, observații, descriere, responsabil...", key=f"{PREFIX}filtru_search_{client_id}")
    sort_select = f4.selectbox("Sortare", ["Data contract ↓", "Data contract ↑", "Valoare ↓", "Valoare ↑", "Status A-Z", "Tip lucrare A-Z"], key=f"{PREFIX}sort_{client_id}")
    reset_filters = f5.button("Reset", key=f"{PREFIX}reset_filters_{client_id}")
    st.markdown("</div>", unsafe_allow_html=True)

    if reset_filters:
        for k in [
            f"{PREFIX}filtru_tip_{client_id}",
            f"{PREFIX}filtru_status_{client_id}",
            f"{PREFIX}filtru_search_{client_id}",
            f"{PREFIX}sort_{client_id}",
        ]:
            st.session_state.pop(k, None)
        st.rerun()

    if tip_selectat != "Toate" and not df.empty:
        df = df[df["tip_lucrare"] == tip_selectat]
    if status_selectat != "Toate" and not df.empty:
        df = df[df["status"] == status_selectat]
    if cautare and not df.empty:
        txt = cautare.strip().lower()
        mask = df.apply(
            lambda row: txt in " | ".join([
                str(row.get("tip_lucrare", "")),
                str(row.get("status", "")),
                str(row.get("responsabil", "")),
                str(row.get("observatii", "")),
                str(row.get("descriere", "")),
                str(row.get("echipa", "")),
            ]).lower(),
            axis=1,
        )
        df = df[mask]

    if not df.empty:
        if sort_select == "Data contract ↓":
            df = df.sort_values(by="data_contract", ascending=False, na_position="last")
        elif sort_select == "Data contract ↑":
            df = df.sort_values(by="data_contract", ascending=True, na_position="last")
        elif sort_select == "Valoare ↓":
            df = df.sort_values(by="valoare_contractata", ascending=False, na_position="last")
        elif sort_select == "Valoare ↑":
            df = df.sort_values(by="valoare_contractata", ascending=True, na_position="last")
        elif sort_select == "Status A-Z":
            df = df.sort_values(by="status", ascending=True, na_position="last")
        elif sort_select == "Tip lucrare A-Z":
            df = df.sort_values(by="tip_lucrare", ascending=True, na_position="last")

    render_lucrari_list(client_id, df)

    render_documente_panel(
        user=user,
        client_id=client_id,
        client=client,
        ensure_nr_ordin_fn=_ensure_nr_ordin_for_lucrare,
        ensure_nr_contract_fn=_ensure_nr_contract_for_lucrare,
        build_adresa_obiectiv_fn=build_adresa_obiectiv,
        validate_excel_lucrare_fields_fn=validate_excel_lucrare_fields,
        build_situatie_plata_cell_values_fn=build_situatie_plata_cell_values,
    )

    render_flux_birou_panel(
        user=user,
        client_id=client_id,
    )

    render_add_lucrare_form(user=user, client_id=client_id, client_row=client)
    render_edit_lucrare_form(client_id=client_id, df=df)
    render_delete_lucrare_panel(client_id=client_id, df=df)
