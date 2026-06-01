import streamlit as st
import db.db as db


def show(user, client_id, lucrare_id=None, sarcina_id=None):
    st.header("📎 Atașamente")

    clienti = db.lista_clienti()
    client = clienti[clienti["id"] == client_id].iloc[0]

    ctx_parts = [f"Client: **{client['nume']}** (ID {int(client_id)})"]
    if lucrare_id is not None:
        ctx_parts.append(f"Lucrare ID **{int(lucrare_id)}**")
    if sarcina_id is not None:
        ctx_parts.append(f"Sarcină ID **{int(sarcina_id)}**")

    st.markdown(" | ".join(ctx_parts))

    atasamente = db.lista_atasamente(int(client_id), lucrare_id=lucrare_id, sarcina_id=sarcina_id)

    if atasamente is None or atasamente.empty:
        st.info("Nu există atașamente pentru acest context.")
    else:
        for _, fila in atasamente.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            col1.write(fila["filename"])
            col2.write(f"Upload de: {fila.get('uploaded_by','')}, {fila.get('upload_date','')}")

            try:
                with open(fila["path"], "rb") as f:
                    filedata = f.read()
                col3.download_button(
                    "⬇️ Descarcă",
                    data=filedata,
                    file_name=fila["filename"],
                    key=f"download_{fila['id']}",
                )
            except Exception as e:
                col3.error(f"Eroare la citire fișier: {type(e).__name__}")

            confirm_key = f"atas_confirm_{fila['id']}"
            if st.session_state.get(confirm_key, False):
                btn1 = col4.button("Confirmă", key=f"confirm_del_{fila['id']}")
                btn2 = col4.button("Anulează", key=f"cancel_del_{fila['id']}")
                if btn1:
                    db.sterge_atasament(int(fila["id"]))
                    st.success("Șters cu succes!")
                    st.session_state[confirm_key] = False
                    st.rerun()
                if btn2:
                    st.session_state[confirm_key] = False
                    st.rerun()
            else:
                if col4.button("🗑️ Șterge", key=f"del_{fila['id']}"):
                    st.session_state[confirm_key] = True
                    st.rerun()

    st.markdown("---")
    st.subheader("Încarcă atașament")

    with st.form("upload_form", clear_on_submit=True):
        col1, col2 = st.columns([0.7, 0.3])
        uploaded_file = col1.file_uploader("Alege fișier", label_visibility="collapsed")
        submit = col2.form_submit_button("Încarcă")

    if submit and uploaded_file:
        numedefis = uploaded_file.name.rsplit(".", 1)[0].lower()

        toate = db.lista_atasamente(int(client_id), lucrare_id=lucrare_id, sarcina_id=sarcina_id)
        nume_duplicat = False
        if toate is not None and not toate.empty:
            nume_duplicat = any(
                str(r["filename"]).rsplit(".", 1)[0].lower() == numedefis
                for _, r in toate.iterrows()
            )

        if nume_duplicat:
            st.error(f"Există deja un fișier cu numele '{numedefis}' în acest context (indiferent de extensie)!")
        else:
            db.save_atasament(
                int(client_id),
                uploaded_file.name,
                user,
                uploaded_file.read(),
                lucrare_id=int(lucrare_id) if lucrare_id is not None else None,
                sarcina_id=int(sarcina_id) if sarcina_id is not None else None,
            )
            st.success("Fișier încărcat cu succes!")
            st.rerun()