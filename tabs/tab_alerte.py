import streamlit as st
import pandas as pd
from datetime import date

import db.db as db

TIPURI_CU_PIF = [
    "Instalatie de utilizare noua",
    "Suplimentare debit instalat",
    "Bransament nou prin DGSR",
    "Bransament nou cu OE client",
    "Extindere retea",
    "Extindere retea cu bransament",
]


def pif_missing_parts(row):
    lipsuri = []
    if not str(row.get("data_programare_pif", "") or "").strip():
        lipsuri.append("data PIF")
    if not str(row.get("interval_orar_pif", "") or "").strip():
        lipsuri.append("interval PIF")
    if not str(row.get("echipa_pif", "") or "").strip():
        lipsuri.append("echipa PIF")
    if not str(row.get("sef_echipa_pif", "") or "").strip():
        lipsuri.append("șef echipă PIF")
    return ", ".join(lipsuri)


def lucrari_executate_fara_pif():
    lucrari = db.lista_lucrari()
    if lucrari is None or lucrari.empty:
        return pd.DataFrame()

    df = lucrari.copy()

    for col in ["data_programare_pif", "interval_orar_pif", "echipa_pif", "sef_echipa_pif"]:
        if col not in df.columns:
            df[col] = ""

    if "tip_lucrare" not in df.columns or "status" not in df.columns:
        return pd.DataFrame()

    df["tip_lucrare"] = df["tip_lucrare"].fillna("").astype(str).str.strip()
    df["status"] = df["status"].fillna("").astype(str).str.strip().str.upper()

    df = df[
        df["tip_lucrare"].isin(TIPURI_CU_PIF) &
        (df["status"] == "EXECUTAT")
    ].copy()

    if df.empty:
        return df

    df = df[
        df["data_programare_pif"].fillna("").astype(str).str.strip().eq("") |
        df["interval_orar_pif"].fillna("").astype(str).str.strip().eq("") |
        df["echipa_pif"].fillna("").astype(str).str.strip().eq("") |
        df["sef_echipa_pif"].fillna("").astype(str).str.strip().eq("")
    ].copy()

    if df.empty:
        return df

    df["lipsuri_pif"] = df.apply(pif_missing_parts, axis=1)

    clienti = db.lista_clienti()
    if clienti is not None and not clienti.empty and "client_id" in df.columns and "id" in clienti.columns:
        clienti_map = clienti[["id", "nume", "telefon"]].copy()
        clienti_map = clienti_map.rename(columns={
            "id": "client_id",
            "nume": "client",
            "telefon": "telefon"
        })
        df = df.merge(clienti_map, on="client_id", how="left")

    sort_cols = [c for c in ["responsabil", "data_programare", "client_id"] if c in df.columns]
    if sort_cols:
        df = df.sort_values(sort_cols, ascending=True)

    return df


def _calc_overdue_days(data_scadenta: str, azi_iso: str) -> int:
    try:
        d1 = pd.to_datetime(str(data_scadenta)).date()
        d2 = pd.to_datetime(str(azi_iso)).date()
        return max((d2 - d1).days, 0)
    except Exception:
        return 0


