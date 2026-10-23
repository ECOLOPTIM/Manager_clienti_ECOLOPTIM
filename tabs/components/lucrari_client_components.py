import streamlit as st
import pandas as pd
from datetime import datetime
import os
import db.db as db

from config.documents_config import TEMPLATE_MAP
from utils.utils_documents import (
    safe_str,
    safe_filename_part,
    split_team,
    join_team,
    atasament_exists,
    require_docxtpl,
    require_word_pdf,
    render_docx,
    docx_bytes_to_pdf_bytes_via_word,
)
from utils.utils_excel import render_excel_template
from config.excel_mappings import SITUATIE_PLATA_BRANSAMENT_CONFIG
from utils.utils_status import format_status

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
    "Proiect IUGN",
    "Revizie IUGN",
]
RESPONSABILI = ["", "Buruiana Gelu", "Enache Doru Lucian", "Bejan Marlena", "Nourescu Alexandra", "Poitasu Florinel"]
MUNCITORI = [
    "ISAIEA ADRIAN",
    "CERNAT STEFANICA",
    "VASILACHE ION",
    "ISAIEA GHEORGHE",
    "JOSAN CORNEL",
    "LOVIN CRISTIAN-CORNELIU",
]
TIPURI_CU_DATE_DGSR = [
    "Bransament nou prin DGSR",
    "Bransament nou cu OE client",
    "Extindere retea",
    "Extindere retea cu bransament",
]
TIPURI_CU_PIF = [
    "Instalatie de utilizare noua",
    "Suplimentare debit instalat",
    "Bransament nou prin DGSR",
    "Bransament nou cu OE client",
    "Extindere retea",
    "Extindere retea cu bransament",
]
STATUS_FLOW = ["OFERTAT", "CONTRACTAT", "PROGRAMAT", "EXECUTAT", "FINALIZAT", "ÎNCHIS"]
PREFIX = "lucrari_client_"


def allowed_next_statuses(current_status: str):
    s = str(current_status or "").strip().upper()
    if s not in STATUS_FLOW:
        return STATUS_FLOW
    idx = STATUS_FLOW.index(s)
    allowed = [STATUS_FLOW[idx]]
    if idx - 1 >= 0:
        allowed.insert(0, STATUS_FLOW[idx - 1])
    if idx + 1 < len(STATUS_FLOW):
        allowed.append(STATUS_FLOW[idx + 1])
    return allowed


def is_valid_status_transition(old_status: str, new_status: str) -> bool:
    old_s = str(old_status or "").strip().upper()
    new_s = str(new_status or "").strip().upper()
    if old_s not in STATUS_FLOW or new_s not in STATUS_FLOW:
        return True
    old_idx = STATUS_FLOW.index(old_s)
    new_idx = STATUS_FLOW.index(new_s)
    return new_idx in {old_idx, old_idx - 1, old_idx + 1}


