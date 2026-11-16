"""Client/work prefill, editable contract draft, preview and final issuance."""
from datetime import date, datetime
from pathlib import Path
import streamlit as st
from db import iugn_documents as docs
from utils import iugn_contract as contract
from config.company_fields import COMPANY_FIELDS

LABELS={
 **contract.deadlines.STAGE_LABELS,
 'beneficiar_nume':'Nume beneficiar / reprezentant','beneficiar_firma':'Denumire beneficiar persoana juridica',
 'beneficiar_cui':'CUI beneficiar','beneficiar_regcom':'Registrul Comertului beneficiar',
 'beneficiar_reprezentant_calitate':'Calitatea reprezentantului beneficiarului',
 'beneficiar_ci_serie':'Serie CI','beneficiar_ci_nr':'Numar CI',
 'beneficiar_ci_emitent':'CI eliberata de','beneficiar_ci_data':'Data eliberarii CI',
 'client_telefon':'Telefon beneficiar','client_email':'E-mail beneficiar',
 'beneficiar_banca':'Banca beneficiar optional','beneficiar_iban':'IBAN beneficiar optional',
 'data_contract':'Data contractului','nr_oferta':'Numar deviz-oferta','data_oferta':'Data devizului-oferta',
 'nr_deviz':'Numar deviz-oferta','data_deviz':'Data devizului-oferta','durata_contract_zile':'Durata contractului in zile calendaristice',
 'descriere_lucrare':'Descrierea si continutul lucrarii','documente_detectoare_beneficiar':'Documente detectoare furnizate de beneficiar sau nu este cazul',
 'valoare_proiectare':'Proiectare cu TVA','valoare_verificare':'Verificare proiect cu TVA',
 'valoare_avize':'Avize incluse cu TVA','defalcare_avize':'Explicatii pentru avizele incluse sau nu este cazul',
 'valoare_executie_receptie':'Executie probe si receptie cu TVA','valoare_asistenta_pif':'Demersuri si participare PIF cu TVA',
 'avans_procent':'Avans convenit procent',
}


def _date(value):
    for fmt in ('%Y-%m-%d','%d.%m.%Y'):
        try:return datetime.strptime(str(value),fmt).date()
        except ValueError:pass
    return None


def _message(error):
    text=str(error)
    labels={**LABELS,**COMPANY_FIELDS}
    for prefix,label in [('beneficiar_','Domiciliu / sediu'),('adresa_','Adresa lucrarii'),('corespondenta_','Corespondenta')]:
        for part in contract.ADDRESS_PARTS:
            labels[prefix+part]=label+' - '+part.replace('_',' ')
    for name in sorted(labels,key=len,reverse=True):
        text=text.replace(name,labels[name])
    return text


