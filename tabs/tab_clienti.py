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
STATUS_OPTIONS = ["OFERTAT", "PROGRAMAT", "CONTRACTAT", "EXECUTAT", "FINALIZAT", "ÎNCHIS"]


def status_display(status):
    emoji, color = STATUS_COLORS.get(str(status).upper(), ("⚪", "#b0b0b0"))
    return (
        f"<span style='color:{color}; font-size:14px; vertical-align:middle;'>{emoji}</span> "
        f"<span style='vertical-align:middle;'>{str(status)}</span>"
    )


def close_all_modals():
    st.session_state.pop("add_client_open", None)
    st.session_state.pop("edit_client_id", None)
    st.session_state.pop("lucrari_for_client", None)
    st.session_state.pop("financiar_for_client", None)
    st.session_state.pop("delete_client_id", None)
    st.session_state.pop("show_atasamente_for", None)
    st.session_state.pop("show_atasamente_lucrare_id", None)
    st.session_state.pop("show_atasamente_sarcina_id", None)


def _icon_btn(col, label: str, key: str) -> bool:
    with col:
        st.markdown("<div class='eco-icon-btn'>", unsafe_allow_html=True)
        pressed = st.button(label, key=key)
        st.markdown("</div>", unsafe_allow_html=True)
        return pressed


def _fmt_date_ro(value: str) -> str:
    s = str(value or "")
    if not s:
        return ""
    s_short = s.split(" ")[0] if " " in s else s
    try:
        dt = pd.to_datetime(s_short, errors="coerce")
        return dt.strftime("%d-%m-%Y") if not pd.isna(dt) else s_short
    except Exception:
        return s_short


def _num(x) -> float:
    try:
        return float(x or 0.0)
    except Exception:
        return 0.0


