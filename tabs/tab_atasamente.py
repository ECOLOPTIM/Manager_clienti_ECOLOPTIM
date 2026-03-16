import streamlit as st
import db.db as db

def show(user, client_id):
    st.header("📎 Atașamente pentru client")
    clienti = db.lista_clienti()
    client = clienti[clienti["id"] == client_id].iloc[0]
    st.markdown(f"Client: **{client['nume']}**")

    atasamente = db.lista_atasamente(client_id)
    if atasamente.empty:
        st.info("Nu există atașamente pentru acest client.")
    else:
        for idx, fila in atasamente.iterrows():
            col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
            col1.write(fila["filename"])
            col2.write(f"Upload de: {fila['uploaded_by']}, {fila['upload_date']}")
            # Descarcare
            with open(fila["path"], "rb") as f:
                filedata = f.read()
            col3.download_button("⬇️ Descarcă", data=filedata, file_name=fila["filename"], key=f"download_{fila['id']}")
            
            # Stergere cu confirmare pe fiecare rand
            if st.session_state.get(f"atas_confirm_{fila['id']}", False):
                # Afisam butoanele Confirmă/Anulează
                btn1 = col4.button("Confirmă", key=f"confirm_del_{fila['id']}")
                btn2 = col4.button("Anulează", key=f"cancel_del_{fila['id']}")
                if btn1:
                    db.sterge_atasament(fila["id"])
                    st.success("Șters cu succes!")
                    st.session_state[f"atas_confirm_{fila['id']}"] = False
                    st.rerun()
                if btn2:
                    st.session_state[f"atas_confirm_{fila['id']}"] = False
                    st.rerun()
            else:
                if col4.button("🗑️ Șterge", key=f"del_{fila['id']}"):
                    st.session_state[f"atas_confirm_{fila['id']}"] = True
                    st.rerun()

    st.markdown("---")
    with st.form("upload_form", clear_on_submit=True):
        col1, col2 = st.columns([0.7, 0.3])
        uploaded_file = col1.file_uploader("Alege fișier", label_visibility="collapsed")
        submit = col2.form_submit_button("Încarcă")
    if submit and uploaded_file:
        numedefis = uploaded_file.name.rsplit('.', 1)[0].lower()
        toate = db.lista_atasamente(client_id)
        nume_duplicat = any(r['filename'].rsplit('.', 1)[0].lower() == numedefis for _, r in toate.iterrows())
        if nume_duplicat:
            st.error(f"Există deja un fișier cu numele '{numedefis}' pentru acest client (indiferent de extensie)!")
        else:
            db.save_atasament(client_id, uploaded_file.name, user, uploaded_file.read())
            st.success("Fișier încărcat cu succes!")
            st.rerun()