def render(lid):
    st.subheader('Contract IUGN cu anexe')
    if not contract.TEMPLATE.exists():
        st.info('Instaleaza sablonul aprobat ca templates/contract_iugn.docx in aceasta copie a aplicatiei.')
        return
    key=f'iugn_contract_bundle_{lid}'
    if key not in st.session_state: st.session_state[key]=docs.open_form(lid)
    bundle=st.session_state[key]
    if st.button('Reincarca datele contractului',key=key+'_reload'):
        for state_key in list(st.session_state):
            if state_key.startswith(key):st.session_state.pop(state_key,None)
        st.rerun()
    issued=bundle['issued']
    if issued:
        st.success('Contract emis: '+issued['number'])
        st.caption('Documentul emis este pastrat in dosar. Semnatura se confirma separat din exemplarul semnat.')
        path=Path(issued['path'])
        if path.is_file():
            data=path.read_bytes()
            import hashlib
            if hashlib.sha256(data).hexdigest()!=issued['sha256']:
                st.error('Fisierul salvat nu corespunde documentului emis. Verifica arhiva.')
            else:st.download_button('Descarca contractul emis',data,file_name=issued['filename'],key=key+'_issued')
        else: st.error('Fisierul emis lipseste din arhiva. Restaureaza documentul din backup.')
        return
    if st.button('Editeaza clientul',key=key+'_client_edit'):
        st.session_state[key+'_editing_client']=True
    if st.session_state.get(key+'_editing_client'):
        from tabs.components.client_profile import render_editor
        if render_editor(int(bundle['client']['id'])):
            for state_key in list(st.session_state):
                if state_key.startswith(key):st.session_state.pop(state_key,None)
            st.rerun()
        return
    client=bundle['client']
    st.markdown('**Beneficiar — din fisa clientului**')
    st.write(str((client.get('firma') if client.get('beneficiar_tip')=='PJ' else client.get('nume')) or ''))
    st.caption(' · '.join(str(client.get(k) or '') for k in ('nume','telefon','email') if client.get(k)))
    if not client.get('profile_saved'):
        st.warning('Verifica si salveaza datele beneficiarului din Editeaza clientul inainte de emitere.')
    st.markdown('**Locul de consum — din lucrare**')
    st.write(', '.join(str(bundle['work'].get('adresa_'+p) or '') for p in ('judet','localitate','strada','numar','bloc','apartament') if bundle['work'].get('adresa_'+p)))
    st.caption('Adresa se modifica din editarea lucrarii.')
    missing=[COMPANY_FIELDS[n] for n,v in bundle['company']['values'].items()
             if not v and n in {'executant_email','autorizatie_proiectare_numar','autorizatie_proiectare_expirare',
                                'autorizatie_executie_numar','autorizatie_executie_expirare'}]
    if missing:st.warning('Completeaza Date generale: '+', '.join(missing))
    st.caption('Numarul se aloca numai la emitere. Sumele sunt cu TVA; taxele Distrigaz sunt separate.')
    defaults=dict(bundle['beneficiary_defaults'])
    if bundle['beneficiary_inherited']:
        st.caption('Datele beneficiarului lipsa din fisa clientului au fost preluate din documentele anterioare ale aceluiasi client. Verifica daca mai sunt actuale.')
    defaults.update({n:bundle['work'].get(src) or '' for n,src in contract.WORK_FIELDS.items()})
    defaults.update(contract.offer_as_estimate(bundle['terms']))
    defaults.update(bundle['beneficiary_defaults'])
    defaults.update({k:bundle['work'].get(k) or '' for k in contract.WORK_FIELDS if k.startswith('adresa_')})
    legacy=bundle['terms']
    if (legacy.get('nr_oferta') and legacy.get('nr_deviz') and legacy['nr_oferta']!=legacy['nr_deviz'] or
            legacy.get('data_oferta') and legacy.get('data_deviz') and _date(legacy['data_oferta'])!=_date(legacy['data_deviz'])):
        st.warning('Ciorna veche contine doua referinte diferite. Verifica devizul-oferta afisat; la salvare se foloseste o singura referinta.')
    if not defaults.get('descriere_lucrare'):
        defaults['descriere_lucrare']=bundle['work'].get('tip_lucrare') or 'Instalatie de utilizare a gazelor naturale'
    if not defaults.get('documente_detectoare_beneficiar'):
        defaults['documente_detectoare_beneficiar']='Nu este cazul.'
    if not defaults.get('defalcare_avize') and not defaults.get('valoare_avize'):
        defaults['defalcare_avize']='Nu sunt incluse avize in pret.'
    st.caption('Pentru previzualizare, datele GDPR sau devizul inca lipsa sunt marcate in document. '
               'Datele obligatorii se verifica integral inainte de emitere.')
    kind=defaults.get('beneficiar_tip') or ('PJ' if client.get('firma') else 'PF')
    correspondence=st.checkbox('Adresa de corespondenta diferita',value=bool(defaults.get('corespondenta_diferita')),key=key+'_correspondence')
    st.caption('Devizul-oferta este un singur document, cu un singur numar si o singura data.')
    values={**{k:defaults.get(k,'') for k in docs.BENEFICIARY_FIELDS},
            **{k:defaults.get(k,'') for k in contract.WORK_FIELDS if k.startswith('adresa_')},
            'beneficiar_tip':kind,'corespondenta_diferita':correspondence}
    with st.form(key+'_form'):
        for group,names in [
            ('Adresa de corespondenta',['corespondenta_'+p for p in contract.ADDRESS_PARTS] if correspondence else []),
            ('Contract si deviz-oferta',['data_contract','nr_oferta','data_oferta','durata_contract_zile',*contract.deadlines.STAGE_DEFAULTS,'descriere_lucrare','documente_detectoare_beneficiar']),
            ('Pret si transe',[*contract.MONEY_INPUTS,'defalcare_avize','avans_procent']),
        ]:
            if not names:continue
            st.markdown('**'+group+'**')
            short=[n for n in names if n not in ('descriere_lucrare','documente_detectoare_beneficiar','defalcare_avize')]
            columns={}
            for start in range(0,len(short),3):
                columns.update(zip(short[start:start+3],st.columns(3)))
            for name in names:
                field_ui=columns.get(name,st)
                label=LABELS.get(name,name.split('_',1)[-1].replace('_',' ').capitalize())
                val=defaults.get(name,'')
                if name in contract.MONEY_INPUTS or name in ('avans_procent','durata_contract_zile') or name in contract.deadlines.STAGE_DEFAULTS:
                    fallback=50 if name=='avans_procent' else 90 if name=='durata_contract_zile' else contract.deadlines.STAGE_DEFAULTS.get(name,0)
                    try:number=float(val) if str(val) else float(fallback)
                    except (ValueError,TypeError):number=float(fallback)
                    values[name]=field_ui.number_input(label,value=number,min_value=0.0,step=1.0 if name in ('avans_procent','durata_contract_zile') or name in contract.deadlines.STAGE_DEFAULTS else 0.01,key=key+'_'+name)
                elif name.endswith('_data') or name.startswith('data_'):
                    dt=_date(val) or (date.today() if name=='data_contract' else None)
                    chosen=field_ui.date_input(label,value=dt,format='DD.MM.YYYY',key=key+'_'+name)
                    values[name]=chosen.isoformat() if chosen else ''
                elif name in ('descriere_lucrare','documente_detectoare_beneficiar','defalcare_avize'):
                    values[name]=field_ui.text_area(label,value=str(val),key=key+'_'+name)
                else:values[name]=field_ui.text_input(label,value=str(val),key=key+'_'+name)
        save=st.form_submit_button('Salveaza ciorna contractului')
        check=st.form_submit_button('Verifica si previzualizeaza')
    if save or check:
        values=contract.offer_as_estimate(values)
        try:
            rev=docs.save_draft(lid,values,expected_revision=bundle['draft_revision'])
            bundle['draft_revision']=rev;bundle['terms']=values
            st.session_state.pop(key+'_preview',None)
            if check:
                data=docs.preview(bundle,values)
                plan=contract.deadlines.budget(values,values['data_contract'])
                st.info('Incadrare de baza: receptie estimata '+plan['reception'].strftime('%d.%m.%Y')+'; termen total estimat '+plan['expiry'].strftime('%d.%m.%Y')+'. Asteptarea documentelor, programarile si PIF trebuie sa incapa in timpul ramas. Data efectiva de inceput este semnarea contractului.')
                st.session_state[key+'_preview']={'terms':values,'data':data}
            else:st.success('Ciorna salvata. Datele clientului si ale lucrarii nu au fost modificate.')
        except (ValueError,PermissionError,OSError) as exc:st.error(_message(exc))
    approved=st.session_state.get(key+'_preview')
    if approved and (approved['terms']['beneficiar_tip']!=kind or
                     approved['terms']['corespondenta_diferita']!=correspondence):
        st.session_state.pop(key+'_preview',None)
        approved=None
    if approved:
        st.download_button('Descarca previzualizarea DOCX',approved['data'],file_name=f'PREVIZUALIZARE_IUGN_L-{lid}.docx',key=key+'_download')
        st.caption('La emitere se folosesc datele previzualizate. Pentru modificari apasa din nou Verifica si previzualizeaza.')
        if st.button('Emite si salveaza contractul in dosar',key=key+'_issue',disabled=not client.get('profile_saved')):
            try:
                docs.issue(lid,bundle,approved['terms'])
            except (ValueError,PermissionError,OSError) as exc:st.error(_message(exc))
            else:
                st.session_state.pop(key,None);st.session_state.pop(key+'_preview',None)
                st.session_state.pop(f'iugn_{bundle["client"]["id"]}_{lid}_snapshot',None)
                st.rerun()
