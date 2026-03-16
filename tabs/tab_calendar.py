import streamlit as st
import db.db as db

def show(user):
    st.header("🗓️ Calendar/intervenții — ECOLOPTIM_clienti")
    st.info("Aici planifici intervenții calendaristice pe client.")