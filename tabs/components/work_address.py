"""Work address is a saved copy, never a live link to the client."""
import streamlit as st
from utils.iugn_contract import ADDRESS_PARTS

LABELS=('Judet','Localitate','Strada','Numar','Bloc','Scara','Etaj','Apartament','Cod postal')


def copy_home(client):
    return {'adresa_'+part:str(client.get('domiciliu_'+part) or '') for part in ADDRESS_PARTS}


def copy_control(client,key):
    def apply():
        if st.session_state.get(key+'_same'):
            for name,value in copy_home(client).items():st.session_state[key+'_'+name]=value
    st.checkbox('Adresa lucrarii este aceeasi cu domiciliul / sediul clientului',
                key=key+'_same',on_change=apply)
    st.caption('Bifa copiaza adresa acum. Modificarile ulterioare din fisa clientului nu schimba aceasta lucrare.')


def fields(row,key):
    values={}
    for start in (0,3,6):
        for col,part,label in zip(st.columns(3),ADDRESS_PARTS[start:start+3],LABELS[start:start+3]):
            name='adresa_'+part
            widget_key=key+'_'+name
            if widget_key not in st.session_state:st.session_state[widget_key]=str(row.get(name) or '')
            values[name]=col.text_input(label,key=widget_key)
    return values
