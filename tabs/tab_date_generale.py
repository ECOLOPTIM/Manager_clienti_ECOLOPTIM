from datetime import date
import streamlit as st
from config.company_fields import COMPANY_GROUPS
from db import company, permissions


def render_authorization_alerts():
    """Show live warnings on every authenticated app page, without dismissing them."""
    for item in company.authorizations(company.get()['values']):
        label=f"Autorizatia ANRE de {item['kind']}"
        if item['numar']: label+=f" nr. {item['numar']}"
        if item['status']=='expirata':
            st.error(f"{label} a expirat la {item['expiry']:%d.%m.%Y}. Actualizeaza Date generale dupa reinnoire.")
        elif item['status']=='expira_curand':
            suffix='astazi' if item['days']==0 else f"in {item['days']} zile"
            st.warning(f"{label} expira {suffix}, la {item['expiry']:%d.%m.%Y}. Pregateste reinnoirea.")


def show(user):
    permissions.require('admin')
    st.subheader('Date generale')
    st.caption('Datele firmei pentru documente. Autorizarile se verifica la fiecare accesare a aplicatiei; '
               'avertizarea incepe cu trei luni calendaristice inainte de expirare.')
    cache='company_settings_snapshot'
    if cache not in st.session_state:
        st.session_state[cache]=company.get()
    snapshot=st.session_state[cache]
    if st.button('Reincarca datele generale', key='company_reload'):
        st.session_state.pop(cache,None)
        st.rerun()
    for item in company.authorizations(snapshot['values']):
        if not item['complete']:
            st.info(f"Completeaza tipul, numarul si data expirarii pentru autorizatia de {item['kind']}.")
    rev=snapshot['revision']
    with st.form(f'company_form_{rev}'):
        values={}
        for group, fields in COMPANY_GROUPS.items():
            st.markdown('**'+group+'**')
            for name,label in fields.items():
                value=snapshot['values'][name]
                if name.endswith('_expirare'):
                    values[name]=st.date_input(label, value=date.fromisoformat(value) if value else None,
                        min_value=date(1900,1,1),max_value=date(2200,12,31),format='DD.MM.YYYY',
                        key=f'company_{name}_{rev}')
                elif name.startswith('gdpr_') and name!='gdpr_contact_dpo':
                    values[name]=st.text_area(label, value=value,key=f'company_{name}_{rev}')
                else:
                    values[name]=st.text_input(label, value=value,key=f'company_{name}_{rev}')
        submit=st.form_submit_button('Salveaza datele generale')
    if submit:
        try:
            company.save(values,expected_revision=rev)
        except (ValueError,PermissionError) as exc:
            st.error(str(exc))
        else:
            st.session_state.pop(cache,None)
            st.session_state['company_saved_notice']=True
            st.rerun()
    if st.session_state.pop('company_saved_notice',False):
        st.success('Datele generale au fost salvate.')
    if snapshot['updated_at']:
        st.caption(f"Ultima salvare: {snapshot['updated_at']} | {snapshot['updated_by']}")