def show(user):
    st.header("👥 CLIENȚI — ECOLOPTIM_CLIENTI")

    # dacă venim din tab-ul Alerte și vrem să deschidem financiarul direct
    if st.session_state.get("open_financiar_for_client"):
        close_all_modals()
        st.session_state["financiar_for_client"] = st.session_state["open_financiar_for_client"]
        del st.session_state["open_financiar_for_client"]
        st.rerun()

    # === SUBPAGINI: dacă una e deschisă, ascundem lista de clienți ===
    if st.session_state.get("financiar_for_client"):
        import tabs.tab_financiar_client

        tabs.tab_financiar_client.show(user, st.session_state["financiar_for_client"])
        if st.button("⬅️ ÎNAPOI LA CLIENȚI", key="back_to_clients_fin_top"):
            del st.session_state["financiar_for_client"]
            st.rerun()
        return

    if st.session_state.get("lucrari_for_client"):
        import tabs.tab_lucrari_client

        tabs.tab_lucrari_client.show(user, st.session_state["lucrari_for_client"])
        if st.button("⬅️ ÎNAPOI LA CLIENȚI", key="back_to_clients_works_top"):
            del st.session_state["lucrari_for_client"]
            st.rerun()
        return

    if st.session_state.get("show_atasamente_for"):
        import tabs.tab_atasamente

        cli_id = int(st.session_state["show_atasamente_for"])
        lucrare_id = st.session_state.get("show_atasamente_lucrare_id", None)
        sarcina_id = st.session_state.get("show_atasamente_sarcina_id", None)

        tabs.tab_atasamente.show(user, cli_id, lucrare_id=lucrare_id, sarcina_id=sarcina_id)

        if st.button("⬅️ ÎNAPOI LA CLIENȚI", key="back_to_clients_attach_top"):
            del st.session_state["show_atasamente_for"]
            st.session_state.pop("show_atasamente_lucrare_id", None)
            st.session_state.pop("show_atasamente_sarcina_id", None)
            st.rerun()
        return

    # =========================
    # ADD CLIENT
    # =========================
    if st.session_state.get("add_client_open"):
        st.subheader("➕ Adăugare client")

        with st.form("add_client_form", clear_on_submit=True):
            col_status, col_obs, col_save = st.columns([1.3, 2.7, 1])
            status = col_status.selectbox("STATUS", STATUS_OPTIONS, key="add_status")
            observatii = col_obs.text_area("OBSERVAȚII", key="add_obs")
            save_btn = col_save.form_submit_button("💾 SALVEAZĂ CLIENTUL")

            col_nume, col_email, col_telefon = st.columns([2, 2, 1.7])
            nume = col_nume.text_input("NUME COMPLET", key="add_nume")
            email = col_email.text_input("EMAIL", key="add_email")
            telefon = col_telefon.text_input("TELEFON", key="add_telefon")

            col_firma, col_cod, col_scor = st.columns([2, 2, 1])
            firma = col_firma.text_input("FIRMĂ CLIENT", key="add_firma")
            cod_intern = col_cod.text_input("COD INTERN", key="add_cod")
            scor = col_scor.number_input("SCOR", value=0, key="add_scor")
            remark = st.text_input("REMARK", key="add_remark")

            # ---- DATE ACTE (pentru contracte) ----
            st.markdown("#### ACTE IDENTITATE (pentru contracte)")
            col_cnp, col_ci_serie, col_ci_nr = st.columns([2, 1, 1.5])
            cnp = col_cnp.text_input("CNP", key="add_cnp")
            ci_serie = col_ci_serie.text_input("CI SERIE", key="add_ci_serie")
            ci_numar = col_ci_nr.text_input("CI NUMĂR", key="add_ci_numar")

            col_emit, col_data = st.columns([2, 1.5])
            ci_emitent = col_emit.text_input("CI EMITENT (ex: SPCLEP Galați)", key="add_ci_emitent")
            ci_data = col_data.text_input("CI DATA (ex: 24.09.2024)", key="add_ci_data")

            st.markdown("#### ADRESA DOMICILIU")
            col_jud, col_loc, col_str, col_nr, col_bloc, col_sc, col_et, col_ap = st.columns([1.2, 2, 2, 1, 1, 1, 1, 1])
            domiciliu_judet = col_jud.text_input("JUDEȚ", key="add_dom_judet")
            domiciliu_localitate = col_loc.text_input("LOCALITATE", key="add_dom_loc")
            domiciliu_strada = col_str.text_input("STRADA", key="add_dom_str")
            domiciliu_numar = col_nr.text_input("NUMĂR", key="add_dom_nr")
            domiciliu_bloc = col_bloc.text_input("BLOC", key="add_dom_bloc")
            domiciliu_scara = col_sc.text_input("SCARĂ", key="add_dom_scara")
            domiciliu_etaj = col_et.text_input("ETAJ", key="add_dom_etaj")
            domiciliu_apartament = col_ap.text_input("APARTAMENT", key="add_dom_ap")

            aceeasi_adresa = st.checkbox(
                "Adresa de loc consum este identică cu domiciliu",
                value=False,
                key="add_same_addr",
            )

            st.markdown("#### ADRESA LOC CONSUM")
            if aceeasi_adresa:
                consum_judet = domiciliu_judet
                consum_localitate = domiciliu_localitate
                consum_strada = domiciliu_strada
                consum_numar = domiciliu_numar
                consum_bloc = domiciliu_bloc
                consum_apartament = domiciliu_apartament
                st.info("Adresa de loc consum va fi preluată din domiciliu.")
            else:
                col_jud2, col_loc2, col_str2, col_nr2, col_bloc2, col_ap2 = st.columns([1.2, 2, 2, 1, 1, 1])
                consum_judet = col_jud2.text_input("JUDEȚ", key="add_con_judet")
                consum_localitate = col_loc2.text_input("LOCALITATE", key="add_con_loc")
                consum_strada = col_str2.text_input("STRADA", key="add_con_strada")
                consum_numar = col_nr2.text_input("NUMĂR", key="add_con_nr")
                consum_bloc = col_bloc2.text_input("BLOC", key="add_con_bloc")
                consum_apartament = col_ap2.text_input("APARTAMENT", key="add_con_ap")

            if save_btn:
                if not nume or not email:
                    st.error("Completează NUME și EMAIL!")
                else:
                    valori = {
                        "nume": nume,
                        "email": email,
                        "telefon": telefon,
                        "firma": firma,
                        "status": status,
                        "observatii": observatii,
                        "cod_intern": cod_intern,
                        "scor": scor,
                        "remark": remark,
                        "cnp": cnp,
                        "ci_serie": ci_serie,
                        "ci_numar": ci_numar,
                        "ci_emitent": ci_emitent,
                        "ci_data": ci_data,
                        "domiciliu_judet": domiciliu_judet,
                        "domiciliu_localitate": domiciliu_localitate,
                        "domiciliu_strada": domiciliu_strada,
                        "domiciliu_numar": domiciliu_numar,
                        "domiciliu_bloc": domiciliu_bloc,
                        "domiciliu_scara": domiciliu_scara,
                        "domiciliu_etaj": domiciliu_etaj,
                        "domiciliu_apartament": domiciliu_apartament,
                        "consum_judet": consum_judet,
                        "consum_localitate": consum_localitate,
                        "consum_strada": consum_strada,
                        "consum_numar": consum_numar,
                        "consum_bloc": consum_bloc,
                        "consum_apartament": consum_apartament,
                    }
                    db.adauga_client(valori)
                    st.success(f"Clientul {nume.upper()} a fost adăugat!")
                    st.session_state["add_client_open"] = False
                    st.rerun()

        if st.button("⛔ RENUNȚĂ", key="close_add_client"):
            st.session_state["add_client_open"] = False
            st.rerun()
        return

    # =========================
    # EDIT CLIENT
    # =========================
    if st.session_state.get("edit_client_id"):
        client_id = st.session_state["edit_client_id"]
        df_all = db.lista_clienti()
        row = df_all[df_all["id"] == client_id].iloc[0]

        st.subheader(f"✏️ Editare client — {str(row.get('nume', '')).upper()}")

        with st.form(f"edit_client_form_{client_id}", clear_on_submit=False):
            col_status, col_obs, col_save = st.columns([1.3, 2.7, 1])
            status = col_status.selectbox(
                "STATUS",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(str(row["status"]).upper())
                if str(row["status"]).upper() in STATUS_OPTIONS
                else 0,
                key="edit_status",
            )
            observatii = col_obs.text_area("OBSERVAȚII", value=str(row.get("observatii", "")), key="edit_obs")
            save_btn = col_save.form_submit_button("💾 SALVEAZĂ MODIFICĂRILE")

            col_nume, col_email, col_telefon = st.columns([2, 2, 1.7])
            nume = col_nume.text_input("NUME COMPLET", value=str(row["nume"]), key="edit_nume")
            email = col_email.text_input("EMAIL", value=str(row["email"]), key="edit_email")
            telefon = col_telefon.text_input("TELEFON", value=str(row.get("telefon", "")), key="edit_telefon")

            col_firma, col_cod, col_scor = st.columns([2, 2, 1])
            firma = col_firma.text_input("FIRMĂ CLIENT", value=str(row.get("firma", "")), key="edit_firma")
            cod_intern = col_cod.text_input("COD INTERN", value=str(row.get("cod_intern", "")), key="edit_cod")
            scor = col_scor.number_input("SCOR", value=int(row.get("scor", 0)), key="edit_scor")
            remark = st.text_input("REMARK", value=str(row.get("remark", "")), key="edit_remark")

            # ---- DATE ACTE (pentru contracte) ----
            st.markdown("#### ACTE IDENTITATE (pentru contracte)")
            col_cnp, col_ci_serie, col_ci_nr = st.columns([2, 1, 1.5])
            cnp = col_cnp.text_input("CNP", value=str(row.get("cnp", "")), key="edit_cnp")
            ci_serie = col_ci_serie.text_input("CI SERIE", value=str(row.get("ci_serie", "")), key="edit_ci_serie")
            ci_numar = col_ci_nr.text_input("CI NUMĂR", value=str(row.get("ci_numar", "")), key="edit_ci_numar")

            col_emit, col_data = st.columns([2, 1.5])
            ci_emitent = col_emit.text_input("CI EMITENT (ex: SPCLEP Galați)", value=str(row.get("ci_emitent", "")), key="edit_ci_emitent")
            ci_data = col_data.text_input("CI DATA (ex: 24.09.2024)", value=str(row.get("ci_data", "")), key="edit_ci_data")

            st.markdown("#### ADRESA DOMICILIU")
            col_jud, col_loc, col_str, col_nr, col_bloc, col_sc, col_et, col_ap = st.columns([1.2, 2, 2, 1, 1, 1, 1, 1])
            domiciliu_judet = col_jud.text_input("JUDEȚ", value=str(row.get("domiciliu_judet", "")), key="edit_dom_judet")
            domiciliu_localitate = col_loc.text_input("LOCALITATE", value=str(row.get("domiciliu_localitate", "")), key="edit_dom_loc")
            domiciliu_strada = col_str.text_input("STRADA", value=str(row.get("domiciliu_strada", "")), key="edit_dom_strada")
            domiciliu_numar = col_nr.text_input("NUMĂR", value=str(row.get("domiciliu_numar", "")), key="edit_dom_nr")
            domiciliu_bloc = col_bloc.text_input("BLOC", value=str(row.get("domiciliu_bloc", "")), key="edit_dom_bloc")
            domiciliu_scara = col_sc.text_input("SCARĂ", value=str(row.get("domiciliu_scara", "")), key="edit_dom_scara")
            domiciliu_etaj = col_et.text_input("ETAJ", value=str(row.get("domiciliu_etaj", "")), key="edit_dom_etaj")
            domiciliu_apartament = col_ap.text_input("APARTAMENT", value=str(row.get("domiciliu_apartament", "")), key="edit_dom_ap")

            same_addr_default = (
                str(row.get("domiciliu_judet", "")) == str(row.get("consum_judet", ""))
                and str(row.get("domiciliu_localitate", "")) == str(row.get("consum_localitate", ""))
                and str(row.get("domiciliu_strada", "")) == str(row.get("consum_strada", ""))
                and str(row.get("domiciliu_numar", "")) == str(row.get("consum_numar", ""))
                and str(row.get("domiciliu_bloc", "")) == str(row.get("consum_bloc", ""))
                and str(row.get("domiciliu_apartament", "")) == str(row.get("consum_apartament", ""))
                and str(row.get("domiciliu_scara", "")) == str(row.get("domiciliu_scara", ""))
                and str(row.get("domiciliu_etaj", "")) == str(row.get("domiciliu_etaj", ""))
            )
            aceeasi_adresa = st.checkbox(
                "Adresa de loc consum este identică cu domiciliu",
                value=same_addr_default,
                key="edit_same_addr",
            )

            st.markdown("#### ADRESA LOC CONSUM")
            if aceeasi_adresa:
                consum_judet = domiciliu_judet
                consum_localitate = domiciliu_localitate
                consum_strada = domiciliu_strada
                consum_numar = domiciliu_numar
                consum_bloc = domiciliu_bloc
                consum_apartament = domiciliu_apartament
                st.info("Adresa de loc consum va fi preluată din domiciliu.")
            else:
                col_jud2, col_loc2, col_str2, col_nr2, col_bloc2, col_ap2 = st.columns([1.2, 2, 2, 1, 1, 1])
                consum_judet = col_jud2.text_input("JUDEȚ", value=str(row.get("consum_judet", "")), key="edit_con_judet")
                consum_localitate = col_loc2.text_input("LOCALITATE", value=str(row.get("consum_localitate", "")), key="edit_con_loc")
                consum_strada = col_str2.text_input("STRADA", value=str(row.get("consum_strada", "")), key="edit_con_strada")
                consum_numar = col_nr2.text_input("NUMĂR", value=str(row.get("consum_numar", "")), key="edit_con_nr")
                consum_bloc = col_bloc2.text_input("BLOC", value=str(row.get("consum_bloc", "")), key="edit_con_bloc")
                consum_apartament = col_ap2.text_input("APARTAMENT", value=str(row.get("consum_apartament", "")), key="edit_con_ap")

            if save_btn:
                valori = {
                    "nume": nume,
                    "email": email,
                    "telefon": telefon,
                    "firma": firma,
                    "status": status,
                    "observatii": observatii,
                    "cod_intern": cod_intern,
                    "scor": scor,
                    "remark": remark,
                    "cnp": cnp,
                    "ci_serie": ci_serie,
                    "ci_numar": ci_numar,
                    "ci_emitent": ci_emitent,
                    "ci_data": ci_data,
                    "domiciliu_judet": domiciliu_judet,
                    "domiciliu_localitate": domiciliu_localitate,
                    "domiciliu_strada": domiciliu_strada,
                    "domiciliu_numar": domiciliu_numar,
                    "domiciliu_bloc": domiciliu_bloc,
                    "domiciliu_scara": domiciliu_scara,
                    "domiciliu_etaj": domiciliu_etaj,
                    "domiciliu_apartament": domiciliu_apartament,
                    "consum_judet": consum_judet,
                    "consum_localitate": consum_localitate,
                    "consum_strada": consum_strada,
                    "consum_numar": consum_numar,
                    "consum_bloc": consum_bloc,
                    "consum_apartament": consum_apartament,
                }
                db.modifica_client(client_id, valori)
                st.success("DATELE CLIENTULUI AU FOST ACTUALIZATE!")
                del st.session_state["edit_client_id"]
                st.rerun()

        if st.button("⬅️ ÎNCHIDE EDITARE", key=f"close_edit_{client_id}"):
            del st.session_state["edit_client_id"]
            st.rerun()
        return

    # =========================
    # DELETE CLIENT
    # =========================
    if st.session_state.get("delete_client_id"):
        client_id = st.session_state["delete_client_id"]
        df_all = db.lista_clienti()
        row = df_all[df_all["id"] == client_id].iloc[0]

        st.subheader("🗑️ Ștergere client")
        st.error(
            f"EȘTI SIGUR CĂ VREI SĂ ȘTERGI CLIENTUL '{str(row['nume']).upper()}' DIN "
            f"'{str(row.get('consum_judet', '')).upper()}, {str(row['consum_localitate']).upper()}, "
            f"{str(row['consum_strada']).upper()} NR. {str(row['consum_numar']).upper()}'?"
        )

        if st.button("CONFIRMĂ ȘTERGEREA", key=f"confirm_del_{client_id}"):
            db.sterge_client(client_id)
            st.success("CLIENT ȘTERS!")
            del st.session_state["delete_client_id"]
            st.rerun()

        if st.button("ANULEAZĂ", key=f"cancel_del_{client_id}"):
            del st.session_state["delete_client_id"]
            st.rerun()
        return

    # =========================
    # LISTĂ CLIENȚI
    # =========================
    if st.button("➕ ADĂUGĂ CLIENT"):
        close_all_modals()
        st.session_state["add_client_open"] = True
        st.rerun()

    # ----------------- FILTRE (în eco-filters) -----------------
    if "clienti_filters_reset" not in st.session_state:
        st.session_state["clienti_filters_reset"] = 0
    rid = st.session_state["clienti_filters_reset"]

    st.markdown("<div class='eco-filters'>", unsafe_allow_html=True)
    filter_cols = st.columns([3, 1.2, 1.2, 2, 2, 2, 1.1])

    filtru = filter_cols[0].text_input("Filtru rapid după nume/email", key=f"cli_text_{rid}")
    df_full = db.lista_clienti(filtru)

    df_full = df_full.copy()
    df_full["__DATA"] = pd.to_datetime(df_full.get("data_adaugarii", ""), errors="coerce")

    date_valid = df_full["__DATA"].dropna()
    ani = sorted(date_valid.dt.year.unique().tolist()) if not date_valid.empty else []
    luni = list(range(1, 13))

    an_select = filter_cols[1].selectbox("An", ["Toți"] + ani, index=0, key=f"cli_an_{rid}")
    luna_select = filter_cols[2].selectbox("Lună", ["Toate"] + luni, index=0, key=f"cli_luna_{rid}")

    if an_select != "Toți":
        df_full = df_full[df_full["__DATA"].dt.year == int(an_select)]
    if luna_select != "Toate":
        df_full = df_full[df_full["__DATA"].dt.month == int(luna_select)]

    toate_judetele = sorted(df_full["consum_judet"].dropna().astype(str).str.title().unique()) if not df_full.empty else []
    judet_select = filter_cols[3].selectbox("Județ", ["Toate"] + toate_judetele, index=0, key=f"cli_j_{rid}")

    df_judet = df_full
    if judet_select != "Toate" and not df_judet.empty:
        df_judet = df_judet[df_judet["consum_judet"].astype(str).str.title() == judet_select]

    toate_localitatile = sorted(df_judet["consum_localitate"].dropna().astype(str).str.title().unique()) if not df_judet.empty else []
    localitate_select = filter_cols[4].selectbox("Localitate", ["Toate"] + toate_localitatile, index=0, key=f"cli_loc_{rid}")

    df_loc = df_judet
    if localitate_select != "Toate" and not df_loc.empty:
        df_loc = df_loc[df_loc["consum_localitate"].astype(str).str.title() == localitate_select]

    toate_strazile = sorted(df_loc["consum_strada"].dropna().astype(str).str.title().unique()) if not df_loc.empty else []
    strada_select = filter_cols[5].selectbox("Strada", ["Toate"] + toate_strazile, index=0, key=f"cli_str_{rid}")

    if filter_cols[6].button("Reset", key=f"cli_reset_{rid}"):
        st.session_state["clienti_filters_reset"] += 1
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    df = df_loc
    if strada_select != "Toate" and not df.empty:
        df = df[df["consum_strada"].astype(str).str.title() == strada_select]

    df = df.drop(columns=["__DATA"], errors="ignore")

    # ---- CALCULE (contract/facturat/sold) + sortare ----
    lucrari = db.lista_lucrari()
    valori_contract = (
        lucrari.groupby("client_id")["valoare_contractata"].sum().to_dict()
        if (lucrari is not None and not lucrari.empty)
        else {}
    )

    solduri = db.solduri_pe_clienti() or {}
    facturat = db.facturat_pe_clienti() or {}

    df = df.copy()
    df["__SOLD"] = df["id"].apply(lambda cid: float(solduri.get(int(cid), 0.0) or 0.0))

    st.markdown("<div class='eco-filters'>", unsafe_allow_html=True)
    fin_cols = st.columns([1.4, 1.3, 1.5, 2.0, 1.1])

    doar_restantieri = fin_cols[0].checkbox("Doar restanțieri (SOLD > 0)", value=False, key=f"cli_rest_{rid}")
    sort_by_sold = fin_cols[1].checkbox("Sortează după SOLD", value=False, key=f"cli_sort_{rid}")
    sold_desc = fin_cols[2].selectbox("Ordine SOLD", ["Desc", "Asc"], index=0, key=f"cli_ord_{rid}")
    prag = fin_cols[3].number_input(
        "Prag minim SOLD (RON)",
        min_value=0.0,
        step=100.0,
        value=0.0,
        key=f"cli_prag_{rid}",
    )

    if fin_cols[4].button("Reset", key=f"cli_fin_reset_{rid}"):
        st.session_state["clienti_filters_reset"] += 1
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    if doar_restantieri:
        df = df[df["__SOLD"] > 0]
    if prag > 0:
        df = df[df["__SOLD"] >= float(prag)]
    if sort_by_sold and not df.empty:
        df = df.sort_values("__SOLD", ascending=(sold_desc == "Asc"))

    # ---- PAGINARE ----
    PAGE_SIZE = 10
    if "clienti_page" not in st.session_state:
        st.session_state["clienti_page"] = 1

    total_pages = ((len(df) - 1) // PAGE_SIZE) + 1 if not df.empty else 1
    if st.session_state["clienti_page"] > total_pages:
        st.session_state["clienti_page"] = total_pages
    if st.session_state["clienti_page"] < 1:
        st.session_state["clienti_page"] = 1

    if df.empty:
        st.info("NU EXISTĂ CLIENȚI PENTRU FILTRUL ACTUAL.")
        return

    start, stop = (st.session_state["clienti_page"] - 1) * PAGE_SIZE, st.session_state["clienti_page"] * PAGE_SIZE
    df_page = df.iloc[start:stop]

    if "selected_client_id" not in st.session_state:
        st.session_state["selected_client_id"] = None

    st.markdown("<div class='clients-table'>", unsafe_allow_html=True)
    st.markdown("<div class='eco-card'>", unsafe_allow_html=True)
    st.markdown("#### CLIENȚI (LOC CONSUM)")

    selected_id = st.session_state.get("selected_client_id")
    if selected_id is not None:
        sel_df = df[df["id"] == selected_id]
        if not sel_df.empty:
            sel = sel_df.iloc[0]
            meta = f"{str(sel.get('nume','')).upper()} • {str(sel.get('consum_localitate','')).upper()} • {str(sel.get('email','')).lower()}"
        else:
            meta = f"Client ID: {selected_id}"

        st.markdown(
            f"""
            <div class="clients-actionbar">
              <div class="meta">Selectat: <b>{meta}</b></div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        btn_cols = st.columns([1, 1, 1, 1, 1, 6])
        if _icon_btn(btn_cols[0], "✏️", key="sel_edit"):
            close_all_modals()
            st.session_state["edit_client_id"] = int(selected_id)
            st.rerun()
        if _icon_btn(btn_cols[1], "🔨", key="sel_lucrari"):
            close_all_modals()
            st.session_state["lucrari_for_client"] = int(selected_id)
            st.rerun()
        if _icon_btn(btn_cols[2], "💶", key="sel_fin"):
            close_all_modals()
            st.session_state["financiar_for_client"] = int(selected_id)
            st.rerun()
        if _icon_btn(btn_cols[3], "📎", key="sel_attach"):
            close_all_modals()
            st.session_state["show_atasamente_for"] = int(selected_id)
            st.session_state["show_atasamente_lucrare_id"] = None
            st.session_state["show_atasamente_sarcina_id"] = None
            st.rerun()
        if _icon_btn(btn_cols[4], "🗑️", key="sel_delete"):
            close_all_modals()
            st.session_state["delete_client_id"] = int(selected_id)
            st.rerun()

    # Header: stânga (grid 11 col) + dreapta (SEL)
    h_cols = st.columns([11.45, 0.55])
    with h_cols[0]:
        st.markdown(
            """
            <div class="clients-grid clients-grid-header">
              <div>DATA</div><div>NUME</div><div>EMAIL</div><div>JUDEȚ</div><div>LOCALITATE</div>
              <div>STRADA</div><div>NUMĂR</div><div>STATUS</div><div>VALOARE CONTRACT</div><div>FACTURAT</div><div>SOLD</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with h_cols[1]:
        st.markdown("<div class='clients-grid-header' style='text-align:center;'>SEL</div>", unsafe_allow_html=True)

    for _, row in df_page.iterrows():
        client_id = int(row["id"])

        data_ro = _fmt_date_ro(row.get("data_adaugarii", ""))
        val_contract = _num(valori_contract.get(client_id, 0.0))
        total_facturat = _num(facturat.get(client_id, 0.0))
        sold = _num(solduri.get(client_id, 0.0))

        fact_html = f"{total_facturat:,.2f}"
        if total_facturat > 0:
            fact_html = f"<span style='color:#0A84FF; font-weight:900;'>{total_facturat:,.2f}</span>"

        sold_html = f"{sold:,.2f}"
        if sold > 0:
            sold_html = f"<span style='color:#EF4444; font-weight:900;'>{sold:,.2f}</span>"
        elif sold < 0:
            sold_html = f"<span style='color:#10B981; font-weight:900;'>{sold:,.2f}</span>"

        row_class = "clients-grid-row"
        if st.session_state.get("selected_client_id") == client_id:
            row_class += " selected"

        row_cols = st.columns([11.45, 0.55])

        with row_cols[0]:
            st.markdown(
                f"""
                <div class="clients-grid {row_class}">
                  <div class="clip">{data_ro}</div>
                  <div class="clip">{str(row.get('nume','')).upper()}</div>
                  <div class="clip">{str(row.get('email','')).lower()}</div>
                  <div class="clip">{str(row.get('consum_judet','')).upper()}</div>
                  <div class="clip">{str(row.get('consum_localitate','')).upper()}</div>
                  <div class="clip">{str(row.get('consum_strada','')).upper()}</div>
                  <div class="clip">{str(row.get('consum_numar',''))}</div>
                  <div class="clip">{status_display(row.get('status',''))}</div>
                  <div class="clip num">{val_contract:,.2f}</div>
                  <div class="clip num">{fact_html}</div>
                  <div class="clip num">{sold_html}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with row_cols[1]:
            is_sel = st.session_state.get("selected_client_id") == client_id
            if st.button("▾" if is_sel else "▸", key=f"sel_{client_id}"):
                st.session_state["selected_client_id"] = client_id
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # eco-card
    st.markdown("</div>", unsafe_allow_html=True)  # clients-table

    # ---- PAGINARE (centrată) ----
    st.markdown("---")
    outer = st.columns([1, 3, 1])

    with outer[1]:
        mid = st.columns([0.45, 1.1, 0.45])

        prev_disabled = st.session_state["clienti_page"] <= 1
        next_disabled = st.session_state["clienti_page"] >= total_pages

        if mid[0].button("⬅️", disabled=prev_disabled, key="clienti_prev_center"):
            st.session_state["clienti_page"] -= 1
            st.rerun()

        mid[1].markdown(
            f"<div style='text-align:center; font-weight:900; padding-top:6px;'>"
            f"Pagina {st.session_state['clienti_page']} / {total_pages}"
            f"</div>",
            unsafe_allow_html=True,
        )

        if mid[2].button("➡️", disabled=next_disabled, key="clienti_next_center"):
            st.session_state["clienti_page"] += 1
            st.rerun()

        with st.popover("Sari la pagina"):
            pages = list(range(1, total_pages + 1))
            jump = st.selectbox(
                "Pagina",
                options=pages,
                index=pages.index(st.session_state["clienti_page"]),
                key="clienti_jump_center",
                label_visibility="collapsed",
            )
            if jump != st.session_state["clienti_page"]:
                st.session_state["clienti_page"] = int(jump)
                st.rerun()

    # ---- EXPORT ----
    st.markdown("---")
    st.subheader("📤 Export")

    export_df = df.copy().drop(columns=["__SOLD"], errors="ignore")
    export_df["VALOARE_CONTRACT"] = export_df["id"].apply(lambda cid: float(valori_contract.get(int(cid), 0.0) or 0.0))
    export_df["FACTURAT"] = export_df["id"].apply(lambda cid: float(facturat.get(int(cid), 0.0) or 0.0))
    export_df["SOLD"] = export_df["id"].apply(lambda cid: float(solduri.get(int(cid), 0.0) or 0.0))

    cols_export = [
        "id",
        "nume",
        "email",
        "telefon",
        "status",
        "consum_judet",
        "consum_localitate",
        "consum_strada",
        "consum_numar",
        "VALOARE_CONTRACT",
        "FACTURAT",
        "SOLD",
    ]
    cols_export = [c for c in cols_export if c in export_df.columns]
    export_df = export_df[cols_export].copy()

    export_df = export_df.rename(
        columns={
            "id": "ID",
            "nume": "NUME",
            "email": "EMAIL",
            "telefon": "TELEFON",
            "status": "STATUS",
            "consum_judet": "JUDET_CONSUM",
            "consum_localitate": "LOCALITATE_CONSUM",
            "consum_strada": "STRADA_CONSUM",
            "consum_numar": "NUMAR_CONSUM",
        }
    )

    buffer = io.BytesIO()
    export_df.to_excel(buffer, index=False)
    buffer.seek(0)
    csv_data = export_df.to_csv(index=False).encode("utf-8")

    export_cols = st.columns(2)
    with export_cols[0]:
        st.download_button(
            label="💾 EXPORT EXCEL",
            data=buffer,
            file_name="CLIENTI.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_excel_clienti",
        )
    with export_cols[1]:
        st.download_button(
            label="💾 EXPORT CSV",
            data=csv_data,
            file_name="CLIENTI.csv",
            mime="text/csv",
            key="export_csv_clienti",
        )