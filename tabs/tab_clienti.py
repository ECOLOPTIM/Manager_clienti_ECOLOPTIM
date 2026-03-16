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
    return f"<span style='color:{color}; font-size:14px; vertical-align:middle;'>{emoji}</span> <span style='vertical-align:middle;'>{str(status)}</span>"

def close_all_modals():
    st.session_state.pop("add_client_open", None)
    st.session_state.pop("edit_client_id", None)
    st.session_state.pop("lucrari_for_client", None)
    st.session_state.pop("delete_client_id", None)
    st.session_state.pop("show_atasamente_for", None)

def show(user):
    st.header("👥 CLIENȚI — ECOLOPTIM_CLIENTI")

    if st.button("➕ ADĂUGĂ CLIENT"):
        close_all_modals()
        st.session_state["add_client_open"] = True

    filter_cols = st.columns([3, 2, 2])
    filtru = filter_cols[0].text_input("Filtru rapid după nume/email")
    df_full = db.lista_clienti(filtru)

    # Filtre pentru localitate și strada (opțional)
    toate_localitatile = sorted(df_full["consum_localitate"].dropna().astype(str).str.title().unique())
    localitate_select = filter_cols[1].selectbox("Localitate", ["Toate"] + toate_localitatile, index=0)
    if localitate_select != "Toate":
        strazi_filtru = df_full[df_full["consum_localitate"].astype(str).str.title() == localitate_select]
    else:
        strazi_filtru = df_full
    toate_strazile = sorted(strazi_filtru["consum_strada"].dropna().astype(str).str.title().unique())
    strada_select = filter_cols[2].selectbox("Strada", ["Toate"] + toate_strazile, index=0)

    df = df_full
    if localitate_select != "Toate":
        df = df[df["consum_localitate"].astype(str).str.title() == localitate_select]
    if strada_select != "Toate":
        df = df[df["consum_strada"].astype(str).str.title() == strada_select]

    lucrari = db.lista_lucrari()
    valori_contract = lucrari.groupby("client_id")["valoare_contractata"].sum().to_dict()

    # PAGINARE
    PAGE_SIZE = 10
    if "clienti_page" not in st.session_state:
        st.session_state["clienti_page"] = 1
    total_pages = ((len(df)-1)//PAGE_SIZE)+1 if not df.empty else 1
    pag_cols = st.columns([2, 1, 2])
    if pag_cols[0].button("⏮️ Pagina anterioară", disabled=st.session_state["clienti_page"] <= 1):
        if st.session_state["clienti_page"] > 1:
            st.session_state["clienti_page"] -= 1
    pag_cols[1].markdown(f"<div style='text-align:center; font-weight:bold;'>Pagina {st.session_state['clienti_page']} din {total_pages}</div>", unsafe_allow_html=True)
    if pag_cols[2].button("Pagina următoare ⏭️", disabled=st.session_state["clienti_page"] >= total_pages):
        if st.session_state["clienti_page"] < total_pages:
            st.session_state["clienti_page"] += 1
    if st.session_state["clienti_page"] > total_pages:
        st.session_state["clienti_page"] = total_pages
    if st.session_state["clienti_page"] < 1:
        st.session_state["clienti_page"] = 1

    # TABEL CLIENȚI cu ordinea corectă JUDEȚ, LOCALITATE, ...
    if df.empty:
        st.info("NU EXISTĂ CLIENȚI PENTRU FILTRUL ACTUAL.")
    else:
        start, stop = (st.session_state["clienti_page"]-1)*PAGE_SIZE, (st.session_state["clienti_page"])*PAGE_SIZE
        df_page = df.iloc[start:stop]
        st.markdown("#### CLIENȚI (LOC CONSUM)")
        cols = st.columns([2.1, 2, 1.3, 2, 2, 1.5, 1.7, 1, 1, 1, 1, 1])
        header = [
            "NUME", "EMAIL", "JUDEȚ", "LOCALITATE", "STRADA", "NUMĂR", "STATUS",
            "VALOARE CONTRACT", "✏️", "🔨", "📎", "🗑️"
        ]
        for col, txt in zip(cols, header):
            col.write(f"**{txt}**")
        for i, row in df_page.iterrows():
            c = st.columns([2.1, 2, 1.3, 2, 2, 1.5, 1.7, 1, 1, 1, 1, 1])
            c[0].write(str(row["nume"]).upper())
            c[1].write(str(row["email"]).lower())
            c[2].write(str(row.get("consum_judet", "")).upper())
            c[3].write(str(row["consum_localitate"]).upper())
            c[4].write(str(row["consum_strada"]).upper())
            c[5].write(str(row["consum_numar"]))
            c[6].markdown(status_display(row["status"]), unsafe_allow_html=True)
            val_contract = valori_contract.get(row["id"], 0.0)
            c[7].write(f"{val_contract:,.2f}")
            if c[8].button("✏️", key=f"edit_{row['id']}"):
                close_all_modals()
                st.session_state["edit_client_id"] = row["id"]
            if c[9].button("🔨", key=f"lucrari_{row['id']}"):
                close_all_modals()
                st.session_state["lucrari_for_client"] = row["id"]
            if c[10].button("📎", key=f"attachments_{row['id']}"):
                close_all_modals()
                st.session_state["show_atasamente_for"] = row["id"]
            if c[11].button("🗑️", key=f"delete_{row['id']}"):
                close_all_modals()
                st.session_state["delete_client_id"] = row["id"]

    # SUBPAGINA LUCRĂRI CLIENT
    if st.session_state.get("lucrari_for_client"):
        import tabs.tab_lucrari_client
        tabs.tab_lucrari_client.show(user, st.session_state["lucrari_for_client"])
        if st.button("ÎNAPOI LA CLIENȚI", key="back_to_clients_works"):
            del st.session_state["lucrari_for_client"]
            st.rerun()

    # SUBPAGINA ATAȘAMENTE CLIENT
    if st.session_state.get("show_atasamente_for"):
        import tabs.tab_atasamente
        tabs.tab_atasamente.show(user, st.session_state["show_atasamente_for"])
        if st.button("ÎNAPOI LA CLIENȚI", key="back_to_clients_attachments"):
            del st.session_state["show_atasamente_for"]
            st.rerun()

    # Export EXCEL / CSV, păstrează ordinea dacă vrei aceleași coloane:
    export_df = df.copy()
    for col in export_df.columns:
        if col == "email":
            export_df[col] = export_df[col].astype(str).str.lower()
        else:
            export_df[col] = export_df[col].astype(str).str.upper()
    buffer = io.BytesIO()
    export_df.to_excel(buffer, index=False)
    buffer.seek(0)
    csv_data = export_df.to_csv(index=False).encode('utf-8')
    export_cols = st.columns(2)
    with export_cols[0]:
        st.download_button(
            label="💾 EXPORT EXCEL",
            data=buffer,
            file_name="CLIENTI.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    with export_cols[1]:
        st.download_button(
            label="💾 EXPORT CSV",
            data=csv_data,
            file_name="CLIENTI.csv",
            mime="text/csv"
        )

    # --- ADĂUGARE CLIENT (JUDEȚ PRIMUL) ---
    if st.session_state.get("add_client_open"):
        with st.form("add_client_form", clear_on_submit=True):
            col_status, col_obs, col_save = st.columns([1.3, 2.7, 1])
            status = col_status.selectbox("STATUS", STATUS_OPTIONS, key="add_status")
            observatii = col_obs.text_area("OBSERVAȚII", key="add_obs")
            save_btn = col_save.form_submit_button("💾 SALVEAZĂ CLIENTUL")
            col_nume, col_email, col_telefon = st.columns([2,2,1.7])
            nume = col_nume.text_input("NUME COMPLET", key="add_nume")
            email = col_email.text_input("EMAIL", key="add_email")
            telefon = col_telefon.text_input("TELEFON", key="add_telefon")
            col_firma, col_cod, col_scor = st.columns([2,2,1])
            firma = col_firma.text_input("FIRMĂ CLIENT", key="add_firma")
            cod_intern = col_cod.text_input("COD INTERN", key="add_cod")
            scor = col_scor.number_input("SCOR", value=0, key="add_scor")
            remark = st.text_input("REMARK", key="add_remark")
            st.markdown("#### ADRESA DOMICILIU")
            col_jud, col_loc, col_str, col_nr, col_bloc, col_ap = st.columns([1.2,2,2,1,1,1])
            domiciliu_judet = col_jud.text_input("JUDEȚ", key="add_dom_judet")
            domiciliu_localitate = col_loc.text_input("LOCALITATE", key="add_dom_loc")
            domiciliu_strada = col_str.text_input("STRADA", key="add_dom_str")
            domiciliu_numar = col_nr.text_input("NUMĂR", key="add_dom_nr")
            domiciliu_bloc = col_bloc.text_input("BLOC", key="add_dom_bloc")
            domiciliu_apartament = col_ap.text_input("APARTAMENT", key="add_dom_ap")
            aceeasi_adresa = st.checkbox(
                "Adresa de loc consum este identică cu domiciliu", value=False, key="add_same_addr"
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
                col_jud2, col_loc2, col_str2, col_nr2, col_bloc2, col_ap2 = st.columns([1.2,2,2,1,1,1])
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
                        "domiciliu_judet": domiciliu_judet,
                        "domiciliu_localitate": domiciliu_localitate,
                        "domiciliu_strada": domiciliu_strada,
                        "domiciliu_numar": domiciliu_numar,
                        "domiciliu_bloc": domiciliu_bloc,
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

    # --- EDITARE CLIENT (JUDEȚ PRIMUL) ---
    if st.session_state.get("edit_client_id"):
        client_id = st.session_state["edit_client_id"]
        df_all = db.lista_clienti()
        row = df_all[df_all["id"] == client_id].iloc[0]
        with st.form(f"edit_client_form_{client_id}", clear_on_submit=False):
            col_status, col_obs, col_save = st.columns([1.3, 2.7, 1])
            status = col_status.selectbox(
                "STATUS", STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(str(row["status"]).upper()) if str(row["status"]).upper() in STATUS_OPTIONS else 0,
                key="edit_status"
            )
            observatii = col_obs.text_area("OBSERVAȚII", value=str(row.get("observatii", "")), key="edit_obs")
            save_btn = col_save.form_submit_button("💾 SALVEAZĂ MODIFICĂRILE")
            col_nume, col_email, col_telefon = st.columns([2,2,1.7])
            nume = col_nume.text_input("NUME COMPLET", value=str(row["nume"]), key="edit_nume")
            email = col_email.text_input("EMAIL", value=str(row["email"]), key="edit_email")
            telefon = col_telefon.text_input("TELEFON", value=str(row.get("telefon", "")), key="edit_telefon")
            col_firma, col_cod, col_scor = st.columns([2,2,1])
            firma = col_firma.text_input("FIRMĂ CLIENT", value=str(row.get("firma","")), key="edit_firma")
            cod_intern = col_cod.text_input("COD INTERN", value=str(row.get("cod_intern", "")), key="edit_cod")
            scor = col_scor.number_input("SCOR", value=int(row.get("scor", 0)), key="edit_scor")
            remark = st.text_input("REMARK", value=str(row.get("remark", "")), key="edit_remark")
            st.markdown("#### ADRESA DOMICILIU")
            col_jud, col_loc, col_str, col_nr, col_bloc, col_ap = st.columns([1.2,2,2,1,1,1])
            domiciliu_judet = col_jud.text_input("JUDEȚ", value=str(row.get("domiciliu_judet", "")), key="edit_dom_judet")
            domiciliu_localitate = col_loc.text_input("LOCALITATE", value=str(row.get("domiciliu_localitate", "")), key="edit_dom_loc")
            domiciliu_strada = col_str.text_input("STRADA", value=str(row.get("domiciliu_strada", "")), key="edit_dom_strada")
            domiciliu_numar = col_nr.text_input("NUMĂR", value=str(row.get("domiciliu_numar", "")), key="edit_dom_nr")
            domiciliu_bloc = col_bloc.text_input("BLOC", value=str(row.get("domiciliu_bloc", "")), key="edit_dom_bloc")
            domiciliu_apartament = col_ap.text_input("APARTAMENT", value=str(row.get("domiciliu_apartament", "")), key="edit_dom_ap")
            same_addr_default = (
                str(row.get("domiciliu_judet", "")) == str(row.get("consum_judet", "")) and
                str(row.get("domiciliu_localitate", "")) == str(row.get("consum_localitate", "")) and
                str(row.get("domiciliu_strada", "")) == str(row.get("consum_strada", "")) and
                str(row.get("domiciliu_numar", "")) == str(row.get("consum_numar", "")) and
                str(row.get("domiciliu_bloc", "")) == str(row.get("consum_bloc", "")) and
                str(row.get("domiciliu_apartament", "")) == str(row.get("consum_apartament", ""))
            )
            aceeasi_adresa = st.checkbox(
                "Adresa de loc consum este identică cu domiciliu", value=same_addr_default, key="edit_same_addr"
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
                col_jud2, col_loc2, col_str2, col_nr2, col_bloc2, col_ap2 = st.columns([1.2,2,2,1,1,1])
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
                    "domiciliu_judet": domiciliu_judet,
                    "domiciliu_localitate": domiciliu_localitate,
                    "domiciliu_strada": domiciliu_strada,
                    "domiciliu_numar": domiciliu_numar,
                    "domiciliu_bloc": domiciliu_bloc,
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
        if st.button("ÎNCHIDE EDITARE", key=f"close_edit_{client_id}"):
            del st.session_state["edit_client_id"]
            st.rerun()

    # CONFIRMARE ȘTERGERE CLIENT
    if st.session_state.get("delete_client_id"):
        client_id = st.session_state["delete_client_id"]
        df_all = db.lista_clienti()
        row = df_all[df_all["id"] == client_id].iloc[0]
        st.error(
            f"EȘTI SIGUR CĂ VREI SĂ ȘTERGI CLIENTUL '{str(row['nume']).upper()}' DIN '{str(row.get('consum_judet','')).upper()}, {str(row['consum_localitate']).upper()}, {str(row['consum_strada']).upper()} NR. {str(row['consum_numar']).upper()}'?"
        )
        if st.button("CONFIRMĂ ȘTERGEREA", key=f"confirm_del_{client_id}"):
            db.sterge_client(client_id)
            st.success("CLIENT ȘTERS!")
            del st.session_state["delete_client_id"]
            st.rerun()
        if st.button("ANULEAZĂ", key=f"cancel_del_{client_id}"):
            del st.session_state["delete_client_id"]
            st.rerun()