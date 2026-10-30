"""Route new IUGN works to the contract form; preserve legacy documents."""
import streamlit as st
from db import db
from db.iugn_rules import WORK_TYPE
from tabs.components.lucrari_client_components import PREFIX
from tabs.components.lucrari_client_components import render_documente_panel as legacy_documents
from tabs.components.iugn_contract_form import render


def render_documente_panel(user,client_id,client,**kwargs):
    key=f'{PREFIX}doc_lucrare_id_{client_id}'
    lid=st.session_state.get(key)
    work=db.get_lucrare(int(lid)) if lid else None
    if work and work.get('tip_lucrare')==WORK_TYPE:
        choice=st.selectbox('Documente IUGN',['Contract IUGN cu anexe','Alte documente'],key=f'iugn_doc_choice_{lid}')
        if choice=='Contract IUGN cu anexe':
            render(int(lid))
            if st.button('Inchide documente',key=f'iugn_doc_close_{lid}'):
                st.session_state.pop(key,None)
                st.rerun()
            return
    legacy_documents(user=user,client_id=client_id,client=client,**kwargs)