def show(user):
    st.header("⚠️ Alerte — ECOLOPTIM_clienti")

    # =========================
    # 1) PIF lipsă la lucrări EXECUTATE
    # =========================
    st.subheader("🔥 Lucrări EXECUTATE care necesită programare PIF")

    df_pif = lucrari_executate_fara_pif()

    if df_pif is None or df_pif.empty:
        st.success("Nu există lucrări executate fără PIF.")
    else:
        st.warning(f"Există {len(df_pif)} lucrări executate care necesită programare PIF.")

        coloane_afisare = [
            c for c in [
                "id",
                "client_id",
                "client",
                "telefon",
                "tip_lucrare",
                "responsabil",
                "status",
                "data_programare",
                "interval_orar",
                "lipsuri_pif",
            ] if c in df_pif.columns
        ]

        st.dataframe(
            df_pif[coloane_afisare],
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 👉 Acțiuni rapide (PIF)")
        st.caption("Poți deschide direct clientul în tab-ul 👥 Clienți pentru lucrări/financiar.")

        for i, r in df_pif.iterrows():
            client_id = int(r.get("client_id"))
            client_nume = str(r.get("client", "") or f"Client {client_id}")
            lucrare_id = int(r.get("id")) if pd.notnull(r.get("id")) else None

            cols = st.columns([3.2, 2.4, 2.4, 1.5, 1.5])
            cols[0].write(f"**{client_nume}** (ID {client_id})")
            cols[1].write(f"Lucrare ID: **{lucrare_id}**")
            cols[2].write(f"Lipsuri: **{str(r.get('lipsuri_pif', ''))}**")

            if cols[3].button("🔨 Lucrări", key=f"open_works_pif_{client_id}_{i}"):
                st.session_state["lucrari_for_client"] = client_id
                st.success("OK. Mergi acum în tab-ul 👥 Clienți (se deschid lucrările clientului).")
                st.stop()

            if cols[4].button("💶 Financiar", key=f"open_fin_pif_{client_id}_{i}"):
                st.session_state["open_financiar_for_client"] = client_id
                st.success("OK. Mergi acum în tab-ul 👥 Clienți (se deschide financiarul clientului).")
                st.stop()

    st.divider()

    # =========================
    # 2) Facturi restante
    # =========================
    st.subheader("📅 Facturi cu scadența depășită (rest > 0)")

    clienti = db.lista_clienti()
    if clienti is None or clienti.empty:
        st.info("Nu există clienți.")
        return

    azi = date.today().isoformat()

    rows = []
    for _, c in clienti.iterrows():
        client_id = int(c["id"])
        nume = str(c.get("nume", ""))
        email = str(c.get("email", ""))

        rez = db.rezumat_facturi_client(client_id)
        if rez is None or rez.empty:
            continue

        for _, f in rez.iterrows():
            status = str(f.get("status", "") or "")
            data_scadenta = str(f.get("data_scadenta", "") or "")
            rest = float(f.get("rest", 0) or 0)

            if status == "ANULATA":
                continue

            if data_scadenta and data_scadenta < azi and rest > 0:
                zile_intarziere = _calc_overdue_days(data_scadenta, azi)
                rows.append({
                    "client_id": client_id,
                    "client": nume,
                    "email": email,
                    "factura_id": int(f.get("id")),
                    "numar_factura": str(f.get("numar", "") or ""),
                    "data_scadenta": data_scadenta,
                    "zile_intarziere": zile_intarziere,
                    "total": float(f.get("total", 0) or 0),
                    "incasat": float(f.get("incasat", 0) or 0),
                    "rest": rest,
                    "status": status,
                })

    if not rows:
        st.success("Nu există facturi scadente depășite (cu rest > 0).")
        return

    df = pd.DataFrame(rows).sort_values(
        ["zile_intarziere", "rest", "data_scadenta"],
        ascending=[False, False, True]
    )

    total_restant = float(df["rest"].sum()) if not df.empty else 0.0
    nr_facturi = int(len(df))
    nr_clienti = int(df["client_id"].nunique())

    k1, k2, k3 = st.columns(3)
    k1.metric("Facturi restante", nr_facturi)
    k2.metric("Clienți restanțieri", nr_clienti)
    k3.metric("Total restant (RON)", f"{total_restant:,.2f}")

    st.dataframe(
        df[
            [
                "client_id",
                "client",
                "factura_id",
                "numar_factura",
                "data_scadenta",
                "zile_intarziere",
                "total",
                "incasat",
                "rest",
                "status",
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("#### 👉 Acțiuni rapide (facturi restante)")
    st.caption("Apasă butonul, apoi mergi în tab-ul 👥 Clienți.")

    for i, r in df.iterrows():
        cols = st.columns([3.0, 2.0, 1.8, 1.8, 1.4, 1.4])

        cols[0].write(f"**{r['client']}** (ID {int(r['client_id'])})")
        cols[1].write(f"Factură: **{r['numar_factura']}** (ID {int(r['factura_id'])})")
        cols[2].write(f"Scadență: **{r['data_scadenta']}**")
        cols[3].write(f"Întârziere: **{int(r['zile_intarziere'])} zile**")
        cols[4].write(f"Rest: **{float(r['rest']):,.2f}**")

        if cols[5].button("💶 Deschide", key=f"open_fin_{int(r['client_id'])}_{int(r['factura_id'])}_{i}"):
            st.session_state["open_financiar_for_client"] = int(r["client_id"])
            st.success("OK. Mergi acum în tab-ul 👥 Clienți.")
            st.stop()