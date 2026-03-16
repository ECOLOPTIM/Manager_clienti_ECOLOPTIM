import streamlit as st
import db.db as db

def show(user):
    st.header("💶 Financiar — ECOLOPTIM_clienti")
    st.info("Aici gestionezi facturile/plățile asociate cliților.")