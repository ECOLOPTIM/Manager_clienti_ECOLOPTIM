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
    form_prefix=prefix+'_'+kind
    with st.form(form_prefix+'_upload_form',clear_on_submit=True):
        uploads=st.file_uploader('Alege documentele',accept_multiple_files=True,key=form_prefix+'_files')
        cols=st.columns(3)
        day=cols[0].date_input('Data documentului / evenimentului',value=date.today(),max_value=date.today())
        reference=cols[1].text_input('Numar / referinta documentului')
        scheduled='';team=''
        if step in {'executie_programata','programare_pif_primita'}:
            scheduled=st.date_input('Data programata pentru etapa',value=date.today())
        if step in {'executie_programata','echipa_pif_alocata'}:
            team=st.text_input('Echipa pentru etapa')
        note=cols[2].text_input('Observatii document')
        confirm=st.checkbox('Confirma etapa dupa salvare',
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


FILTERS=('Toate', 'De facut', 'Cu documente', 'Finalizate')
STREAM_LABELS={'dosar':'Dosar si contracte', 'proiect':'Proiectare', 'executie':'Executie', 'pif':'Punere in functiune'}


def visible_steps(state,items,selection):
    with_files={item['step_key'] for item in items}
    return [row for row in rules.STEPS if (
        selection=='Toate' or
        selection=='De facut' and row[0] not in state['facts'] or
        selection=='Cu documente' and row[0] in with_files or
        selection=='Finalizate' and row[0] in state['facts'])]


def _clear_panel(prefix):
    st.session_state.pop(prefix+'_doc_panel',None)


def _quick_original(lid,item,prefix):
    try:
        data,name,mime=documents.download(lid,item['origin'],lid)
    except (ValueError,PermissionError,OSError) as exc:
        st.error(str(exc));return
    st.download_button(item['label'],data,file_name=name,mime=mime,
        icon=':material/download:',key=prefix+'_quick_'+item['kind'],help=name)


def _row(lid,row,state,revision,live_revision,items,prefix,cache,active):
    step,label,stream,role,_=row
    rows=[item for item in items if item['step_key']==step]
    done=step in state['facts'];problem=rules.blocked_reason(state,step)
    allowed=_can_write(state,step) and revision==live_revision
    cols=st.columns([5,3,1.5],vertical_alignment='center')
    badge=':green[✓ Finalizat]' if done else ':orange[De continuat]' if not problem else ':gray[In asteptare]'
    cols[0].markdown('**'+label+'**')
    owner='Gelu' if role=='manager' else state['roles'].get(role,'')
    metadata=[badge]
    if done:metadata.append(state['facts'][step]['date'])
    if owner:metadata.append(owner)
    cols[0].caption(' · '.join(metadata))
    originals=[item for item in rows if item.get('origin')]
    if originals:
        with cols[1]:
            for item in originals:_quick_original(lid,item,prefix+'_'+step)
    elif rows:
        labels=list(dict.fromkeys(KINDS.get(step,{}).get(item['kind'],item['kind']) for item in rows))
        cols[1].caption(' · '.join(labels))
        if cols[1].button(str(len(rows))+' documente',icon=':material/folder_open:',
                key=prefix+'_down_'+step,help='Vezi si descarca fisierele acestei etape',type='tertiary'):
            st.session_state[prefix+'_doc_panel']=(step,'download');st.rerun()
    elif step in KINDS:
        cols[1].caption('Fara documente')
    if step=='contract_semnat':
        have={item['kind'] for item in rows}
        for kind,text in (('contract_semnat','Contract'),('mandat_semnat','Mandat')):
            if cols[2].button(text,icon=':material/upload:',key=prefix+'_up_'+step+'_'+kind,
                    help='Incarca '+KINDS[step][kind].lower(),disabled=not allowed,type='tertiary'):
                st.session_state[prefix+'_'+step+'_kind']=kind
                st.session_state[prefix+'_doc_panel']=(step,'upload');st.rerun()
        cols[1].caption(('✓' if 'contract_semnat' in have else '○')+' Contract semnat  ·  '+
                        ('✓' if 'mandat_semnat' in have else '○')+' Mandat semnat')
        if 'mandat_semnat' in have:cols[0].caption('✓ Mandat semnat incarcat')
    elif step in KINDS:
        if cols[2].button('Incarca',icon=':material/upload:',key=prefix+'_up_'+step,
                help='Incarca documente pentru '+label,disabled=not allowed,type='tertiary'):
            st.session_state[prefix+'_doc_panel']=(step,'upload');st.rerun()
    if active and active[0]==step:
        with st.container(border=True):
            close=st.columns([6,1])
            close[0].markdown('**'+label+'**')
            if close[1].button('Inchide',key=prefix+'_close_'+step):
                _clear_panel(prefix);st.rerun()
            if problem and not done:st.caption(problem)
            if rows:
                st.markdown('**Documentele etapei**')
                _downloads(lid,rows,prefix+'_'+step)
            if step in KINDS and allowed:
                with st.expander('Incarca documente',expanded=active[1]=='upload'):
                    _upload(lid,step,state,revision,rows,prefix+'_'+step,cache)
            elif active[1]=='upload':
                st.info('Reincarca fluxul sau verifica drepturile pentru aceasta etapa.')


def render(lid,state,revision,live_revision,prefix,cache):
    items=documents.list_for_work(lid)
    active=st.session_state.get(prefix+'_doc_panel')
    total=len(rules.STEPS);done=sum(row[0] in state['facts'] for row in rules.STEPS)
    st.progress(done/total,text=f'{done} din {total} etape finalizate')
    ready=[label for step,label,*_ in rules.STEPS if not rules.blocked_reason(state,step)]
    if ready:st.info('De continuat: '+ ' · '.join(ready[:3])+(' · ...' if len(ready)>3 else ''))
    selection=st.radio('Afiseaza etapele',FILTERS,horizontal=True,key=prefix+'_doc_filter',
        label_visibility='collapsed',on_change=_clear_panel,args=(prefix,))
    filtered=visible_steps(state,items,selection)
    focus_stream=next((row[2] for row in rules.STEPS if not rules.blocked_reason(state,row[0])),None)
    if not filtered:st.caption('Nu exista etape pentru filtrul ales.')
    for index,(stream,title) in enumerate(STREAM_LABELS.items(),1):
        group=[row for row in filtered if row[2]==stream]
        if not group:continue
        all_group=[row for row in rules.STEPS if row[2]==stream]
        finished=sum(row[0] in state['facts'] for row in all_group)
        count=sum(item['step_key'] in {row[0] for row in all_group} for item in items)
        expanded=(selection!='Toate' or stream==focus_stream
                  or bool(active and active[0] in {row[0] for row in group}))
        with st.expander(f'{index:02d}  {title}  ·  {finished}/{len(all_group)} etape  ·  {count} documente',expanded=expanded):
            for row in group:_row(lid,row,state,revision,live_revision,items,prefix,cache,active)
    st.caption('Originalele emise si exemplarele semnate sunt pastrate separat, in dosarul lucrarii.')
