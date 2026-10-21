"""Read-only business views without edit, delete or upload forms."""
import streamlit as st
from db import db

LABELS = {
    'nume': 'Client', 'cod_intern': 'Cod intern', 'telefon': 'Telefon', 'email': 'E-mail',
    'firma': 'Firma', 'status': 'Status', 'valoare_contract': 'Valoare contract (lei)',
    'facturat': 'Facturat (lei)', 'platit': 'Incasat (lei)', 'sold': 'Sold (lei)',
    'tip_lucrare': 'Tip lucrare', 'valoare_contractata': 'Valoare (lei)',
    'responsabil': 'Responsabil', 'data_contract': 'Data contract',
    'data_programare': 'Data programare', 'descriere': 'Descriere',
    'adresa_localitate': 'Localitate', 'adresa_strada': 'Strada', 'adresa_numar': 'Numar',
    'numar': 'Factura', 'data_emiterii': 'Data emiterii', 'data_scadenta': 'Scadenta',
    'total': 'Total (lei)', 'incasat': 'Incasat (lei)', 'rest': 'Rest (lei)',
    'data_platii': 'Data platii', 'suma': 'Suma (lei)', 'metoda': 'Metoda',
    'client_nume': 'Client', 'lucrare_tip': 'Lucrare', 'tip_sarcina': 'Sarcina',
    'observatii': 'Observatii',
}


def _table(frame, columns):
    if frame is None or frame.empty:
        st.info('Nu exista inregistrari.')
        return
    visible = [name for name in columns if name in frame.columns]
    st.dataframe(frame[visible].rename(columns=LABELS), hide_index=True, use_container_width=True)


def show_clienti(user):
    st.header('Clienti - consultare')
    text = st.text_input('Cauta client', key='consultare_client_search')
    clients = db.lista_clienti(text)
    if clients.empty:
        st.info('Nu exista clienti pentru cautarea curenta.')
        return
    financials = db.agregate_financiare_clienti()
    if not financials.empty:
        clients = clients.merge(financials, left_on='id', right_on='client_id', how='left')
    _table(clients, ['nume', 'cod_intern', 'telefon', 'email', 'firma', 'status',
                     'valoare_contract', 'facturat', 'platit', 'sold'])
    names = {int(row['id']): f"{row['nume']} ({row.get('cod_intern') or '-'})"
             for _, row in clients.iterrows()}
    client_id = st.selectbox('Client pentru consultare', list(names), format_func=names.get,
                             key='consultare_client_id')
    st.subheader('Lucrari')
    _table(db.lista_lucrari_client(client_id), ['tip_lucrare', 'status', 'valoare_contractata',
           'responsabil', 'data_contract', 'data_programare', 'adresa_localitate',
           'adresa_strada', 'adresa_numar', 'descriere'])
    st.subheader('Facturi')
    _table(db.rezumat_facturi_client(client_id), ['numar', 'data_emiterii', 'data_scadenta',
                                               'total', 'incasat', 'rest', 'status'])
    st.subheader('Plati')
    _table(db.lista_plati(client_id), ['data_platii', 'suma', 'metoda', 'observatii'])


def show_sarcini(user):
    st.header('Sarcini - consultare')
    _table(db.lista_sarcini_all(), ['client_nume', 'lucrare_tip', 'tip_sarcina', 'status',
                                   'responsabil', 'data_scadenta', 'observatii'])
