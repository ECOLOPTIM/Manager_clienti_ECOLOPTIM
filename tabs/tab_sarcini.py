import streamlit as st
import db.db as db
import pandas as pd

STATUS_SARCINA = ["Toate", "NOU", "IN_LUCRU", "BLOCAT", "FINALIZAT"]


def status_badge(status: str) -> str:
    s = str(status or "").upper().strip()
    if s == "IN_LUCRU":
        return "<span class='badge badge-in'>IN LUCRU</span>"
    if s == "BLOCAT":
        return "<span class='badge badge-bl'>BLOCAT</span>"
    if s == "FINALIZAT":
        return "<span class='badge badge-fin'>FINALIZAT</span>"
    return "<span class='badge badge-nou'>NOU</span>"


def show(user):
    st.header("📌 Sarcini — overview")

    df = db.lista_sarcini_all(filtru_status="", filtru_text="")
    if df is None or df.empty:
        st.info("Nu există sarcini.")
        return

    df = df.copy()

    for col in (
        "client_id",
        "client_nume",
        "lucrare_id",
        "lucrare_tip",
        "lucrare_status",
        "id",
        "ordine",
        "tip_sarcina",
        "status",
        "responsabil",
        "data_scadenta",
        "observatii",
    ):
        if col not in df.columns:
            df[col] = ""

    df["__ord"] = df.apply(
        lambda r: int(r["ordine"]) if pd.notnull(r.get("ordine")) else int(r["id"]),
        axis=1,
    )

    df["__due_dt"] = pd.to_datetime(df["data_scadenta"], errors="coerce")
    today = pd.Timestamp.today().normalize()

    # ----------------- Filter bar -----------------
    if "sarcini_filters_reset" not in st.session_state:
        st.session_state["sarcini_filters_reset"] = 0
    rid = st.session_state["sarcini_filters_reset"]

    st.markdown("<div class='eco-filters'>", unsafe_allow_html=True)
    fcols = st.columns([2.2, 2.2, 1.5, 3.3, 1.2])

    clienti = sorted([c for c in df["client_nume"].dropna().astype(str).unique().tolist() if c.strip()])
    tipuri = sorted([t for t in df["lucrare_tip"].dropna().astype(str).unique().tolist() if t.strip()])

    client_select = fcols[0].selectbox("Client", ["Toți"] + clienti, index=0, key=f"sarc_client_{rid}")
    tip_select = fcols[1].selectbox("Tip lucrare", ["Toate"] + tipuri, index=0, key=f"sarc_tip_{rid}")
    status_select = fcols[2].selectbox("Status sarcină", STATUS_SARCINA, index=0, key=f"sarc_status_{rid}")
    text = fcols[3].text_input("Caută (client / lucrare / sarcină / observații)", value="", key=f"sarc_text_{rid}")

    if fcols[4].button("Reset", key=f"sarc_reset_{rid}"):
        st.session_state["sarcini_filters_reset"] += 1
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

    df_f = df

    if client_select != "Toți":
        df_f = df_f[df_f["client_nume"].astype(str) == str(client_select)]
    if tip_select != "Toate":
        df_f = df_f[df_f["lucrare_tip"].astype(str) == str(tip_select)]
    if status_select != "Toate":
        df_f = df_f[df_f["status"].astype(str) == str(status_select)]
    if text.strip():
        t = text.strip().lower()
        df_f = df_f[
            df_f["client_nume"].astype(str).str.lower().str.contains(t, na=False)
            | df_f["lucrare_tip"].astype(str).str.lower().str.contains(t, na=False)
            | df_f["tip_sarcina"].astype(str).str.lower().str.contains(t, na=False)
            | df_f["observatii"].astype(str).str.lower().str.contains(t, na=False)
        ]

    if df_f.empty:
        st.info("Nu există rezultate pentru filtrele selectate.")
        return

    only_client_filter = (
        client_select != "Toți"
        and tip_select == "Toate"
        and status_select == "Toate"
        and not text.strip()
    )

    def fmt_due(row) -> str:
        raw = str(row.get("data_scadenta") or "").strip()
        dt = row.get("__due_dt", pd.NaT)
        stt = str(row.get("status") or "")
        if not raw:
            return ""
        if pd.isna(dt):
            return raw
        overdue = (dt.normalize() < today) and (stt != "FINALIZAT")
        if overdue:
            return f"<span style='color:#EF4444; font-weight:900;'>{dt.strftime('%Y-%m-%d')}</span>"
        return dt.strftime("%Y-%m-%d")

    # badge-urile
    df_f = df_f.copy()
    df_f["status"] = df_f["status"].apply(status_badge)
    df_f["lucrare_status"] = df_f["lucrare_status"].apply(lambda x: status_badge(x) if str(x).strip() else "")

    if only_client_filter:
        st.subheader(f"Toate sarcinile clientului: {client_select}")

        df_all_client = df_f.sort_values(["lucrare_id", "__ord"], ascending=[True, True]).copy()
        df_all_client["data_scadenta"] = df_all_client.apply(fmt_due, axis=1)

        view_cols = [
            "lucrare_id",
            "lucrare_tip",
            "lucrare_status",
            "ordine",
            "id",
            "tip_sarcina",
            "status",
            "responsabil",
            "data_scadenta",
            "observatii",
        ]
        for col in view_cols:
            if col not in df_all_client.columns:
                df_all_client[col] = ""

        st.markdown(
            df_all_client[view_cols].to_html(escape=False, index=False, classes="eco-table"),
            unsafe_allow_html=True,
        )
        return

    st.subheader("Lucrări + sarcina curentă (1 rând per lucrare)")

    def pick_current_for_lucrare(g: pd.DataFrame) -> pd.Series:
        g = g.sort_values("__ord", ascending=True)

        in_lucru = g[g["status"].astype(str).str.contains("IN LUCRU", na=False)]
        if not in_lucru.empty:
            return in_lucru.iloc[0]

        blocat = g[g["status"].astype(str).str.contains("BLOCAT", na=False)]
        if not blocat.empty:
            return blocat.iloc[0]

        not_done = g[~g["status"].astype(str).str.contains("FINALIZAT", na=False)]
        if not not_done.empty:
            return not_done.iloc[0]

        return g.iloc[-1]

    rows = []
    for _, g in df_f.groupby("lucrare_id"):
        rows.append(pick_current_for_lucrare(g))

    df_cur = pd.DataFrame(rows).copy()
    df_cur["data_scadenta"] = df_cur.apply(fmt_due, axis=1)

    # sortare
    def prio_from_badge_html(x: str) -> int:
        s = str(x or "")
        if "IN LUCRU" in s:
            return 0
        if "BLOCAT" in s:
            return 1
        if "NOU" in s:
            return 2
        if "FINALIZAT" in s:
            return 3
        return 9

    df_cur["__prio"] = df_cur["status"].apply(prio_from_badge_html)
    df_cur = df_cur.sort_values(["__prio", "client_nume", "lucrare_id"], ascending=[True, True, True])

    view_cols = [
        "client_nume",
        "lucrare_id",
        "lucrare_tip",
        "lucrare_status",
        "ordine",
        "id",
        "tip_sarcina",
        "status",
        "responsabil",
        "data_scadenta",
        "observatii",
    ]
    for col in view_cols:
        if col not in df_cur.columns:
            df_cur[col] = ""

    st.caption(f"Lucrări afișate: {len(df_cur)}")
    st.markdown(
        df_cur[view_cols].to_html(escape=False, index=False, classes="eco-table"),
        unsafe_allow_html=True,
    )