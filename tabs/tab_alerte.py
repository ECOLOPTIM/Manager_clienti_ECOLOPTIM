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


def show(user):
    st.header("⚠️ Alerte — ECOLOPTIM_clienti")

    st.subheader("🔥 Lucrări executate care necesită programare PIF")

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

    st.divider()

    st.subheader("📅 Facturi cu scadența depășită (rest > 0)")

    clienti = db.lista_clienti()
    if clienti.empty:
        st.info("Nu există clienți.")
        return

    azi = date.today().isoformat()

    rows = []
    for _, c in clienti.iterrows():
        client_id = int(c["id"])
        nume = str(c.get("nume", ""))
        email = str(c.get("email", ""))

        rez = db.rezumat_facturi_client(client_id)
        if rez.empty:
            continue

        for _, f in rez.iterrows():
            status = str(f.get("status", "") or "")
            data_scadenta = str(f.get("data_scadenta", "") or "")
            rest = float(f.get("rest", 0) or 0)

            if status == "ANULATA":
                continue

            if data_scadenta and data_scadenta < azi and rest > 0:
                rows.append({
                    "client_id": client_id,
                    "client": nume,
                    "email": email,
                    "factura_id": int(f.get("id")),
                    "numar_factura": str(f.get("numar", "") or ""),
                    "data_scadenta": data_scadenta,
                    "total": float(f.get("total", 0) or 0),
                    "incasat": float(f.get("incasat", 0) or 0),
                    "rest": rest,
                    "status": status,
                })

    if not rows:
        st.success("Nu există facturi scadente depășite (cu rest > 0).")
        return

    df = pd.DataFrame(rows).sort_values(["data_scadenta", "rest"], ascending=[True, False])

    st.dataframe(
        df[["client_id", "client", "factura_id", "numar_factura", "data_scadenta", "total", "incasat", "rest", "status"]],
        use_container_width=True,
        hide_index=True
    )

    st.markdown("#### 👉 Deschide clientul (Financiar)")
    st.caption("Apasă butonul, apoi mergi în tab-ul 👥 Clienți (se va deschide automat pagina financiară).")

    for i, r in df.iterrows():
        cols = st.columns([3, 2, 2, 2, 1.6])
        cols[0].write(f"**{r['client']}** (ID {int(r['client_id'])})")
        cols[1].write(f"Factură: **{r['numar_factura']}** (ID {int(r['factura_id'])})")
        cols[2].write(f"Scadență: **{r['data_scadenta']}**")
        cols[3].write(f"Rest: **{float(r['rest']):,.2f}**")
        if cols[4].button("💶 Deschide", key=f"open_fin_{int(r['client_id'])}_{int(r['factura_id'])}_{i}"):
            st.session_state["open_financiar_for_client"] = int(r["client_id"])
            st.success("OK. Mergi acum în tab-ul 👥 Clienți.")
            st.stop()