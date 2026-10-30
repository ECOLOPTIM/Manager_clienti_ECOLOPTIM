"""Client/work prefill, editable contract draft, preview and final issuance."""
from datetime import date, datetime
from pathlib import Path
import streamlit as st
from db import iugn_documents as docs
from utils import iugn_contract as contract
from config.company_fields import COMPANY_FIELDS

LABELS={
 'beneficiar_nume':'Nume beneficiar / reprezentant','beneficiar_firma':'Denumire beneficiar persoana juridica',
 'beneficiar_cui':'CUI beneficiar','beneficiar_regcom':'Registrul Comertului beneficiar',
 'beneficiar_reprezentant_calitate':'Calitatea reprezentantului beneficiarului',
 'beneficiar_ci_serie':'Serie CI','beneficiar_ci_nr':'Numar CI',
 'beneficiar_ci_emitent':'CI eliberata de','beneficiar_ci_data':'Data eliberarii CI',
 'client_telefon':'Telefon beneficiar','client_email':'E-mail beneficiar',
 'beneficiar_banca':'Banca beneficiar optional','beneficiar_iban':'IBAN beneficiar optional',
 'data_contract':'Data contractului','nr_oferta':'Numar oferta acceptata','data_oferta':'Data ofertei',
 'nr_deviz':'Numar deviz anexat','data_deviz':'Data devizului','durata_contract_zile':'Durata contractului in zile calendaristice',
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
        st.session_state.pop(key,None);st.session_state.pop(key+'_preview',None);st.rerun()
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
    missing=[COMPANY_FIELDS[n] for n,v in bundle['company']['values'].items()
             if not v and n in {'executant_email','autorizatie_proiectare_numar','autorizatie_proiectare_expirare',
                                'autorizatie_executie_numar','autorizatie_executie_expirare'}]
    if missing:st.warning('Completeaza Date generale: '+', '.join(missing))
    st.caption('Numarul se aloca numai la emitere. Sumele sunt cu TVA; taxele Distrigaz sunt separate.')
    defaults={n:bundle['client'].get(src) or '' for n,src in contract.CLIENT_FIELDS.items()}
    defaults.update({n:bundle['work'].get(src) or '' for n,src in contract.WORK_FIELDS.items()})
    defaults.update(bundle['terms'])
    if not defaults.get('descriere_lucrare'):
        defaults['descriere_lucrare']=bundle['work'].get('tip_lucrare') or 'Instalatie de utilizare a gazelor naturale'
    if not defaults.get('documente_detectoare_beneficiar'):
        defaults['documente_detectoare_beneficiar']='Nu este cazul.'
    if not defaults.get('defalcare_avize') and not defaults.get('valoare_avize'):
        defaults['defalcare_avize']='Nu sunt incluse avize in pret.'
    st.caption('Pentru previzualizare, datele GDPR sau devizul inca lipsa sunt marcate in document. '
               'Datele obligatorii se verifica integral inainte de emitere.')
    kind=st.selectbox('Tip beneficiar',['PF','PJ'],index=1 if defaults.get('beneficiar_tip')=='PJ' else 0,key=key+'_kind')
    correspondence=st.checkbox('Adresa de corespondenta diferita',value=bool(defaults.get('corespondenta_diferita')),key=key+'_correspondence')
    values={'beneficiar_tip':kind,'corespondenta_diferita':correspondence}
    with st.form(key+f"_form_{bundle['draft_revision']}"):
        for group,names in [
            ('Beneficiar', ['beneficiar_nume']+(['beneficiar_firma','beneficiar_cui','beneficiar_regcom','beneficiar_reprezentant_calitate'] if kind=='PJ'
                else ['beneficiar_ci_serie','beneficiar_ci_nr','beneficiar_ci_emitent','beneficiar_ci_data'])+
                ['client_telefon','client_email','beneficiar_banca','beneficiar_iban']),
            ('Domiciliul sau sediul beneficiarului',['beneficiar_'+p for p in contract.ADDRESS_PARTS]),
            ('Adresa lucrarii',['adresa_'+p for p in contract.ADDRESS_PARTS]),
            ('Adresa de corespondenta',['corespondenta_'+p for p in contract.ADDRESS_PARTS] if correspondence else []),
            ('Contract oferta si deviz',['data_contract','nr_oferta','data_oferta','nr_deviz','data_deviz','durata_contract_zile','descriere_lucrare','documente_detectoare_beneficiar']),
            ('Pret si transe',[*contract.MONEY_INPUTS,'defalcare_avize','avans_procent']),
        ]:
            if not names:continue
            st.markdown('**'+group+'**')
            for name in names:
                label=LABELS.get(name,name.split('_',1)[-1].replace('_',' ').capitalize())
                val=defaults.get(name,'')
                if name in contract.MONEY_INPUTS or name in ('avans_procent','durata_contract_zile'):
                    fallback=50 if name=='avans_procent' else 90 if name=='durata_contract_zile' else 0
                    try:number=float(val) if str(val) else float(fallback)
                    except (ValueError,TypeError):number=float(fallback)
                    values[name]=st.number_input(label,value=number,min_value=0.0,step=1.0 if name in ('avans_procent','durata_contract_zile') else 0.01,key=key+'_'+name)
                elif name.endswith('_data') or name.startswith('data_'):
                    dt=_date(val) or (date.today() if name=='data_contract' else None)
                    chosen=st.date_input(label,value=dt,format='DD.MM.YYYY',key=key+'_'+name)
                    values[name]=chosen.isoformat() if chosen else ''
                elif name in ('descriere_lucrare','documente_detectoare_beneficiar','defalcare_avize'):
                    values[name]=st.text_area(label,value=str(val),key=key+'_'+name)
                else:values[name]=st.text_input(label,value=str(val),key=key+'_'+name)
        save=st.form_submit_button('Salveaza ciorna contractului')
        check=st.form_submit_button('Verifica si previzualizeaza')
    if save or check:
        try:
            rev=docs.save_draft(lid,values,expected_revision=bundle['draft_revision'])
            bundle['draft_revision']=rev;bundle['terms']=values
            st.session_state.pop(key+'_preview',None)
            if check:
                data=docs.preview(bundle,values)
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
        if st.button('Emite si salveaza contractul in dosar',key=key+'_issue'):
            try:
                docs.issue(lid,bundle,approved['terms'])
            except (ValueError,PermissionError,OSError) as exc:st.error(_message(exc))
            else:
                st.session_state.pop(key,None);st.session_state.pop(key+'_preview',None)
                st.session_state.pop(f'iugn_{bundle["client"]["id"]}_{lid}_snapshot',None)
                st.rerun()
