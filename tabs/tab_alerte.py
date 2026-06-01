import streamlit as st
import pandas as pd
from datetime import date

import db.db as db


def show(user):
    st.header("⚠️ Alerte — ECOLOPTIM_clienti")

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