import os
import time
import streamlit as st

from tabs import (
    tab_overview,
    tab_clienti,
    tab_alerte,
    tab_word,
    tab_chat,
    tab_calendar,
    tab_financiar,
    tab_lucrari,
    tab_sarcini,
    tab_utilizatori,
)

import db.db as db

# IMPORTANT: set_page_config trebuie să fie primul apel Streamlit (înainte de orice st.* output)
st.set_page_config(page_title="ECOLOPTIM_clienti", page_icon="🧑‍🔧", layout="wide")

db.init_db()


def load_ui():
    css_path = os.path.join("assets", "ui.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        v = int(time.time())
        st.markdown(f"<style id='eco-ui-{v}'>\n{css}\n</style>", unsafe_allow_html=True)


def render_header(user: str, role: str = ""):
    role_html = f"<div>Rol: <b>{role}</b></div>" if role else ""
    st.markdown(
        f"""
        <div class="eco-header">
          <div class="eco-brand">
            <div class="eco-logo">🧑‍🔧</div>
            <div>
              <p class="eco-title">ECOLOPTIM</p>
              <p class="eco-sub">Manager clienți • Lucrări • Sarcini • Documente</p>
            </div>
          </div>
          <div class="eco-user">
            <div>Conectat: <b>{user}</b></div>
            {role_html}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def login():
    if "user" in st.session_state:
        return

    load_ui()

    st.markdown("<div class='login-wrap'>", unsafe_allow_html=True)
    st.markdown("<div class='login-card'>", unsafe_allow_html=True)

    logo_path = os.path.join("assets", "logo.png")
    if os.path.exists(logo_path):
        st.markdown("<div class='login-head'>", unsafe_allow_html=True)
        st.image(logo_path, width=44)
        st.markdown(
            "<div><div class='login-title'>Autentificare</div><div class='login-sub'>ECOLOPTIM • Manager clienți</div></div>",
            unsafe_allow_html=True,
        )
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='login-head'><div class='eco-logo'>🧑‍🔧</div>"
            "<div><div class='login-title'>Autentificare</div><div class='login-sub'>ECOLOPTIM • Manager clienți</div></div></div>",
            unsafe_allow_html=True,
        )

    with st.form("login_form", clear_on_submit=False):
        l, mid, r = st.columns([1.2, 2.2, 1.2])
        with mid:
            user_in = st.text_input("Utilizator", value="admin", placeholder="ex: admin", key="login_user")
            show_pwd = st.checkbox("Afișează parola", value=False, key="login_show_pwd")
            pwd_in = st.text_input(
                "Parolă",
                type="default" if show_pwd else "password",
                placeholder="••••••••",
                key="login_pwd",
            )
            submit = st.form_submit_button("Login")

    if submit:
        user_row = db.login(user_in, pwd_in)
        if user_row:
            st.session_state["user"] = user_row[1]
            st.session_state["role"] = user_row[3]
            st.session_state["must_change_password"] = bool(user_row[5])
            st.rerun()
        else:
            st.error("Utilizator, parolă greșită sau cont inactiv.")

    st.markdown("<div class='login-footer'>Dacă ai nevoie de cont nou, contactează administratorul.</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


login()
user = st.session_state["user"]
role = st.session_state.get("role", "")
must_change_password = st.session_state.get("must_change_password", False)

load_ui()
render_header(user, role)

with st.sidebar:
    st.markdown("### 👤 Cont")
    st.write(f"Conectat ca: **{user}**")
    if role:
        st.write(f"Rol: **{role}**")

    if must_change_password:
        st.warning("Trebuie să îți schimbi parola înainte de utilizarea normală a aplicației.")

    with st.expander("🔒 Schimbă parola", expanded=must_change_password):
        with st.form("change_password_form", clear_on_submit=True):
            parola_veche = st.text_input("Parola curentă", type="password")
            parola_noua = st.text_input("Parola nouă", type="password")
            parola_noua_2 = st.text_input("Confirmă parola nouă", type="password")
            submit_change_pwd = st.form_submit_button("Actualizează parola")

            if submit_change_pwd:
                try:
                    if not parola_veche:
                        raise ValueError("Introdu parola curentă.")
                    if not parola_noua:
                        raise ValueError("Introdu parola nouă.")
                    if len(parola_noua) < 8:
                        raise ValueError("Parola nouă trebuie să aibă minim 8 caractere.")
                    if parola_noua != parola_noua_2:
                        raise ValueError("Confirmarea parolei nu corespunde.")
                    if parola_veche == parola_noua:
                        raise ValueError("Parola nouă trebuie să fie diferită de cea veche.")

                    user_row = db.login(user, parola_veche)
                    if not user_row:
                        raise ValueError("Parola curentă este incorectă.")

                    db.schimba_parola_fara_verificare_admin(user, parola_noua, must_change_password=0)
                    st.session_state["must_change_password"] = False
                    st.success("Parola a fost schimbată cu succes.")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    if st.button("⛔ Renunță", key="logout_btn"):
        st.session_state.pop("user", None)
        st.session_state.pop("role", None)
        st.session_state.pop("must_change_password", None)
        for k in [
            "add_client_open",
            "edit_client_id",
            "lucrari_for_client",
            "financiar_for_client",
            "delete_client_id",
            "show_atasamente_for",
            "show_atasamente_lucrare_id",
            "show_atasamente_sarcina_id",
            "open_financiar_for_client",
        ]:
            st.session_state.pop(k, None)
        st.rerun()

if must_change_password:
    st.info("Pentru siguranță, schimbă parola din bara laterală înainte să continui.")

tab_defs = [
    ("🏠 Overview", lambda: tab_overview.show(user)),
    ("👥 Clienți", lambda: tab_clienti.show(user)),
    ("⚠️ Alerte", lambda: tab_alerte.show(user)),
    ("📝 Generare Word", lambda: tab_word.show(user)),
    ("💬 Chat", lambda: tab_chat.show(user)),
    ("🗓️ Calendar", lambda: tab_calendar.show(user)),
    ("💶 Financiar", lambda: tab_financiar.show(user)),
    ("📌 Sarcini", lambda: tab_sarcini.show(user)),
    ("🔨 Lucrări", lambda: tab_lucrari.show(user)),
]

if role == "admin":
    tab_defs.append(("👤 Utilizatori", lambda: tab_utilizatori.show(user)))

tab_titles = [title for title, _ in tab_defs]
tab_objects = st.tabs(tab_titles)

for tab_obj, (_, render_fn) in zip(tab_objects, tab_defs):
    with tab_obj:
        render_fn()