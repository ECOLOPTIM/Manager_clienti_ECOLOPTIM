"""Compact inline upload/download controls beside each workflow milestone."""
from datetime import date
import streamlit as st
from db import iugn, iugn_rules as rules, iugn_step_documents as documents
from config.iugn_step_documents import KINDS, DOCUMENT_FACTS, REQUIRED_KINDS


def _can_write(state,step):
    try:return iugn.can_record(state,step)
    except PermissionError:return False


def _downloads(lid,items,prefix):
    if not items:
        st.caption('Nu exista documente pentru aceasta etapa.')
    for item in items:
        origin=item.get('origin','uploaded')
        label=item.get('label') or KINDS.get(item['step_key'],{}).get(item['kind'],item['kind'])
        st.caption(label+' | '+str(item.get('reference') or item.get('document_date') or ''))
        try:
            data,name,mime=documents.download(lid,origin,item.get('id',lid))
        except (ValueError,PermissionError,OSError) as exc:
            st.error(str(exc));continue
        st.download_button('↓ '+name,data,file_name=name,mime=mime,
            key=f"{prefix}_file_{origin}_{item.get('id',lid)}")


def _upload(lid,step,state,revision,items,prefix,cache):
    kinds=KINDS[step]
    kind=st.selectbox('Tip document',list(kinds),format_func=kinds.get,key=prefix+'_kind')
    problem=rules.blocked_reason(state,step)
    done=step in state['facts']
    can_confirm=not problem and not done and not (step=='contract_semnat' and kind=='mandat_semnat')
    if problem and not done:st.caption('Documentul poate fi pastrat acum. Confirmarea etapei asteapta: '+problem)
    if step=='contract_semnat' and kind=='mandat_semnat':
        st.caption('Mandatul semnat se pastreaza separat. Nu confirma semnarea contractului de prestari servicii.')
    have={item['kind'] for item in items}|{kind}
    default_confirm=step in DOCUMENT_FACTS and REQUIRED_KINDS.get(step,set())<=have
    with st.form(prefix+'_upload_form',clear_on_submit=True):
        uploads=st.file_uploader('Alege documentele',accept_multiple_files=True,key=prefix+'_files')
        cols=st.columns(2)
        day=cols[0].date_input('Data documentului / evenimentului',value=date.today(),max_value=date.today())
        reference=cols[1].text_input('Numar / referinta documentului')
        scheduled='';team=''
        if step in {'executie_programata','programare_pif_primita'}:
            scheduled=st.date_input('Data programata pentru etapa',value=date.today())
        if step in {'executie_programata','echipa_pif_alocata'}:
            team=st.text_input('Echipa pentru etapa')
        note=st.text_input('Observatii document')
        confirm=st.checkbox('Confirma etapa pe baza documentelor si a actiunii efectuate',
            value=bool(default_confirm and can_confirm),disabled=not can_confirm)
        if step not in DOCUMENT_FACTS and can_confirm:
            st.caption('Bifeaza confirmarea numai dupa efectuarea actiunii: trimitere, incasare, executie sau predare, dupa caz.')
        save=st.form_submit_button('Salveaza documentele')
    if save:
        try:
            result=documents.upload(lid,step,kind,[(f.name,f.getvalue()) for f in uploads],
                expected_revision=revision,occurred_on=str(day),confirm=bool(confirm and can_confirm),
                reference=reference,note=note,scheduled_for=str(scheduled),team=team)
        except (ValueError,PermissionError,OSError) as exc:st.error(str(exc))
        else:
            st.session_state[prefix+'_message']='Documente salvate. '+('Etapa a fost confirmata.' if result['confirmed'] else 'Starea etapei este pastrata.')
            st.session_state.pop(cache,None)
            st.rerun()
    if st.session_state.get(prefix+'_message'):
        st.success(st.session_state.pop(prefix+'_message'))


def render(lid,state,revision,live_revision,prefix,cache):
    items=documents.list_for_work(lid)
    active=st.session_state.get(prefix+'_doc_panel')
    header=st.columns([4,1.1,1.3,.6,.65])
    for col,label in zip(header,('Etapa','Stare','Data','Incarca','Fisiere')):col.caption(label)
    stream_before=None
    for step,label,stream,role,_ in rules.STEPS:
        if stream!=stream_before:
            st.caption(stream.upper());stream_before=stream
        rows=[item for item in items if item['step_key']==step]
        cols=st.columns([4,1.1,1.3,.6,.65],vertical_alignment='center')
        cols[0].write(label)
        done=step in state['facts'];problem=rules.blocked_reason(state,step)
        cols[1].caption('✓ Finalizat' if done else 'In asteptare' if problem else 'Disponibil')
        cols[2].caption(state['facts'].get(step,{}).get('date','') or '—')
        if step in KINDS:
            allowed=_can_write(state,step) and revision==live_revision
            if cols[3].button('↑',key=prefix+'_up_'+step,help='Incarca documente pentru '+label,disabled=not allowed):
                st.session_state[prefix+'_doc_panel']=(step,'upload');st.rerun()
        if rows:
            if cols[4].button('↓ '+str(len(rows)),key=prefix+'_down_'+step,help='Descarca documentele etapei'):
                st.session_state[prefix+'_doc_panel']=(step,'download');st.rerun()
        else:cols[4].caption('—')
        if step=='contract_semnat' and any(item['kind']=='mandat_semnat' for item in rows):
            cols[0].caption('✓ Mandat semnat incarcat')
        if active and active[0]==step:
            with st.container(border=True):
                close_cols=st.columns([5,1])
                close_cols[0].markdown('**'+label+' · Documente**')
                if close_cols[1].button('Inchide',key=prefix+'_close_'+step):
                    st.session_state.pop(prefix+'_doc_panel',None);st.rerun()
                if problem and not done:st.caption(problem)
                if active[1]=='upload' and step in KINDS:
                    if _can_write(state,step) and revision==live_revision:
                        _upload(lid,step,state,revision,rows,prefix+'_'+step,cache)
                    else:st.info('Reincarca fluxul sau verifica drepturile pentru aceasta etapa.')
                else:_downloads(lid,rows,prefix+'_'+step)
    st.caption('↑ Incarca langa etapa · ↓ Descarca originale emise si exemplare incarcate. Fiecare document ramane legat de lucrare si de etapa.')
