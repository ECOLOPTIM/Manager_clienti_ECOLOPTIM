import streamlit as st
from datetime import datetime
import io

import db.db as db

PREFIX = "fin_client_"
METODE_PLATA = ["", "CASH", "OP", "CARD"]


def show(user: str, client_id: int):
    clienti = db.lista_clienti()
    client = clienti[clienti["id"] == client_id].iloc[0]

    st.header(f"💶 FINANCIAR pentru: {client['nume']}")

    sold = db.calculeaza_sold_client(client_id)
    if sold > 0:
        st.warning(f"Sold (de încasat): {sold:,.2f} RON")
    elif sold < 0:
        st.success(f"Sold (avans): {abs(sold):,.2f} RON")
    else:
        st.info("Sold: 0.00 RON")

    st.markdown("---")

    colA, colB = st.columns(2)

    # ================= FACTURI =================
    with colA:
        st.subheader("🧾 Facturi (Total / Încasat / Rest)")

        df_fact = db.rezumat_facturi_client(client_id)
        if df_fact.empty:
            st.info("Nu există facturi.")
        else:
            show_cols = [c for c in [
                "id", "numar", "data_emiterii", "data_scadenta",
                "total", "incasat", "rest", "moneda", "status", "observatii"
            ] if c in df_fact.columns]

            def _style_rest(val):
                try:
                    v = float(val)
                except Exception:
                    return ""
                if v > 0:
                    return "color:#d01a1a;font-weight:700;"
                if v < 0:
                    return "color:#1a7f37;font-weight:700;"
                return ""

            styled = df_fact[show_cols].style.format({
                "total": "{:,.2f}",
                "incasat": "{:,.2f}",
                "rest": "{:,.2f}",
            }).applymap(_style_rest, subset=["rest"])

            st.dataframe(styled, use_container_width=True, hide_index=True)

            st.markdown("#### 🧯 Anulare / Ștergere factură")

            factura_ids = df_fact["id"].tolist()

            act_id = st.selectbox("Selectează factura (ID)", [""] + factura_ids, key=f"{PREFIX}act_fact_{client_id}")

            colx, coly = st.columns(2)
            if act_id:
                fid = int(act_id)

                if colx.button("🚫 ANULEAZĂ factura (păstrează istoric)", key=f"{PREFIX}btn_anuleaza_{client_id}"):
                    db.anuleaza_factura(fid)
                    st.success("Factura a fost anulată.")
                    st.rerun()

                if coly.button("🗑️ ȘTERGE factura (șterge și plățile)", key=f"{PREFIX}btn_sterge_{client_id}"):
                    db.sterge_factura(fid)
                    st.success("Factura a fost ștearsă.")
                    st.rerun()

            buffer = io.BytesIO()
            df_fact.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                "💾 Export facturi (Excel)",
                data=buffer,
                file_name=f"facturi_client_{client_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{PREFIX}export_fact_{client_id}"
            )

        st.markdown("#### ➕ Adaugă factură")
        with st.form(f"{PREFIX}form_add_fact_{client_id}", clear_on_submit=True):
            numar = st.text_input("Număr factură", value="")
            data_emiterii = st.date_input("Data emiterii", value=datetime.now().date())
            data_scadenta = st.date_input("Data scadenței", value=datetime.now().date())
            total = st.number_input("Total (RON)", min_value=0.0, step=100.0, value=0.0)
            observatii = st.text_area("Observații", value="")
            submit = st.form_submit_button("Salvează factura")
            if submit:
                if total <= 0:
                    st.error("Totalul facturii trebuie să fie > 0.")
                else:
                    db.adauga_factura({
                        "client_id": client_id,
                        "numar": numar,
                        "data_emiterii": str(data_emiterii),
                        "data_scadenta": str(data_scadenta),
                        "total": total,
                        "moneda": "RON",
                        "status": "NEINCASATA",
                        "observatii": observatii,
                        "created_by": user,
                    })
                    st.success("Factură adăugată.")
                    st.rerun()

    # ================= PLĂȚI =================
    with colB:
        st.subheader("💳 Plăți")

        df_plati = db.lista_plati(client_id)
        if df_plati.empty:
            st.info("Nu există plăți.")
        else:
            show_cols = [c for c in ["id", "factura_id", "data_platii", "suma", "metoda", "observatii"] if c in df_plati.columns]
            st.dataframe(df_plati[show_cols], use_container_width=True, hide_index=True)

            plata_ids = df_plati["id"].tolist()
            del_id = st.selectbox("Șterge plată (ID)", [""] + plata_ids, key=f"{PREFIX}del_plata_{client_id}")
            if del_id:
                if st.button("🗑️ Confirmă ștergerea plății", key=f"{PREFIX}confirm_del_plata_{client_id}"):
                    db.sterge_plata(int(del_id))
                    st.success("Plată ștearsă.")
                    st.rerun()

            buffer = io.BytesIO()
            df_plati.to_excel(buffer, index=False)
            buffer.seek(0)
            st.download_button(
                "💾 Export plăți (Excel)",
                data=buffer,
                file_name=f"plati_client_{client_id}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key=f"{PREFIX}export_plati_{client_id}"
            )

        st.markdown("---")
        st.markdown("#### ➕ Adaugă plată (clasic) — auto-fill cu REST")

        rez = db.rezumat_facturi_client(client_id)
        if rez.empty:
            st.warning("Nu poți adăuga o plată până nu există cel puțin o factură pentru acest client.")
        else:
            # selectbox cu rest + status
            optiuni = []
            map_id = []
            for _, r in rez.iterrows():
                fid = int(r["id"])
                numar = str(r.get("numar", "") or "")
                rest = float(r.get("rest", 0) or 0)
                status = str(r.get("status", "") or "")
                optiuni.append(f"{fid} | {numar} | Rest: {rest:,.2f} | {status}")
                map_id.append(fid)

            # păstrăm selecția în session_state ca să putem auto-seta suma
            key_fact = f"{PREFIX}plata_fact_select_{client_id}"
            if key_fact not in st.session_state:
                st.session_state[key_fact] = optiuni[0]

            def _extract_factura_id(opt: str) -> int:
                return int(opt.split("|")[0].strip())

            def _rest_for(fid: int) -> float:
                return float(rez[rez["id"] == fid].iloc[0]["rest"] or 0)

            def _status_for(fid: int) -> str:
                return str(rez[rez["id"] == fid].iloc[0]["status"] or "")

            with st.form(f"{PREFIX}form_add_plata_{client_id}", clear_on_submit=True):
                opt = st.selectbox("Factura", optiuni, key=key_fact)
                factura_id = _extract_factura_id(opt)
                rest_curent = _rest_for(factura_id)
                status_curent = _status_for(factura_id)

                st.caption(f"Rest curent: {rest_curent:,.2f} RON | Status: {status_curent}")

                # auto-fill: implicit pune restul (dacă e pozitiv)
                suma_default = rest_curent if rest_curent > 0 else 0.0

                data_platii = st.date_input("Data plății", value=datetime.now().date())
                suma = st.number_input("Sumă (RON)", min_value=0.0, step=100.0, value=float(suma_default))
                metoda = st.selectbox("Metodă", METODE_PLATA, index=0)
                observatii = st.text_area("Observații", value="")
                submit = st.form_submit_button("Salvează plata")

                if submit:
                    if status_curent == "ANULATA":
                        st.error("Nu poți înregistra plată pe o factură ANULATĂ.")
                    elif suma <= 0:
                        st.error("Suma trebuie să fie > 0.")
                    else:
                        # avertizare dacă e peste rest
                        if rest_curent > 0 and suma > rest_curent:
                            st.warning("Atenție: suma este mai mare decât REST-ul facturii. (Se permite, dar verifică!)")

                        try:
                            db.adauga_plata({
                                "client_id": client_id,
                                "factura_id": factura_id,
                                "data_platii": str(data_platii),
                                "suma": suma,
                                "metoda": metoda,
                                "observatii": observatii,
                                "created_by": user,
                            })
                            st.success("Plată adăugată. Statusul facturii s-a actualizat automat.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Eroare la salvarea plății: {e}")