import streamlit as st
from tabs import tab_clienti, tab_alerte, tab_word, tab_chat, tab_calendar, tab_financiar, tab_lucrari

import db.db as db

db.init_db()

def login():
    if "user" not in st.session_state:
        st.title("🔑 Login utilizator")
        user = st.text_input("Utilizator", value="admin")
        pwd = st.text_input("Parolă", type="password")
        login_btn = st.button("Login")
        if login_btn:
            user_row = db.login(user, pwd)
            if user_row:
                st.session_state["user"] = user_row[1]
                st.rerun()
            else:
                st.error("Login eșuat.")
        st.stop()
login()
user = st.session_state["user"]

st.set_page_config(page_title="ECOLOPTIM_clienti", page_icon="🧑‍🔧", layout="wide")
st.markdown("<h1 style='color:#009aff;text-align:center;'>🧑‍🔧 ECOLOPTIM_clienti</h1>", unsafe_allow_html=True)

tabs = st.tabs([
    "👥 Clienți", "⚠️ Alerte", "📝 Generare Word",
    "💬 Chat", "🗓️ Calendar", "💶 Financiar", "🔨 Lucrări"
])

with tabs[0]:
    tab_clienti.show(user)
with tabs[1]:
    tab_alerte.show(user)
with tabs[2]:
    tab_word.show(user)
with tabs[3]:
    tab_chat.show(user)
with tabs[4]:
    tab_calendar.show(user)
with tabs[5]:
    tab_financiar.show(user)
with tabs[6]:
    tab_lucrari.show(user)