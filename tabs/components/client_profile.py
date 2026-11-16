"""One editable client record shared by the client list and contract screen."""
from contextlib import closing
import streamlit as st
from db import db, iugn_documents as docs
from utils import iugn_contract as contract


def render_editor(client_id=None):
    key=f'client_profile_{client_id or "new"}'
    row={}
    inherited=False
    if client_id is not None:
        with closing(db._connect()) as conn:
            row=docs._row(conn,'SELECT * FROM clienti WHERE id=?',(int(client_id),))
            if not row:
                st.error('Clientul nu mai exista.');return False
            defaults,inherited=docs._beneficiary_defaults(conn,row,0)
        for name,source in contract.CLIENT_FIELDS.items():
            if not row.get('profile_saved') and not row.get(source) and defaults.get(name):
                row[source]=defaults[name]
    if key+'_snapshot' not in st.session_state:
        st.session_state[key+'_snapshot']=(row,inherited)
    row,inherited=st.session_state[key+'_snapshot']
    st.subheader('Editeaza clientul' if client_id else 'Adauga client')
    st.caption('Identitate, contact si domiciliu / sediu. Adresa locului de consum se completeaza separat in fiecare lucrare.')
    if inherited and not row.get('profile_saved'):
        st.info('Am recuperat date din documentele acestui client. Verifica-le si salveaza fisa; contractele emise raman nemodificate.')
    kind=st.selectbox('Tip client',['PF','PJ'],index=1 if (row.get('beneficiar_tip')=='PJ' if row.get('beneficiar_tip') else bool(row.get('firma'))) else 0,key=key+'_kind')
    values={'beneficiar_tip':kind,'profile_saved':1}
    with st.form(key+'_form'):
        def fields(items):
            cols=st.columns(len(items))
            for col,(name,label) in zip(cols,items):
                values[name]=col.text_input(label,value=str(row.get(name) or ''),key=key+'_'+name)
        fields([('nume','Nume complet / reprezentant'),('telefon','Telefon'),('email','E-mail')])
        if kind=='PJ':
            fields([('firma','Denumire firma'),('beneficiar_cui','CUI'),('beneficiar_regcom','Registrul Comertului')])
            fields([('beneficiar_reprezentant_calitate','Calitatea reprezentantului')])
        else:
            values.update(firma='',beneficiar_cui='',beneficiar_regcom='',beneficiar_reprezentant_calitate='')
            fields([('ci_serie','Serie CI'),('ci_numar','Numar CI'),('ci_emitent','CI eliberata de'),('ci_data','Data eliberarii CI (zz.ll.aaaa)')])
        st.markdown('**Domiciliu / sediu**')
        fields([('domiciliu_judet','Judet'),('domiciliu_localitate','Localitate'),('domiciliu_strada','Strada')])
        fields([('domiciliu_numar','Numar'),('domiciliu_bloc','Bloc'),('domiciliu_scara','Scara')])
        fields([('domiciliu_etaj','Etaj'),('domiciliu_apartament','Apartament'),('domiciliu_cod_postal','Cod postal')])
        with st.expander('Alte date ale clientului'):
            fields([('beneficiar_banca','Banca (optional)'),('beneficiar_iban','IBAN (optional)')])
            fields([('cod_intern','Cod intern'),('remark','Nota interna')])
            status_options=['OFERTAT','CONTRACTAT','PROGRAMAT','EXECUTAT','FINALIZAT','ÎNCHIS']
            current=str(row.get('status') or 'OFERTAT').upper()
            cols=st.columns(2)
            values['status']=cols[0].selectbox('Status client',status_options,index=status_options.index(current) if current in status_options else 0)
            values['scor']=cols[1].number_input('Scor',value=int(row.get('scor') or 0))
            values['observatii']=st.text_area('Observatii client',value=str(row.get('observatii') or ''))
        save=st.form_submit_button('Salveaza clientul')
        cancel=st.form_submit_button('Inchide editarea clientului')
    if cancel:
        for k in list(st.session_state):
            if k.startswith(key+'_'):st.session_state.pop(k,None)
        return True
    if save:
        if not values['nume'].strip():st.error('Completeaza numele clientului.');return False
        if not values['telefon'].strip() and not values['email'].strip():
            st.error('Completeaza cel putin telefonul sau e-mailul.');return False
        if values['email'] and ('@' not in values['email'] or '.' not in values['email'].split('@')[-1]):
            st.error('Verifica adresa de e-mail.');return False
        try:
            if client_id:db.modifica_client(client_id,values,expected_revision=row.get('profile_revision') or 0)
            else:db.adauga_client(values)
        except (ValueError,PermissionError) as exc:st.error(str(exc));return False
        for k in list(st.session_state):
            if k.startswith(key+'_'):st.session_state.pop(k,None)
        return True
    return False
