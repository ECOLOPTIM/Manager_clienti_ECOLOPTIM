import streamlit as st
import db.db as db

ROLURI = ["admin", "birou", "vizualizare"]
PREFIX = "utilizatori_"


def show(user):
    role = st.session_state.get("role", "")

    if role != "admin":
        st.error("Nu ai drepturi pentru administrarea utilizatorilor.")
        st.stop()

    st.header("👤 Administrare utilizatori")

    # ---------------- Adăugare utilizator ----------------
    with st.expander("➕ Adaugă utilizator nou", expanded=False):
        with st.form(f"{PREFIX}form_add_user", clear_on_submit=True):
            c1, c2 = st.columns(2)
            username = c1.text_input("Username", key=f"{PREFIX}add_username")
            parola = c2.text_input("Parolă inițială", type="password", key=f"{PREFIX}add_password")

            c3, c4, c5 = st.columns(3)
            rol = c3.selectbox("Rol", ROLURI, index=1, key=f"{PREFIX}add_role")
            activ = c4.checkbox("Activ", value=True, key=f"{PREFIX}add_activ")
            must_change = c5.checkbox("Schimbă parola la prima logare", value=True, key=f"{PREFIX}add_must_change")

            submit_add = st.form_submit_button("Salvează utilizator")

            if submit_add:
                try:
                    db.adauga_utilizator(
                        username=username,
                        parola=parola,
                        rol=rol,
                        activ=1 if activ else 0,
                        must_change_password=1 if must_change else 0,
                    )
                    st.success(f"Utilizatorul '{username}' a fost creat.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    st.markdown("---")

    # ---------------- Listă utilizatori ----------------
    df_users = db.lista_utilizatori()

    if df_users is None or df_users.empty:
        st.info("Nu există utilizatori.")
        return

    st.subheader("Lista utilizatorilor")

    for _, row in df_users.iterrows():
        username = str(row["username"])
        rol_curent = str(row.get("rol") or "birou")
        activ_curent = int(row.get("activ") or 0)
        must_change_curent = int(row.get("must_change_password") or 0)

        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2.2, 1.4, 1.2, 1.4, 2.2])

            c1.markdown(
                f"**{username}**  \n"
                f"Creat: {row.get('created_at', '') or '-'}"
            )

            rol_nou = c2.selectbox(
                "Rol",
                ROLURI,
                index=ROLURI.index(rol_curent) if rol_curent in ROLURI else 1,
                key=f"{PREFIX}role_{username}",
            )

            activ_nou = c3.checkbox(
                "Activ",
                value=bool(activ_curent),
                key=f"{PREFIX}activ_{username}",
            )

            must_change_nou = c4.checkbox(
                "Schimbă parola",
                value=bool(must_change_curent),
                key=f"{PREFIX}mustchg_{username}",
            )

            with c5:
                cols_btn = st.columns([1, 1, 1])

                if cols_btn[0].button("💾 Salvează", key=f"{PREFIX}save_{username}"):
                    try:
                        db.seteaza_rol_utilizator(username, rol_nou)
                        db.seteaza_activ_utilizator(username, 1 if activ_nou else 0)
                        db.seteaza_must_change_password(username, 1 if must_change_nou else 0)
                        st.success(f"Utilizatorul '{username}' a fost actualizat.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

                if cols_btn[1].button("🔑 Reset parolă", key=f"{PREFIX}reset_btn_{username}"):
                    st.session_state[f"{PREFIX}reset_for"] = username

                if cols_btn[2].button("🗑️ Șterge", key=f"{PREFIX}delete_btn_{username}", disabled=(username.lower() == "admin")):
                    st.session_state[f"{PREFIX}delete_for"] = username

        st.markdown("---")

    # ---------------- Resetare parolă ----------------
    reset_for = st.session_state.get(f"{PREFIX}reset_for")
    if reset_for:
        st.subheader(f"🔑 Resetare parolă pentru: {reset_for}")

        with st.form(f"{PREFIX}form_reset_{reset_for}", clear_on_submit=True):
            p1, p2 = st.columns(2)
            new_password = p1.text_input("Parolă nouă", type="password", key=f"{PREFIX}newpass_{reset_for}")
            must_change_after_reset = p2.checkbox(
                "Obligă schimbarea parolei la următoarea logare",
                value=True,
                key=f"{PREFIX}must_change_after_reset_{reset_for}",
            )

            c1, c2 = st.columns([1, 1])
            do_reset = c1.form_submit_button("Resetează parola")
            do_cancel = c2.form_submit_button("Anulează")

            if do_reset:
                try:
                    db.reseteaza_parola_admin(
                        username=reset_for,
                        parola_noua=new_password,
                        must_change_password=1 if must_change_after_reset else 0,
                    )
                    st.success(f"Parola pentru '{reset_for}' a fost resetată.")
                    st.session_state.pop(f"{PREFIX}reset_for", None)
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

            if do_cancel:
                st.session_state.pop(f"{PREFIX}reset_for", None)
                st.rerun()

    # ---------------- Ștergere utilizator ----------------
    delete_for = st.session_state.get(f"{PREFIX}delete_for")
    if delete_for:
        st.subheader(f"🗑️ Ștergere utilizator: {delete_for}")
        st.warning(f"Ești sigur că vrei să ștergi utilizatorul '{delete_for}'?")

        c1, c2 = st.columns([1, 1])
        if c1.button("Confirmă ștergerea", key=f"{PREFIX}confirm_delete_{delete_for}"):
            try:
                db.sterge_utilizator(delete_for)
                st.success(f"Utilizatorul '{delete_for}' a fost șters.")
                st.session_state.pop(f"{PREFIX}delete_for", None)
                st.rerun()
            except Exception as e:
                st.error(str(e))

        if c2.button("Anulează", key=f"{PREFIX}cancel_delete_{delete_for}"):
            st.session_state.pop(f"{PREFIX}delete_for", None)
            st.rerun()