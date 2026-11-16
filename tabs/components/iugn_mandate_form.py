"""Download issued mandates or complete a pre-existing service contract."""
from pathlib import Path
import hashlib
import streamlit as st
from db import iugn_mandates as mandates


def render(lid):
    key=f'iugn_mandate_{lid}'
    st.subheader('Contract de mandat IUGN')
    issued=mandates.get(lid)
    st.caption('Datele se preiau din contractul de prestari servicii emis. Emiterea nu confirma semnatura beneficiarului.')
    if issued:
        st.success('Mandat emis: '+issued['number'])
        path=Path(issued['path'])
        if not path.is_file():st.error('Mandatul lipseste din arhiva. Restaureaza documentul din backup.');return
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=issued['sha256']:
            st.error('Fisierul nu corespunde mandatului emis. Verifica arhiva.');return
        st.download_button('Descarca mandatul emis',data,file_name=issued['filename'],key=key+'_download')
        return
    st.info('Contractul emis anterior poate fi completat cu mandatul, fara reemiterea contractului.')
    if st.button('Previzualizeaza mandatul',key=key+'_preview_button'):
        st.session_state.pop(key+'_approved',None)
        try:st.session_state[key+'_approved']=mandates.preview(lid)
        except (ValueError,PermissionError,OSError) as exc:st.error(str(exc))
    approved=st.session_state.get(key+'_approved')
    if approved:
        st.download_button('Descarca previzualizarea mandatului',approved['data'],file_name='PREVIZUALIZARE_MANDAT_IUGN.docx',key=key+'_preview_download')
        if st.button('Emite si salveaza mandatul in dosar',key=key+'_issue'):
            try:mandates.issue_existing(lid,approved)
            except (ValueError,PermissionError,OSError) as exc:st.error(str(exc))
            else:
                st.session_state.pop(key+'_approved',None);st.rerun()
