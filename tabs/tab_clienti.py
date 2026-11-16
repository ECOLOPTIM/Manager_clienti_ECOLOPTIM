import streamlit as st
import db.db as db
import pandas as pd
import io
import re
from utils.utils_status import format_status
from utils.utils_documents import make_export_filename


STATUS_OPTIONS = ["OFERTAT", "CONTRACTAT", "PROGRAMAT", "EXECUTAT", "FINALIZAT", "ÎNCHIS"]

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
    
def _is_mobile() -> bool:
    try:
        ua = st.context.headers.get("user-agent", "").lower()
    except Exception:
        ua = ""
    return bool(re.search(r"android|iphone|ipad|mobile", ua))


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

    if st.session_state.get("add_client_open") or st.session_state.get("edit_client_id"):
        from tabs.components.client_profile import render_editor
        client_id=st.session_state.get("edit_client_id")
        if render_editor(client_id):
            st.session_state.pop("add_client_open",None)
            st.session_state.pop("edit_client_id",None)
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
            f"'{str(row.get('domiciliu_judet', '')).upper()}, {str(row['domiciliu_localitate']).upper()}, "
            f"{str(row['domiciliu_strada']).upper()} NR. {str(row['domiciliu_numar']).upper()}'?"
        )

        if st.button("CONFIRMĂ ȘTERGEREA", key=f"confirm_del_{client_id}"):
            try:
                db.sterge_client(client_id)
                st.success("CLIENT ȘTERS!")
                del st.session_state["delete_client_id"]
                st.rerun()
            except Exception as e:
                st.error(str(e))

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
    filter_cols = st.columns([3, 1.1, 1.1, 1.6, 1.8, 1.8, 1.8, 1.1])

    filtru = filter_cols[0].text_input("Filtru rapid: nume / email / telefon / firmă / cod", key=f"cli_text_{rid}")
    df_full = db.lista_clienti(filtru)

    df_full = df_full.copy()
    df_full["__DATA"] = pd.to_datetime(df_full.get("data_adaugarii", ""), errors="coerce")

    date_valid = df_full["__DATA"].dropna()
    ani = sorted(date_valid.dt.year.unique().tolist()) if not date_valid.empty else []
    luni = list(range(1, 13))

    an_select = filter_cols[1].selectbox("An", ["Toți"] + ani, index=0, key=f"cli_an_{rid}")
    luna_select = filter_cols[2].selectbox("Lună", ["Toate"] + luni, index=0, key=f"cli_luna_{rid}")

    statusuri = ["Toate"] + STATUS_OPTIONS
    status_select = filter_cols[3].selectbox("Status", statusuri, index=0, key=f"cli_status_{rid}")
    
    if an_select != "Toți":
        df_full = df_full[df_full["__DATA"].dt.year == int(an_select)]
    if luna_select != "Toate":
        df_full = df_full[df_full["__DATA"].dt.month == int(luna_select)]
    if status_select != "Toate":
        df_full = df_full[df_full["status"].astype(str).str.upper() == str(status_select).upper()]

    toate_judetele = sorted(df_full["domiciliu_judet"].dropna().astype(str).str.title().unique()) if not df_full.empty else []
    judet_select = filter_cols[4].selectbox("Județ", ["Toate"] + toate_judetele, index=0, key=f"cli_j_{rid}")

    df_judet = df_full
    if judet_select != "Toate" and not df_judet.empty:
        df_judet = df_judet[df_judet["domiciliu_judet"].astype(str).str.title() == judet_select]

    toate_localitatile = sorted(df_judet["domiciliu_localitate"].dropna().astype(str).str.title().unique()) if not df_judet.empty else []
    localitate_select = filter_cols[5].selectbox("Localitate", ["Toate"] + toate_localitatile, index=0, key=f"cli_loc_{rid}")

    df_loc = df_judet
    if localitate_select != "Toate" and not df_loc.empty:
        df_loc = df_loc[df_loc["domiciliu_localitate"].astype(str).str.title() == localitate_select]

    toate_strazile = sorted(df_loc["domiciliu_strada"].dropna().astype(str).str.title().unique()) if not df_loc.empty else []
    strada_select = filter_cols[6].selectbox("Strada", ["Toate"] + toate_strazile, index=0, key=f"cli_str_{rid}")
    
    if filter_cols[7].button("Reset", key=f"cli_reset_{rid}"):
        st.session_state["clienti_filters_reset"] += 1
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    df = df_loc
    if strada_select != "Toate" and not df.empty:
        df = df[df["domiciliu_strada"].astype(str).str.title() == strada_select]

    df = df.drop(columns=["__DATA"], errors="ignore")

    # ---- CALCULE (contract/facturat/sold) + sortare ----
    agg_df = db.agregate_financiare_clienti()
    if agg_df is None or agg_df.empty:
        contract_map = {}
        facturat_map = {}
        solduri_map = {}
    else:
        contract_map = dict(zip(agg_df["client_id"].astype(int), agg_df["valoare_contract"].astype(float)))
        facturat_map = dict(zip(agg_df["client_id"].astype(int), agg_df["facturat"].astype(float)))
        solduri_map = dict(zip(agg_df["client_id"].astype(int), agg_df["sold"].astype(float)))

    df = df.copy()
    df["__SOLD"] = df["id"].apply(lambda cid: float(solduri_map.get(int(cid), 0.0) or 0.0))

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

    view_mode = st.segmented_control(
        "Vizualizare",
        options=["Tabel", "Carduri"],
        default="Tabel",
        key="clienti_view_mode",
    )
    mobile_view = view_mode == "Carduri"

    if mobile_view:
        st.markdown("#### CLIENȚI (vizualizare carduri)")
        for _, row in df_page.iterrows():
            client_id = int(row["id"])
            data_ro = _fmt_date_ro(row.get("data_adaugarii", ""))
            val_contract = _num(contract_map.get(client_id, 0.0))
            total_facturat = _num(facturat_map.get(client_id, 0.0))
            sold = _num(solduri_map.get(client_id, 0.0))

            with st.container(border=True):
                st.markdown(f"**{str(row.get('nume','')).upper()}**")
                st.caption(f"ID: {client_id} • Data: {data_ro}")
                st.write(f"📧 {str(row.get('email','')).lower()} | 📞 {str(row.get('telefon',''))}")
                st.write(
                    f"📍 {str(row.get('domiciliu_judet','')).upper()}, "
                    f"{str(row.get('domiciliu_localitate','')).upper()}, "
                    f"{str(row.get('domiciliu_strada','')).upper()} nr. {str(row.get('domiciliu_numar',''))}"
                )
                st.write(f"Status: {format_status(row.get('status',''))}")
                st.write(
                    f"Contract: **{val_contract:,.2f}** | "
                    f"Facturat: **{total_facturat:,.2f}** | "
                    f"Sold: **{sold:,.2f}**"
                )

                c1, c2, c3, c4, c5 = st.columns(5)
                if c1.button("✏️", key=f"m_edit_{client_id}"):
                    close_all_modals()
                    st.session_state["edit_client_id"] = client_id
                    st.rerun()
                if c2.button("🔨", key=f"m_lucr_{client_id}"):
                    close_all_modals()
                    st.session_state["lucrari_for_client"] = client_id
                    st.rerun()
                if c3.button("💶", key=f"m_fin_{client_id}"):
                    close_all_modals()
                    st.session_state["financiar_for_client"] = client_id
                    st.rerun()
                if c4.button("📎", key=f"m_att_{client_id}"):
                    close_all_modals()
                    st.session_state["show_atasamente_for"] = client_id
                    st.session_state["show_atasamente_lucrare_id"] = None
                    st.session_state["show_atasamente_sarcina_id"] = None
                    st.rerun()
                if c5.button("🗑️", key=f"m_del_{client_id}"):
                    close_all_modals()
                    st.session_state["delete_client_id"] = client_id
                    st.rerun()
    else:
        st.markdown("<div class='clients-table'>", unsafe_allow_html=True)
        st.markdown("<div class='eco-card'>", unsafe_allow_html=True)
        st.markdown("#### CLIENȚI (DOMICILIU / SEDIU)")

        selected_id = st.session_state.get("selected_client_id")
        if selected_id is not None:
            sel_df = df[df["id"] == selected_id]
            if not sel_df.empty:
                sel = sel_df.iloc[0]
                meta = f"{str(sel.get('nume','')).upper()} • {str(sel.get('domiciliu_localitate','')).upper()} • {str(sel.get('email','')).lower()}"
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
            val_contract = _num(contract_map.get(client_id, 0.0))
            total_facturat = _num(facturat_map.get(client_id, 0.0))
            sold = _num(solduri_map.get(client_id, 0.0))

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
                      <div class="clip">{str(row.get('domiciliu_judet','')).upper()}</div>
                      <div class="clip">{str(row.get('domiciliu_localitate','')).upper()}</div>
                      <div class="clip">{str(row.get('domiciliu_strada','')).upper()}</div>
                      <div class="clip">{str(row.get('domiciliu_numar',''))}</div>
                      <div class="clip">{format_status(row.get('status',''))}</div>
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

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

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
    export_df["VALOARE_CONTRACT"] = export_df["id"].apply(lambda cid: float(contract_map.get(int(cid), 0.0) or 0.0))
    export_df["FACTURAT"] = export_df["id"].apply(lambda cid: float(facturat_map.get(int(cid), 0.0) or 0.0))
    export_df["SOLD"] = export_df["id"].apply(lambda cid: float(solduri_map.get(int(cid), 0.0) or 0.0))

    cols_export = [
        "id",
        "nume",
        "email",
        "telefon",
        "status",
        "domiciliu_judet",
        "domiciliu_localitate",
        "domiciliu_strada",
        "domiciliu_numar",
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
            "domiciliu_judet": "JUDET_DOMICILIU",
            "domiciliu_localitate": "LOCALITATE_DOMICILIU",
            "domiciliu_strada": "STRADA_DOMICILIU",
            "domiciliu_numar": "NUMAR_DOMICILIU",
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
            file_name=make_export_filename("CLIENTI", ext="xlsx"),
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key="export_excel_clienti",
        )
    with export_cols[1]:
        st.download_button(
            label="💾 EXPORT CSV",
            data=csv_data,
            file_name=make_export_filename("CLIENTI", ext="csv"),
            mime="text/csv",
            key="export_csv_clienti",
        )