import streamlit as st
import db.db as db
import pandas as pd


def _kpi_card(title: str, value: str, sub: str = "", color: str = "#0A84FF"):
    st.markdown(
        f"""
        <div class="eco-card" style="padding:14px;">
          <div style="font-size:12px; letter-spacing:.04em; text-transform:uppercase; color:rgba(15,23,42,0.65); font-weight:900;">
            {title}
          </div>
          <div style="font-size:30px; font-weight:950; margin-top:4px; color:{color}; line-height:1.1;">
            {value}
          </div>
          <div style="font-size:12px; color:rgba(15,23,42,0.65); margin-top:4px;">
            {sub}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _status_badge(status: str) -> str:
    s = str(status or "").upper().strip()
    if s == "IN_LUCRU":
        return "<span class='badge badge-in'>IN LUCRU</span>"
    if s == "BLOCAT":
        return "<span class='badge badge-bl'>BLOCAT</span>"
    if s == "FINALIZAT":
        return "<span class='badge badge-fin'>FINALIZAT</span>"
    return "<span class='badge badge-nou'>NOU</span>"


def _fmt_due(dt) -> str:
    if dt is None or pd.isna(dt):
        return ""
    return pd.to_datetime(dt).strftime("%Y-%m-%d")


def show(user):
    st.markdown("### 🏠 Overview")

    today = pd.Timestamp.today().normalize()

    # ----------------- Sarcini -----------------
    df_s = db.lista_sarcini_all(filtru_status="", filtru_text="")
    if df_s is None:
        df_s = pd.DataFrame()

    if not df_s.empty:
        for col in (
            "client_nume",
            "lucrare_id",
            "lucrare_tip",
            "id",
            "ordine",
            "tip_sarcina",
            "status",
            "data_scadenta",
            "responsabil",
            "observatii",
        ):
            if col not in df_s.columns:
                df_s[col] = ""

        df_s = df_s.copy()
        df_s["__ord"] = df_s.apply(
            lambda r: int(r["ordine"]) if pd.notnull(r.get("ordine")) else int(r["id"]),
            axis=1,
        )
        df_s["__due_dt"] = pd.to_datetime(df_s["data_scadenta"], errors="coerce")
        df_s["__overdue"] = (
            (df_s["__due_dt"].notna())
            & (df_s["__due_dt"].dt.normalize() < today)
            & (df_s["status"].astype(str) != "FINALIZAT")
        )

        overdue = int(df_s["__overdue"].sum())
        in_lucru = int((df_s["status"].astype(str) == "IN_LUCRU").sum())
        blocat = int((df_s["status"].astype(str) == "BLOCAT").sum())
        total_sarcini = int(len(df_s))
        finalizate = int((df_s["status"].astype(str) == "FINALIZAT").sum())
    else:
        overdue = in_lucru = blocat = total_sarcini = finalizate = 0

    # ----------------- Lucrări -----------------
    df_l = db.lista_lucrari()
    if df_l is None:
        df_l = pd.DataFrame()

    if not df_l.empty:
        df_l = df_l.copy()
        df_l["__prog_dt"] = pd.to_datetime(df_l.get("data_programare", ""), errors="coerce")
        prog_azi = int((df_l["__prog_dt"].dt.normalize() == today).sum())
        total_lucrari = int(len(df_l))
    else:
        prog_azi = total_lucrari = 0

    # ----------------- Financiar -----------------
    try:
        solduri = db.solduri_pe_clienti() or {}
        total_sold = float(sum(float(v or 0.0) for v in solduri.values()))
        restantieri = int(sum(1 for v in solduri.values() if float(v or 0.0) > 0))
    except Exception:
        total_sold = 0.0
        restantieri = 0

    # ----------------- KPI row -----------------
    k = st.columns(5)
    with k[0]:
        _kpi_card("Sarcini depășite", str(overdue), "Termen depășit (și nu sunt FINALIZATE)", color="#EF4444")
    with k[1]:
        _kpi_card("În lucru", str(in_lucru), "Sarcini cu status IN_LUCRU", color="#0A84FF")
    with k[2]:
        _kpi_card("Blocate", str(blocat), "Sarcini cu status BLOCAT", color="#F59E0B")
    with k[3]:
        _kpi_card("Lucrări azi", str(prog_azi), today.strftime("%Y-%m-%d"), color="#8B5CF6")
    with k[4]:
        _kpi_card("SOLD total", f"{total_sold:,.0f}", f"Restanțieri: {restantieri}", color="#0F172A")

    st.markdown("---")

    # ----------------- Liste rapide -----------------
    left, mid, right = st.columns([1.15, 1.00, 0.85], gap="large")

    with left:
        st.markdown("#### ⛔ Sarcini depășite (top 15)")
        if df_s.empty or overdue == 0:
            st.info("Nu există sarcini depășite.")
        else:
            df_o = df_s[df_s["__overdue"]].copy()
            df_o = df_o.sort_values(["__due_dt", "client_nume", "__ord"], ascending=[True, True, True]).head(15)

            def fmt_due_html(r):
                return f"<span style='color:#EF4444; font-weight:900;'>{_fmt_due(r['__due_dt'])}</span>"

            df_o["status"] = df_o["status"].apply(_status_badge)
            df_o["data_scadenta"] = df_o.apply(fmt_due_html, axis=1)

            view = df_o[["client_nume", "lucrare_id", "lucrare_tip", "id", "tip_sarcina", "status", "data_scadenta"]].copy()
            st.markdown(view.to_html(escape=False, index=False, classes="eco-table"), unsafe_allow_html=True)

    with mid:
        st.markdown("#### ⏳ Sarcini în lucru (top 12)")
        if df_s.empty or in_lucru == 0:
            st.info("Nu există sarcini în lucru.")
        else:
            df_w = df_s[df_s["status"].astype(str) == "IN_LUCRU"].copy()
            df_w = df_w.sort_values(["__due_dt", "client_nume", "__ord"], ascending=[True, True, True]).head(12)

            df_w["status"] = df_w["status"].apply(_status_badge)
            df_w["data_scadenta"] = df_w["__due_dt"].apply(_fmt_due)

            view = df_w[["client_nume", "lucrare_id", "lucrare_tip", "id", "tip_sarcina", "status", "data_scadenta"]].copy()
            st.markdown(view.to_html(escape=False, index=False, classes="eco-table"), unsafe_allow_html=True)

    with right:
        st.markdown("#### 🗓️ Lucrări programate azi (top 12)")
        if df_l.empty or prog_azi == 0:
            st.info("Nu există lucrări programate azi.")
        else:
            df_p = df_l.copy()
            df_p["__prog_dt"] = pd.to_datetime(df_p.get("data_programare", ""), errors="coerce")
            df_p = df_p[df_p["__prog_dt"].dt.normalize() == today].copy()

            try:
                clienti = db.lista_clienti()
                if clienti is not None and not clienti.empty and "client_id" in df_p.columns:
                    df_p = df_p.merge(
                        clienti[["id", "nume"]],
                        left_on="client_id",
                        right_on="id",
                        how="left",
                        suffixes=("", "_c"),
                    )
                    df_p = df_p.rename(columns={"nume": "client_nume"})
            except Exception:
                df_p["client_nume"] = ""

            for col in ("client_nume", "tip_lucrare", "interval_orar", "responsabil", "echipa"):
                if col not in df_p.columns:
                    df_p[col] = ""

            df_p = df_p.sort_values(["interval_orar", "client_nume"], ascending=[True, True]).head(12)

            view = df_p[["client_nume", "tip_lucrare", "interval_orar", "responsabil", "echipa"]].copy()
            st.markdown(view.to_html(escape=False, index=False, classes="eco-table"), unsafe_allow_html=True)

    st.markdown("---")
    st.caption(f"Sarcini: {total_sarcini} (finalizate: {finalizate}) • Lucrări: {total_lucrari}")