def render_lucrari_list(client_id: int, df: pd.DataFrame):
    st.markdown("#### Toate lucrările acestui client")
    if df.empty:
        st.info("Nu există lucrări pentru acest client/filtru.")
        return

    pagekey = f"{PREFIX}page_{client_id}"
    if pagekey not in st.session_state:
        st.session_state[pagekey] = 1

    PAGE_SIZE = 10
    total_pages = ((len(df) - 1) // PAGE_SIZE) + 1 if not df.empty else 1
    st.session_state[pagekey] = max(1, min(st.session_state[pagekey], total_pages))

    nav = st.columns([2, 1, 2])
    if nav[0].button("⏮️ Pagina anterioară", key=f"{PREFIX}prev_{client_id}"):
        if st.session_state[pagekey] > 1:
            st.session_state[pagekey] -= 1
            st.rerun()
    nav[1].markdown(
        f"<div style='text-align:center; font-weight:bold;'>Pagina {st.session_state[pagekey]} din {total_pages}</div>",
        unsafe_allow_html=True,
    )
    if nav[2].button("Pagina următoare ⏭️", key=f"{PREFIX}next_{client_id}"):
        if st.session_state[pagekey] < total_pages:
            st.session_state[pagekey] += 1
            st.rerun()

    total_lucrari = len(df)
    total_valoare = float(df["valoare_contractata"].fillna(0).sum()) if "valoare_contractata" in df.columns else 0.0
    total_finalizate = int((df["status"].astype(str).str.upper() == "FINALIZAT").sum()) if "status" in df.columns else 0

    k1, k2, k3 = st.columns(3)
    k1.metric("Lucrări afișate", total_lucrari)
    k2.metric("Valoare totală", f"{total_valoare:,.2f} RON")
    k3.metric("Finalizate", total_finalizate)

    start = (st.session_state[pagekey] - 1) * PAGE_SIZE
    stop = st.session_state[pagekey] * PAGE_SIZE
    df_page = df.iloc[start:stop]

    head = st.columns([3, 2.2, 2, 2, 1.5, 1.5, 1.5, 2, 1, 1, 1, 1])
    header = [
        "TIP LUCRARE", "STATUS", "RESPONSABIL", "VALOARE (RON cu TVA)",
        "DATA CONTRACT", "DATA EXECUȚIE", "DATA PIF", "OBSERVAȚII",
        "📄", "🗂", "✏️", "🗑️",
    ]
    for h, txt in zip(head, header):
        h.markdown(f"**{txt}**")

    for _, row in df_page.iterrows():
        c = st.columns([3, 2.2, 2, 2, 1.5, 1.5, 1.5, 2, 1, 1, 1, 1])

        c[0].write(row["tip_lucrare"])
        c[1].write(format_status(row["status"]))
        c[2].write(row.get("responsabil", ""))

        val = row.get("valoare_contractata", "")
        val = f"{val:,.2f}" if pd.notnull(val) and val != "" else ""
        c[3].write(val)

        c[4].write(str(row.get("data_contract", "") or "").strip())
        c[5].write(str(row.get("data_programare", "") or "").strip())
        c[6].write(str(row.get("data_programare_pif", "") or "").strip())
        c[7].write(row.get("observatii", ""))

        if c[8].button("📄", key=f"{PREFIX}doc_{row['id']}"):
            st.session_state[f"{PREFIX}doc_lucrare_id_{client_id}"] = int(row["id"])
            st.rerun()

        if c[9].button("🗂", key=f"{PREFIX}flow_{row['id']}"):
            st.session_state[f"{PREFIX}flow_lucrare_id_{client_id}"] = int(row["id"])
            st.rerun()

        if c[10].button("✏️", key=f"{PREFIX}edit_{row['id']}"):
            # Explicitly opening an editor starts a fresh form, including widgets.
            suffix = f"_{int(row['id'])}_{client_id}"
            for key in list(st.session_state):
                if key.startswith(f"{PREFIX}edit_") and key.endswith(suffix):
                    del st.session_state[key]
            st.session_state[f"{PREFIX}edit_lucrare_id_{client_id}"] = int(row["id"])
            st.session_state.pop(f"{PREFIX}edit_snapshot_{client_id}", None)
            st.session_state.pop(f"{PREFIX}edit_conflict_{client_id}", None)
            st.rerun()

        if c[11].button("🗑️", key=f"{PREFIX}del_{row['id']}"):
            st.session_state[f"{PREFIX}del_lucrare_id_{client_id}"] = int(row["id"])
            st.rerun()


def render_documente_panel(
    user: str,
    client_id: int,
    client: pd.Series,
    ensure_nr_ordin_fn,
    ensure_nr_contract_fn,
    build_adresa_obiectiv_fn,
    validate_excel_lucrare_fields_fn,
    build_situatie_plata_cell_values_fn,
):
    doc_key = f"{PREFIX}doc_lucrare_id_{client_id}"
    if not st.session_state.get(doc_key):
        return

    lucrare_id = int(st.session_state[doc_key])
    lucrare = db.get_lucrare(lucrare_id)
    if not lucrare:
        st.error("Lucrarea nu mai există.")
        return


    st.markdown("---")
    st.subheader(f"📄 Documente pentru lucrare ID {lucrare_id}")

    doc_type_key = f"{PREFIX}doc_type_{client_id}_{lucrare_id}"
    chosen_type = st.selectbox("Alege template", list(TEMPLATE_MAP.keys()), key=doc_type_key)
    template_path = TEMPLATE_MAP[chosen_type]

    is_os = chosen_type == "🧾 OS (Ordin serviciu)"
    is_contract = chosen_type == "📄 Contract execuție branș. gaze"
    is_mandat = chosen_type == "📝 Contract mandat"
    is_adresa1 = chosen_type == "Adresa inaintare Distrigaz (1)"
    is_excel_situatie_plata = chosen_type == "📊 Situație plată branșament"

    contact_key = f"{PREFIX}dist_contact_{client_id}_{lucrare_id}"
    cerere_key = f"{PREFIX}dist_cerere_{client_id}_{lucrare_id}"
    st.session_state.setdefault(contact_key, "")
    st.session_state.setdefault(cerere_key, "")

    if is_adresa1:
        c_inp = st.columns([2, 3])
        st.session_state[contact_key] = c_inp[0].text_input(
            "În atenția (nume persoană)",
            value=st.session_state[contact_key],
            key=f"{contact_key}_input",
        )
        st.session_state[cerere_key] = c_inp[1].text_input(
            "Nr. cerere racordare",
            value=st.session_state[cerere_key],
            key=f"{cerere_key}_input",
        )

    pret1_key = f"{PREFIX}pret1_{client_id}_{lucrare_id}"
    pret2_key = f"{PREFIX}pret2_{client_id}_{lucrare_id}"
    pret3_key = f"{PREFIX}pret3_{client_id}_{lucrare_id}"
    st.session_state.setdefault(pret1_key, 2550.00)
    st.session_state.setdefault(pret2_key, 58.39)
    st.session_state.setdefault(pret3_key, 6852.00)

    if not os.path.exists(template_path):
        st.error(f"Nu găsesc template-ul: {template_path}")
        return

    def build_context() -> dict:
        valoare_tva = float(lucrare.get("valoare_contractata") or 0)
        valoare_fara_tva = (valoare_tva / 1.21) if valoare_tva else 0.0
        avans = float(lucrare.get("avans") or 0)

        ctx = {
            "data_emitere": datetime.now().strftime("%d.%m.%Y"),
            "lucrare_id": str(lucrare_id),
            "executant_denumire": "ECOLOPTIM SRL",
            "executant_sediu": "Str. Traian, Nr.77, Bl.A1, Sc.1, Ap.3",
            "executant_cui": "RO17199758",
            "executant_regcom": "J17/255/2005",
            "executant_iban": "RO43RZBR0000060008480911",
            "executant_banca": "Raiffeisen Bank",
            "executant_reprezentant": "BURUIANA GELU",

            "beneficiar_nume": safe_str(client.get("nume")),
            "beneficiar_localitate": safe_str(client.get("domiciliu_localitate")),
            "beneficiar_judet": safe_str(client.get("domiciliu_judet")),
            "beneficiar_strada": safe_str(client.get("domiciliu_strada")),
            "beneficiar_numar": safe_str(client.get("domiciliu_numar")),
            "beneficiar_cnp": safe_str(client.get("cnp")),
            "beneficiar_ci_serie": safe_str(client.get("ci_serie")),
            "beneficiar_ci_nr": safe_str(client.get("ci_numar")),
            "beneficiar_ci_emitent": safe_str(client.get("ci_emitent")),
            "beneficiar_ci_data": safe_str(client.get("ci_data")),

            "valoare_tva": f"{valoare_tva:.2f}",
            "valoare_fara_tva": f"{valoare_fara_tva:.2f}",
            "avans": f"{avans:.2f}",

            "client_nume": safe_str(client.get("nume")),
            "client_telefon": safe_str(client.get("telefon")),
            "client_email": safe_str(client.get("email")),
            "adresa_judet": safe_str(lucrare.get("adresa_judet")),
            "adresa_localitate": safe_str(lucrare.get("adresa_localitate")),
            "adresa_strada": safe_str(lucrare.get("adresa_strada")),
            "adresa_numar": safe_str(lucrare.get("adresa_numar")),
            "adresa_bloc": safe_str(lucrare.get("adresa_bloc")),
            "adresa_apartament": safe_str(lucrare.get("adresa_apartament")),
            "data_programare": safe_str(lucrare.get("data_programare")),
            "interval_orar": safe_str(lucrare.get("interval_orar")),
            "responsabil": safe_str(lucrare.get("responsabil")),
            "echipa": safe_str(lucrare.get("echipa")),
            "sef_echipa": safe_str(lucrare.get("sef_echipa")),
            "tip_lucrare": safe_str(lucrare.get("tip_lucrare")),
            "descriere": safe_str(lucrare.get("descriere")),
            "observatii": safe_str(lucrare.get("observatii")),
        }

        if is_os:
            ctx["nr_ordin"] = ensure_nr_ordin_fn(lucrare_id)
        if is_contract:
            ctx["nr_contract"] = ensure_nr_contract_fn(lucrare_id)
        if is_adresa1:
            ctx["persoana_contact"] = safe_str(st.session_state.get(contact_key, ""))
            ctx["nr_cerere_racordare"] = safe_str(st.session_state.get(cerere_key, ""))

        return ctx

    def build_filename(ext: str) -> str:
        safe_client = safe_filename_part(client.get("nume"), max_len=50)
        if is_os:
            return f"{ensure_nr_ordin_fn(lucrare_id)}_L-{lucrare_id}_{safe_client}.{ext}"
        if is_contract:
            return f"{ensure_nr_contract_fn(lucrare_id)}_L-{lucrare_id}_{safe_client}.{ext}"
        if is_mandat:
            return f"L-{lucrare_id}_CONTRACT_MANDAT_{safe_client}.{ext}"
        if is_adresa1:
            return f"L-{lucrare_id}_ADRESA1_DIST_{safe_client}.{ext}"
        if is_excel_situatie_plata:
            return f"L-{lucrare_id}_SITUATIE_PLATA_BRANSAMENT_{safe_client}.{ext}"

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_doc = safe_filename_part(chosen_type, max_len=40)
        return f"L-{lucrare_id}_{safe_client}_{safe_doc}_{ts}.{ext}"

    if is_excel_situatie_plata:
        x1, _, _ = st.columns([1.4, 1.4, 3])
        if x1.button("Generează Excel", key=f"{PREFIX}gen_xlsx_{client_id}_{lucrare_id}"):
            lipsa = validate_excel_lucrare_fields_fn(lucrare)
            if lipsa:
                st.error("Completează câmpurile obligatorii: " + ", ".join(lipsa))
                st.stop()

            xlsx_bytes = render_excel_template(
                template_path,
                build_situatie_plata_cell_values_fn(
                    client=dict(client),
                    lucrare=lucrare,
                    adresa_obiectiv=build_adresa_obiectiv_fn(lucrare),
                    pret1=float(st.session_state.get(pret1_key, 0)),
                    pret2=float(st.session_state.get(pret2_key, 0)),
                    pret3=float(st.session_state.get(pret3_key, 0)),
                ),
                sheet_name=SITUATIE_PLATA_BRANSAMENT_CONFIG["sheet_name"],
            )
            filename_xlsx = build_filename("xlsx")
            db.save_atasament(int(client_id), filename_xlsx, user, xlsx_bytes, lucrare_id=int(lucrare_id), sarcina_id=None)
            st.success(f"Excel salvat: {filename_xlsx}")
            st.download_button(
                "⬇️ Descarcă Excel",
                data=xlsx_bytes,
                file_name=filename_xlsx,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
    else:
        d1, d2, _ = st.columns([1.3, 1.3, 3])

        if d1.button("Generează DOCX", key=f"{PREFIX}gen_docx_{client_id}_{lucrare_id}"):
            if not require_docxtpl():
                st.stop()
            filename_docx = build_filename("docx")
            if (is_os or is_contract) and atasament_exists(db, int(client_id), filename_docx, lucrare_id=int(lucrare_id), sarcina_id=None):
                st.warning("Documentul există deja pentru această lucrare.")
                st.stop()
            docx_bytes = render_docx(template_path, build_context())
            db.save_atasament(int(client_id), filename_docx, user, docx_bytes, lucrare_id=int(lucrare_id), sarcina_id=None)
            st.success(f"DOCX salvat: {filename_docx}")
            st.download_button("⬇️ Descarcă DOCX", data=docx_bytes, file_name=filename_docx, mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        if d2.button("Generează PDF", key=f"{PREFIX}gen_pdf_{client_id}_{lucrare_id}"):
            if not require_docxtpl() or not require_word_pdf():
                st.stop()
            filename_pdf = build_filename("pdf")
            if (is_os or is_contract) and atasament_exists(db, int(client_id), filename_pdf, lucrare_id=int(lucrare_id), sarcina_id=None):
                st.warning("PDF-ul există deja pentru această lucrare.")
                st.stop()
            docx_bytes = render_docx(template_path, build_context())
            pdf_bytes = docx_bytes_to_pdf_bytes_via_word(
                docx_bytes,
                base_name=safe_filename_part(os.path.splitext(filename_pdf)[0], max_len=80),
            )
            db.save_atasament(int(client_id), filename_pdf, user, pdf_bytes, lucrare_id=int(lucrare_id), sarcina_id=None)
            st.success(f"PDF salvat: {filename_pdf}")
            st.download_button("⬇️ Descarcă PDF", data=pdf_bytes, file_name=filename_pdf, mime="application/pdf")

    cclose = st.columns([1.4, 4.6])[0]
    if cclose.button("Închide documente", key=f"{PREFIX}close_docs_{client_id}_{lucrare_id}"):
        st.session_state.pop(doc_key, None)
        st.rerun()


def render_flux_birou_panel(user: str, client_id: int):
    flow_key = f"{PREFIX}flow_lucrare_id_{client_id}"
    if not st.session_state.get(flow_key):
        return

    lucrare_id = int(st.session_state[flow_key])
    lucrare = db.get_lucrare(lucrare_id)
    if not lucrare:
        st.error("Lucrarea nu mai există.")
        return

    from db.iugn_rules import WORK_TYPE
    if lucrare.get('tip_lucrare') == WORK_TYPE:
        from tabs.components.iugn_panel import render
        render(lucrare_id, client_id)
        if st.button('Inchide fluxul', key=f'iugn_close_{client_id}_{lucrare_id}'):
            st.session_state.pop(flow_key, None)
            st.rerun()
        return

    st.markdown("---")
    st.subheader(f"🗂 Flux birou pentru lucrare ID {lucrare_id}")
    st.caption("Regulă: se lucrează în lanț — doar prima sarcină nefinalizată este editabilă.")

    df_s = db.lista_sarcini_lucrare(int(lucrare_id))
    if df_s is None or df_s.empty:
        st.info("Nu există sarcini pentru această lucrare (fluxul nu a fost inițializat).")
        cclose = st.columns([1.4, 4.6])[0]
        if cclose.button("Închide flux birou", key=f"{PREFIX}close_flow_empty_{client_id}_{lucrare_id}"):
            st.session_state.pop(flow_key, None)
            st.rerun()
        return

    def _is_finalizat(x: str) -> bool:
        return str(x or "").strip().upper() == "FINALIZAT"

    def _ordine_val(r):
        try:
            if pd.notnull(r.get("ordine")):
                return int(r.get("ordine"))
        except Exception:
            pass
        return int(r.get("id"))

    def _first_not_finalizat_id(df_sarcini: pd.DataFrame):
        tmp = df_sarcini.copy()
        tmp["__ord"] = tmp.apply(_ordine_val, axis=1)
        tmp = tmp.sort_values("__ord", ascending=True)
        nf = tmp[~tmp["status"].apply(_is_finalizat)]
        if nf.empty:
            return None
        return int(nf.iloc[0]["id"])

    def _fmt_task_line(r, current_id: int, first_nf_id):
        ordv = r.get("ordine")
        ord_txt = str(int(ordv)) if pd.notnull(ordv) else str(int(r.get("id")))
        tid = int(r["id"])
        tip = str(r.get("tip_sarcina", ""))
        status = str(r.get("status", ""))

        if _is_finalizat(status):
            icon = "✅"
        else:
            if first_nf_id is not None and tid == first_nf_id:
                icon = "⏳"
            else:
                icon = "🔒"

        cur = "👉 " if tid == int(current_id) else "   "
        due = str(r.get("data_scadenta") or "").strip()
        due_txt = f" | termen: {due}" if due else ""
        return f"{cur}{icon} [{ord_txt}] #{tid} — {tip} — {status}{due_txt}"

    total = int(len(df_s))
    done = int(df_s["status"].apply(_is_finalizat).sum())
    pct = (done / total) if total else 0.0
    st.progress(pct, text=f"Progres: {done}/{total} sarcini finalizate")

    first_nf_id = _first_not_finalizat_id(df_s)
    if first_nf_id is None:
        st.success("✅ Toate sarcinile sunt FINALIZATE pentru această lucrare.")

    key_sel = f"{PREFIX}task_sel_{client_id}_{lucrare_id}"
    pending_key = f"{PREFIX}pending_task_id_{client_id}_{lucrare_id}"

    sarcini_opts = []
    for _, r in df_s.iterrows():
        sarcini_opts.append(f"#{int(r['id'])} — {r.get('tip_sarcina','')} — [{r.get('status','')}]")

    if st.session_state.get(pending_key) is not None:
        target_id = int(st.session_state[pending_key])
        for opt in sarcini_opts:
            if opt.startswith(f"#{target_id} "):
                st.session_state[key_sel] = opt
                break
        st.session_state.pop(pending_key, None)
    elif key_sel not in st.session_state:
        if first_nf_id is not None:
            for opt in sarcini_opts:
                if opt.startswith(f"#{int(first_nf_id)} "):
                    st.session_state[key_sel] = opt
                    break
        else:
            st.session_state[key_sel] = sarcini_opts[0]

    sel = st.selectbox(
        "Alege sarcina (poți vedea orice, dar editezi doar următoarea disponibilă)",
        sarcini_opts,
        key=key_sel
    )
    sarcina_id = int(sel.split("—")[0].strip().replace("#", ""))
    sarcina_row = df_s[df_s["id"] == sarcina_id].iloc[0]
    is_editable = (first_nf_id is None) or (int(sarcina_id) == int(first_nf_id))

    with st.expander("📋 Pașii din flux (status + blocări)", expanded=True):
        lines = []
        for _, r in df_s.iterrows():
            lines.append(_fmt_task_line(r, current_id=sarcina_id, first_nf_id=first_nf_id))
        st.code("\n".join(lines), language="text")

    if not is_editable and first_nf_id is not None:
        must_row = df_s[df_s["id"] == first_nf_id].iloc[0]
        ordv = must_row.get("ordine")
        ord_txt = str(int(ordv)) if pd.notnull(ordv) else str(int(must_row.get("id")))
        st.warning(f"🔒 Sarcina selectată este blocată. Trebuie făcută mai întâi: [{ord_txt}] #{int(must_row['id'])} — {must_row.get('tip_sarcina','')}")

    st.markdown("---")

    c1, c2, c3 = st.columns([2, 2, 3])
    statuses = ["NOU", "IN_LUCRU", "BLOCAT", "FINALIZAT"]
    cur_status = str(sarcina_row.get("status") or "NOU")

    status_nou = c1.selectbox(
        "Status sarcină",
        statuses,
        index=statuses.index(cur_status) if cur_status in statuses else 0,
        key=f"{PREFIX}task_status_{sarcina_id}",
        disabled=not is_editable,
    )

    resp_curent = str(sarcina_row.get("responsabil") or "").strip()
    resp_opts = list(RESPONSABILI)
    if resp_curent and resp_curent not in resp_opts:
        resp_opts = [resp_curent] + resp_opts

    responsabil = c2.selectbox(
        "Responsabil (opțional)",
        resp_opts,
        index=resp_opts.index(resp_curent) if resp_curent in resp_opts else 0,
        key=f"{PREFIX}task_resp_{sarcina_id}",
        disabled=not is_editable,
    )

    existing_due = None
    try:
        v = str(sarcina_row.get("data_scadenta") or "").strip()
        if v:
            existing_due = pd.to_datetime(v, errors="coerce").date()
    except Exception:
        existing_due = None

    data_scadenta_date = c3.date_input(
        "Termen (opțional)",
        value=existing_due,
        key=f"{PREFIX}task_due_{sarcina_id}",
        disabled=not is_editable,
    )
    fara_termen = c3.checkbox(
        "Fără termen",
        value=(existing_due is None),
        key=f"{PREFIX}task_due_none_{sarcina_id}",
        disabled=not is_editable,
    )
    data_scadenta = "" if fara_termen else str(data_scadenta_date)

    obs_task = st.text_area(
        "Observații sarcină",
        value=str(sarcina_row.get("observatii") or ""),
        height=80,
        key=f"{PREFIX}task_obs_{sarcina_id}",
        disabled=not is_editable,
    )

    btn_cols = st.columns([1.6, 2.2, 3.2])

    if btn_cols[0].button("💾 Salvează sarcina", key=f"{PREFIX}task_save_{sarcina_id}", disabled=not is_editable):
        db.update_sarcina(
            int(sarcina_id),
            status=status_nou,
            responsabil=responsabil,
            data_scadenta=data_scadenta,
            observatii=obs_task,
        )
        st.success("Sarcina a fost salvată.")
        st.rerun()

    if btn_cols[1].button("✅ Finalizează & treci la următoarea", key=f"{PREFIX}task_finish_next_{sarcina_id}", disabled=not is_editable):
        db.update_sarcina(
            int(sarcina_id),
            status="FINALIZAT",
            responsabil=responsabil,
            data_scadenta=data_scadenta,
            observatii=obs_task,
        )
        df_s2 = db.lista_sarcini_lucrare(int(lucrare_id))
        new_first = _first_not_finalizat_id(df_s2)

        if new_first is not None:
            st.session_state[pending_key] = int(new_first)
            st.success("Finalizat. Am trecut la următoarea sarcină disponibilă.")
        else:
            st.success("Finalizat. ✅ Toate sarcinile sunt FINALIZATE.")
        st.rerun()

    btn_cols[2].caption("În modul strict, doar următoarea sarcină (⏳) este editabilă.")

    st.markdown("---")
    st.markdown("### 🔢 Număr înregistrare")

    descr = st.text_input(
        "Descriere înregistrare (ex: Depunere acte / Trimis email / Ridicat documente)",
        key=f"{PREFIX}reg_descr_{sarcina_id}",
    )

    if st.button("➕ Generează nr. înregistrare", key=f"{PREFIX}reg_gen_{sarcina_id}"):
        nr = db.adauga_inregistrare(
            int(client_id),
            int(lucrare_id),
            int(sarcina_id),
            descriere=descr,
            created_by=user,
        )
        st.success(f"Creat: {nr}")
        st.rerun()

    df_reg = db.lista_inregistrari(int(client_id), lucrare_id=int(lucrare_id), sarcina_id=int(sarcina_id))
    if df_reg is not None and not df_reg.empty:
        st.dataframe(
            df_reg[["nr_inregistrare", "data", "descriere", "created_by", "created_at"]],
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Nu există înregistrări pe această sarcină.")

    st.markdown("---")
    st.markdown("### 📎 Documente pe sarcină")

    open_cols = st.columns([1.4, 3.6])
    if open_cols[0].button("📎 Atașamente (în tab)", key=f"{PREFIX}open_task_att_{client_id}_{lucrare_id}_{sarcina_id}"):
        st.session_state.pop("lucrari_for_client", None)
        st.session_state["show_atasamente_for"] = int(client_id)
        st.session_state["show_atasamente_lucrare_id"] = int(lucrare_id)
        st.session_state["show_atasamente_sarcina_id"] = int(sarcina_id)
        st.rerun()
    open_cols[1].caption("Deschide pagina Atașamente filtrată pe lucrare + sarcină.")

    up = st.file_uploader("Încarcă document (DOCX/PDF/IMG etc.)", key=f"{PREFIX}task_up_{sarcina_id}")
    if up is not None:
        if st.button("📥 Salvează document", key=f"{PREFIX}task_up_save_{sarcina_id}"):
            db.save_atasament(
                int(client_id),
                up.name,
                user,
                up.getvalue(),
                lucrare_id=int(lucrare_id),
                sarcina_id=int(sarcina_id),
            )
            st.success("Document salvat.")
            st.rerun()

    df_att = db.lista_atasamente(int(client_id), lucrare_id=int(lucrare_id), sarcina_id=int(sarcina_id))
    if df_att is not None and not df_att.empty:
        st.dataframe(df_att[["filename", "upload_date", "uploaded_by"]], use_container_width=True, hide_index=True)
    else:
        st.info("Nu există documente atașate la această sarcină.")

    cclose = st.columns([1.4, 4.6])[0]
    if cclose.button("Închide flux birou", key=f"{PREFIX}close_flow_{client_id}_{lucrare_id}"):
        st.session_state.pop(flow_key, None)
        st.rerun()


def render_add_lucrare_form(user: str, client_id: int, client_row: pd.Series):
    if st.button("➕ Adaugă lucrare", key=f"{PREFIX}add_{client_id}"):
        st.session_state[f"{PREFIX}add_open_{client_id}"] = True

    if not st.session_state.get(f"{PREFIX}add_open_{client_id}"):
        return

    st.subheader("➕ Adăugare lucrare")
    with st.form(f"{PREFIX}form_add_{client_id}", clear_on_submit=False):
        valori = {}
        r1 = st.columns([3, 2, 2])
        valori["tip_lucrare"] = r1[0].selectbox("Tip lucrare", TIPURI_LUCRARE, key=f"{PREFIX}add_tip_{client_id}")
        valori["status"] = r1[1].selectbox("Status", ["OFERTAT", "CONTRACTAT"], key=f"{PREFIX}add_status_{client_id}")
        valori["responsabil"] = r1[2].selectbox("Responsabil", RESPONSABILI, key=f"{PREFIX}add_responsabil_{client_id}")

        status_upper = str(valori["status"]).strip().upper()
        este_contractat = status_upper == "CONTRACTAT"
        este_programat = status_upper == "PROGRAMAT"
        este_lucrare_cu_pif = valori["tip_lucrare"] in TIPURI_CU_PIF
        poate_edita_pif = status_upper in ("EXECUTAT", "FINALIZAT")

        r2 = st.columns(2)
        valori["valoare_contractata"] = r2[0].number_input("Valoare (RON cu TVA)", min_value=0.0, step=100.0, key=f"{PREFIX}add_val_contract_{client_id}")
        valori["avans"] = r2[1].number_input("Avans (RON)", min_value=0.0, step=100.0, key=f"{PREFIX}add_avans_{client_id}")

        r3 = st.columns(2)
        data_contract = r3[0].date_input("Dată contract", value=datetime.now().date(), key=f"{PREFIX}add_data_contract_{client_id}", disabled=not este_contractat)
        data_programare = r3[1].date_input("Dată programare execuție", value=datetime.now().date(), key=f"{PREFIX}add_data_programare_{client_id}", disabled=not este_programat)

        valori["data_contract"] = str(data_contract) if este_contractat else ""
        valori["data_programare"] = str(data_programare) if este_programat else ""

        r4 = st.columns([2, 3, 2])
        interval_orar = r4[0].text_input("Interval orar execuție", placeholder="08:00-12:00", key=f"{PREFIX}add_interval_{client_id}", disabled=not este_programat)
        echipa_sel = r4[1].multiselect("Echipă execuție", options=MUNCITORI, default=[], key=f"{PREFIX}add_echipa_{client_id}", disabled=not este_programat)
        sef_echipa_sel = r4[2].selectbox("Șef de echipă execuție", options=[""] + MUNCITORI, key=f"{PREFIX}add_sef_{client_id}", disabled=not este_programat)

        valori["interval_orar"] = interval_orar if este_programat else ""
        valori["echipa"] = join_team(echipa_sel) if este_programat else ""
        valori["sef_echipa"] = sef_echipa_sel if este_programat else ""

        if este_lucrare_cu_pif:
            st.markdown("### Programare PIF")
            rpif = st.columns([2, 2, 3, 2])
            data_programare_pif = rpif[0].date_input("Dată programare PIF", value=datetime.now().date(), key=f"{PREFIX}add_data_programare_pif_{client_id}", disabled=not poate_edita_pif)
            interval_orar_pif = rpif[1].text_input("Interval orar PIF", placeholder="08:00-12:00", key=f"{PREFIX}add_interval_pif_{client_id}", disabled=not poate_edita_pif)
            echipa_pif_sel = rpif[2].multiselect("Echipă PIF", options=MUNCITORI, default=[], key=f"{PREFIX}add_echipa_pif_{client_id}", disabled=not poate_edita_pif)
            sef_echipa_pif_sel = rpif[3].selectbox("Șef de echipă PIF", options=[""] + MUNCITORI, key=f"{PREFIX}add_sef_pif_{client_id}", disabled=not poate_edita_pif)

            valori["data_programare_pif"] = str(data_programare_pif) if poate_edita_pif else ""
            valori["interval_orar_pif"] = interval_orar_pif if poate_edita_pif else ""
            valori["echipa_pif"] = join_team(echipa_pif_sel) if poate_edita_pif else ""
            valori["sef_echipa_pif"] = sef_echipa_pif_sel if poate_edita_pif else ""
        else:
            valori["data_programare_pif"] = ""
            valori["interval_orar_pif"] = ""
            valori["echipa_pif"] = ""
            valori["sef_echipa_pif"] = ""

        st.markdown("### Adresă lucrare (obligatoriu)")
        copy = st.checkbox("Copiază automat din 'Loc consum' al clientului", value=True, key=f"{PREFIX}add_copy_consum_{client_id}")
        defv = lambda k: safe_str(client_row.get(k)) if copy else ""

        rAdr = st.columns([1, 2, 3, 1, 1, 1])
        valori["adresa_judet"] = rAdr[0].text_input("Județ", value=defv("consum_judet"), key=f"{PREFIX}add_adr_j_{client_id}")
        valori["adresa_localitate"] = rAdr[1].text_input("Localitate", value=defv("consum_localitate"), key=f"{PREFIX}add_adr_l_{client_id}")
        valori["adresa_strada"] = rAdr[2].text_input("Stradă", value=defv("consum_strada"), key=f"{PREFIX}add_adr_s_{client_id}")
        valori["adresa_numar"] = rAdr[3].text_input("Număr", value=defv("consum_numar"), key=f"{PREFIX}add_adr_n_{client_id}")
        valori["adresa_bloc"] = rAdr[4].text_input("Bloc", value=defv("consum_bloc"), key=f"{PREFIX}add_adr_b_{client_id}")
        valori["adresa_apartament"] = rAdr[5].text_input("Apartament", value=defv("consum_apartament"), key=f"{PREFIX}add_adr_a_{client_id}")

        if valori["tip_lucrare"] in TIPURI_CU_DATE_DGSR:
            st.markdown("### Date fixe DGSR / extindere")
            d1, d2 = st.columns(2)
            valori["cod_atr"] = d1.text_input("Cod ATR", key=f"{PREFIX}add_cod_atr_{client_id}")
            valori["executant"] = d2.text_input("Executant", value="ECOLOPTIM S.R.L.", key=f"{PREFIX}add_executant_{client_id}")

            d3, d4 = st.columns(2)
            valori["element_sda"] = d3.text_input("Element SDA", key=f"{PREFIX}add_element_sda_{client_id}")
            valori["comanda_aprovizionare"] = d4.text_input("Comandă aprovizionare", key=f"{PREFIX}add_cmd_aprov_{client_id}")

            d5, d6 = st.columns(2)
            valori["diriginte_santier"] = d5.text_input("Diriginte de șantier", key=f"{PREFIX}add_diriginte_{client_id}")
            valori["contract_prestari_servicii"] = d6.text_input("Nr. contract prestări servicii", key=f"{PREFIX}add_contract_ps_{client_id}")

            d7, _ = st.columns(2)
            valori["numar_conventie_tehnica"] = d7.text_input("Număr convenție tehnică", key=f"{PREFIX}add_conv_tehnica_{client_id}")
        else:
            valori["cod_atr"] = ""
            valori["executant"] = ""
            valori["element_sda"] = ""
            valori["comanda_aprovizionare"] = ""
            valori["diriginte_santier"] = ""
            valori["contract_prestari_servicii"] = ""
            valori["numar_conventie_tehnica"] = ""

        valori["observatii"] = st.text_area("Observații", key=f"{PREFIX}add_obs_{client_id}", height=90)
        valori["descriere"] = st.text_area("Descriere lucrare", key=f"{PREFIX}add_descriere_{client_id}", height=90)

        b1, b2, _ = st.columns([1.3, 1.3, 6])
        submit = b1.form_submit_button("💾 Salvează lucrarea", use_container_width=True)
        cancel = b2.form_submit_button("⛔ Renunță", use_container_width=True)

        if cancel:
            st.session_state[f"{PREFIX}add_open_{client_id}"] = False
            st.rerun()

        if submit:
            required = [("Județ", valori.get("adresa_judet")), ("Localitate", valori.get("adresa_localitate")), ("Stradă", valori.get("adresa_strada")), ("Număr", valori.get("adresa_numar"))]
            missing = [label for label, v in required if not str(v or "").strip()]
            if missing:
                st.error("Completează câmpurile obligatorii la Adresă lucrare: " + ", ".join(missing))
                st.stop()

            if float(valori.get("avans", 0) or 0) > float(valori.get("valoare_contractata", 0) or 0):
                st.error("Avansul nu poate fi mai mare decât valoarea contractată.")
                st.stop()

            sef = (valori.get("sef_echipa") or "").strip()
            team = split_team(valori.get("echipa"))
            if sef and sef not in team:
                team.append(sef)
                valori["echipa"] = join_team(team)

            sef_pif = (valori.get("sef_echipa_pif") or "").strip()
            team_pif = split_team(valori.get("echipa_pif"))
            if sef_pif and sef_pif not in team_pif:
                team_pif.append(sef_pif)
                valori["echipa_pif"] = join_team(team_pif)

            valori["client_id"] = int(client_id)
            valori["created_by"] = user
            db.adauga_lucrare(valori)

            st.success("Lucrare adăugată cu succes!")
            st.session_state[f"{PREFIX}add_open_{client_id}"] = False
            st.rerun()


def render_edit_lucrare_form(client_id: int, df: pd.DataFrame):
    edit_key = f"{PREFIX}edit_lucrare_id_{client_id}"
    if not st.session_state.get(edit_key):
        return

    lucrare_id = int(st.session_state[edit_key])
    snapshot_key = f"{PREFIX}edit_snapshot_{client_id}"
    conflict_key = f"{PREFIX}edit_conflict_{client_id}"
    snapshot = st.session_state.get(snapshot_key)
    if snapshot is None or int(snapshot["id"]) != lucrare_id:
        matches = df[df["id"] == lucrare_id]
        if matches.empty:
            st.warning("Lucrarea nu mai există. Revino la lista de lucrări.")
            return
        snapshot = matches.iloc[0].to_dict()
        st.session_state[snapshot_key] = snapshot
    # Streamlit reruns on submit: keep the ORIGINAL row/revision, not the new df.
    row = snapshot
    if st.session_state.get(conflict_key):
        st.error(st.session_state[conflict_key])
        if st.button("Reîncarcă lucrarea (renunță la modificările nesalvate)",
                     key=f"{PREFIX}reload_edit_{lucrare_id}_{client_id}"):
            suffix = f"_{lucrare_id}_{client_id}"
            for key in list(st.session_state):
                if key.startswith(f"{PREFIX}edit_") and key.endswith(suffix):
                    del st.session_state[key]
            st.session_state.pop(snapshot_key, None)
            st.session_state.pop(conflict_key, None)
            st.rerun()

    st.subheader(f"✏️ Editare lucrare — {safe_str(row.get('tip_lucrare'))}")
    from db.iugn_rules import WORK_TYPE
    from db import iugn
    if row.get('tip_lucrare') == WORK_TYPE and iugn.get(lucrare_id) is not None:
        from tabs.components.iugn_panel import render_work_details
        render_work_details(row, client_id, edit_key, snapshot_key, conflict_key)
        return
    with st.form(f"{PREFIX}form_edit_{lucrare_id}_{client_id}", clear_on_submit=False):
        valori = {}

        r1 = st.columns([3, 2, 2])
        valori["tip_lucrare"] = r1[0].selectbox("Tip lucrare", TIPURI_LUCRARE, index=TIPURI_LUCRARE.index(row["tip_lucrare"]) if row["tip_lucrare"] in TIPURI_LUCRARE else 0, key=f"{PREFIX}edit_tip_{lucrare_id}_{client_id}")

        status_curent_db = str(row.get("status") or "").strip().upper()
        status_edit_options = allowed_next_statuses(status_curent_db)
        valori["status"] = r1[1].selectbox("Status", status_edit_options, index=status_edit_options.index(status_curent_db) if status_curent_db in status_edit_options else 0, key=f"{PREFIX}edit_status_{lucrare_id}_{client_id}")

        valori["responsabil"] = r1[2].selectbox(
            "Responsabil",
            RESPONSABILI,
            index=RESPONSABILI.index(row.get("responsabil", RESPONSABILI[0])) if row.get("responsabil", RESPONSABILI[0]) in RESPONSABILI else 0,
            key=f"{PREFIX}edit_responsabil_{lucrare_id}_{client_id}",
        )

        status_curent = str(valori.get("status") or "").strip().upper()
        este_contractat = status_curent == "CONTRACTAT"
        este_programat = status_curent == "PROGRAMAT"
        este_lucrare_cu_pif = valori["tip_lucrare"] in TIPURI_CU_PIF
        poate_edita_pif = status_curent in ("EXECUTAT", "FINALIZAT")

        r2 = st.columns(2)
        valori["valoare_contractata"] = r2[0].number_input("Valoare (RON cu TVA)", min_value=0.0, step=100.0, value=float(row.get("valoare_contractata", 0) or 0), key=f"{PREFIX}edit_val_contract_{lucrare_id}_{client_id}")
        valori["avans"] = r2[1].number_input("Avans (RON)", min_value=0.0, step=100.0, value=float(row.get("avans", 0) or 0), key=f"{PREFIX}edit_avans_{lucrare_id}_{client_id}")

        r3 = st.columns(2)
        data_contract = r3[0].date_input("Dată contract", value=pd.to_datetime(row["data_contract"]).date() if pd.notnull(row.get("data_contract")) and str(row.get("data_contract")).strip() else datetime.now().date(), key=f"{PREFIX}edit_data_contract_{lucrare_id}_{client_id}", disabled=not este_contractat)
        data_programare = r3[1].date_input("Dată programare execuție", value=pd.to_datetime(row["data_programare"]).date() if pd.notnull(row.get("data_programare")) and str(row.get("data_programare")).strip() else datetime.now().date(), key=f"{PREFIX}edit_data_programare_{lucrare_id}_{client_id}", disabled=not este_programat)

        valori["data_contract"] = str(data_contract) if este_contractat else safe_str(row.get("data_contract"))
        valori["data_programare"] = str(data_programare) if este_programat else safe_str(row.get("data_programare"))

        r4 = st.columns([2, 3, 2])
        interval_orar = r4[0].text_input("Interval orar execuție", value=safe_str(row.get("interval_orar")), placeholder="08:00-12:00", key=f"{PREFIX}edit_interval_{lucrare_id}_{client_id}", disabled=not este_programat)
        valori["interval_orar"] = interval_orar if este_programat else safe_str(row.get("interval_orar"))

        echipa_curenta = split_team(row.get("echipa"))
        opts = list(MUNCITORI)
        for x in echipa_curenta:
            if x and x not in opts:
                opts = [x] + opts
        echipa_sel = r4[1].multiselect("Echipă execuție", options=opts, default=[x for x in echipa_curenta if x in opts], key=f"{PREFIX}edit_echipa_{lucrare_id}_{client_id}", disabled=not este_programat)
        valori["echipa"] = join_team(echipa_sel) if este_programat else safe_str(row.get("echipa"))

        sef_curent = safe_str(row.get("sef_echipa")).strip()
        sef_opts = [""] + list(MUNCITORI)
        if sef_curent and sef_curent not in sef_opts:
            sef_opts = [sef_curent] + sef_opts
        sef_echipa_sel = r4[2].selectbox("Șef de echipă execuție", options=sef_opts, index=sef_opts.index(sef_curent) if sef_curent in sef_opts else 0, key=f"{PREFIX}edit_sef_{lucrare_id}_{client_id}", disabled=not este_programat)
        valori["sef_echipa"] = sef_echipa_sel if este_programat else safe_str(row.get("sef_echipa"))

        if este_lucrare_cu_pif:
            st.markdown("### Programare PIF")
            rpif = st.columns([2, 2, 3, 2])

            data_programare_pif = rpif[0].date_input(
                "Dată programare PIF",
                value=pd.to_datetime(row["data_programare_pif"]).date() if pd.notnull(row.get("data_programare_pif")) and str(row.get("data_programare_pif")).strip() else datetime.now().date(),
                key=f"{PREFIX}edit_data_programare_pif_{lucrare_id}_{client_id}",
                disabled=not poate_edita_pif,
            )
            interval_orar_pif = rpif[1].text_input("Interval orar PIF", value=safe_str(row.get("interval_orar_pif")), placeholder="08:00-12:00", key=f"{PREFIX}edit_interval_pif_{lucrare_id}_{client_id}", disabled=not poate_edita_pif)

            echipa_pif_curenta = split_team(row.get("echipa_pif"))
            opts_pif = list(MUNCITORI)
            for x in echipa_pif_curenta:
                if x and x not in opts_pif:
                    opts_pif = [x] + opts_pif
            echipa_pif_sel = rpif[2].multiselect("Echipă PIF", options=opts_pif, default=[x for x in echipa_pif_curenta if x in opts_pif], key=f"{PREFIX}edit_echipa_pif_{lucrare_id}_{client_id}", disabled=not poate_edita_pif)

            sef_pif_curent = safe_str(row.get("sef_echipa_pif")).strip()
            sef_pif_opts = [""] + list(MUNCITORI)
            if sef_pif_curent and sef_pif_curent not in sef_pif_opts:
                sef_pif_opts = [sef_pif_curent] + sef_pif_opts
            sef_echipa_pif_sel = rpif[3].selectbox("Șef de echipă PIF", options=sef_pif_opts, index=sef_pif_opts.index(sef_pif_curent) if sef_pif_curent in sef_pif_opts else 0, key=f"{PREFIX}edit_sef_pif_{lucrare_id}_{client_id}", disabled=not poate_edita_pif)

            valori["data_programare_pif"] = str(data_programare_pif) if poate_edita_pif else safe_str(row.get("data_programare_pif"))
            valori["interval_orar_pif"] = interval_orar_pif if poate_edita_pif else safe_str(row.get("interval_orar_pif"))
            valori["echipa_pif"] = join_team(echipa_pif_sel) if poate_edita_pif else safe_str(row.get("echipa_pif"))
            valori["sef_echipa_pif"] = sef_echipa_pif_sel if poate_edita_pif else safe_str(row.get("sef_echipa_pif"))
        else:
            valori["data_programare_pif"] = ""
            valori["interval_orar_pif"] = ""
            valori["echipa_pif"] = ""
            valori["sef_echipa_pif"] = ""

        st.markdown("### Adresă lucrare (obligatoriu)")
        rAdr = st.columns([1, 2, 3, 1, 1, 1])
        valori["adresa_judet"] = rAdr[0].text_input("Județ", value=safe_str(row.get("adresa_judet")), key=f"{PREFIX}edit_adr_j_{lucrare_id}_{client_id}")
        valori["adresa_localitate"] = rAdr[1].text_input("Localitate", value=safe_str(row.get("adresa_localitate")), key=f"{PREFIX}edit_adr_l_{lucrare_id}_{client_id}")
        valori["adresa_strada"] = rAdr[2].text_input("Stradă", value=safe_str(row.get("adresa_strada")), key=f"{PREFIX}edit_adr_s_{lucrare_id}_{client_id}")
        valori["adresa_numar"] = rAdr[3].text_input("Număr", value=safe_str(row.get("adresa_numar")), key=f"{PREFIX}edit_adr_n_{lucrare_id}_{client_id}")
        valori["adresa_bloc"] = rAdr[4].text_input("Bloc", value=safe_str(row.get("adresa_bloc")), key=f"{PREFIX}edit_adr_b_{lucrare_id}_{client_id}")
        valori["adresa_apartament"] = rAdr[5].text_input("Apartament", value=safe_str(row.get("adresa_apartament")), key=f"{PREFIX}edit_adr_a_{lucrare_id}_{client_id}")

        if valori["tip_lucrare"] in TIPURI_CU_DATE_DGSR:
            st.markdown("### Date fixe DGSR / extindere")
            d1, d2 = st.columns(2)
            valori["cod_atr"] = d1.text_input("Cod ATR", value=safe_str(row.get("cod_atr")), key=f"{PREFIX}edit_cod_atr_{lucrare_id}_{client_id}")
            valori["executant"] = d2.text_input("Executant", value=safe_str(row.get("executant")) or "ECOLOPTIM S.R.L.", key=f"{PREFIX}edit_executant_{lucrare_id}_{client_id}")

            d3, d4 = st.columns(2)
            valori["element_sda"] = d3.text_input("Element SDA", value=safe_str(row.get("element_sda")), key=f"{PREFIX}edit_element_sda_{lucrare_id}_{client_id}")
            valori["comanda_aprovizionare"] = d4.text_input("Comandă aprovizionare", value=safe_str(row.get("comanda_aprovizionare")), key=f"{PREFIX}edit_cmd_aprov_{lucrare_id}_{client_id}")

            d5, d6 = st.columns(2)
            valori["diriginte_santier"] = d5.text_input("Diriginte de șantier", value=safe_str(row.get("diriginte_santier")), key=f"{PREFIX}edit_diriginte_{lucrare_id}_{client_id}")
            valori["contract_prestari_servicii"] = d6.text_input("Nr. contract prestări servicii", value=safe_str(row.get("contract_prestari_servicii")), key=f"{PREFIX}edit_contract_ps_{lucrare_id}_{client_id}")

            d7, _ = st.columns(2)
            valori["numar_conventie_tehnica"] = d7.text_input("Număr convenție tehnică", value=safe_str(row.get("numar_conventie_tehnica")), key=f"{PREFIX}edit_conv_tehnica_{lucrare_id}_{client_id}")
        else:
            valori["cod_atr"] = ""
            valori["executant"] = ""
            valori["element_sda"] = ""
            valori["comanda_aprovizionare"] = ""
            valori["diriginte_santier"] = ""
            valori["contract_prestari_servicii"] = ""
            valori["numar_conventie_tehnica"] = ""

        valori["observatii"] = st.text_area("Observații", value=safe_str(row.get("observatii")), key=f"{PREFIX}edit_obs_{lucrare_id}_{client_id}", height=90)
        valori["descriere"] = st.text_area("Descriere lucrare", value=safe_str(row.get("descriere")), key=f"{PREFIX}edit_descriere_{lucrare_id}_{client_id}", height=90)
        valori["client_id"] = int(client_id)

        b1, b2, _ = st.columns([1.3, 1.3, 6])
        submit = b1.form_submit_button("💾 Salvează modificările", use_container_width=True)
        cancel = b2.form_submit_button("⛔ Închide editarea", use_container_width=True)

        if cancel:
            del st.session_state[edit_key]
            st.session_state.pop(snapshot_key, None)
            st.session_state.pop(conflict_key, None)
            st.rerun()

        if submit:
            required = [("Județ", valori.get("adresa_judet")), ("Localitate", valori.get("adresa_localitate")), ("Stradă", valori.get("adresa_strada")), ("Număr", valori.get("adresa_numar"))]
            missing = [label for label, v in required if not str(v or "").strip()]

            status_vechi = str(row.get("status") or "").strip().upper()
            status_upper = str(valori.get("status") or "").strip().upper()

            if not is_valid_status_transition(status_vechi, status_upper):
                st.error(f"Tranziție invalidă de status: {status_vechi} → {status_upper}.")
                st.stop()
            if missing:
                st.error("Completează câmpurile obligatorii la Adresă lucrare: " + ", ".join(missing))
                st.stop()
            if float(valori.get("avans", 0) or 0) > float(valori.get("valoare_contractata", 0) or 0):
                st.error("Avansul nu poate fi mai mare decât valoarea contractată.")
                st.stop()

            sef = (valori.get("sef_echipa") or "").strip()
            team = split_team(valori.get("echipa"))
            if sef and sef not in team:
                team.append(sef)
                valori["echipa"] = join_team(team)

            sef_pif = (valori.get("sef_echipa_pif") or "").strip()
            team_pif = split_team(valori.get("echipa_pif"))
            if sef_pif and sef_pif not in team_pif:
                team_pif.append(sef_pif)
                valori["echipa_pif"] = join_team(team_pif)

            try:
                db.modifica_lucrare(lucrare_id, valori, expected_revision=int(row["revision"]))
            except db.ConcurrentWorkEditError as exc:
                st.session_state[conflict_key] = str(exc)
                st.rerun()
            st.success("Modificare salvată.")
            del st.session_state[edit_key]
            st.session_state.pop(snapshot_key, None)
            st.session_state.pop(conflict_key, None)
            st.rerun()


def render_delete_lucrare_panel(client_id: int, df: pd.DataFrame):
    del_key = f"{PREFIX}del_lucrare_id_{client_id}"
    if not st.session_state.get(del_key):
        return

    lucrare_id = int(st.session_state[del_key])
    row = df[df["id"] == lucrare_id].iloc[0]

    st.subheader("🗑️ Ștergere lucrare")
    st.error(f"EȘTI SIGUR CĂ VREI SĂ ȘTERGI LUCRAREA '{row['tip_lucrare']}' ({row['data_contract']} → {row['data_programare']})?")

    deps = db.dependinte_lucrare(lucrare_id)
    if any(int(v or 0) > 0 for v in deps.values()):
        st.warning("Această lucrare are date asociate și nu poate fi ștearsă direct: " + ", ".join(f"{k}: {v}" for k, v in deps.items() if int(v or 0) > 0))

    conf, canc = st.columns([1, 1])
    if conf.button("Confirmă ștergerea", key=f"{PREFIX}conf_del_{lucrare_id}_{client_id}"):
        try:
            db.sterge_lucrare(lucrare_id)
            st.success("Lucrare ștearsă!")
            del st.session_state[del_key]
            st.rerun()
        except Exception as e:
            st.error(str(e))

    if canc.button("Anulează", key=f"{PREFIX}cancel_del_{lucrare_id}_{client_id}"):
        del st.session_state[del_key]
        st.rerun()
