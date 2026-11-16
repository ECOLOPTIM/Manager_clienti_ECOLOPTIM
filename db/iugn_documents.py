"""Atomic IUGN contract issuance with immutable snapshot and linked attachment."""
from contextlib import closing
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets

from db import company, db, iugn, iugn_rules as rules, permissions
from utils import iugn_contract as contract


def migrate(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS iugn_contract_drafts (
        lucrare_id INTEGER PRIMARY KEY REFERENCES lucrari(id), revision INTEGER NOT NULL,
        payload TEXT NOT NULL, updated_by TEXT NOT NULL, updated_at TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS iugn_contract_issues (
        lucrare_id INTEGER PRIMARY KEY REFERENCES lucrari(id), number TEXT UNIQUE NOT NULL,
        filename TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL,
        snapshot TEXT NOT NULL, issued_by TEXT NOT NULL, issued_at TEXT NOT NULL)''')


def _dump(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,default=str,allow_nan=False)


def fingerprint(value):
    return hashlib.sha256(_dump(value).encode()).hexdigest()


def _row(conn, sql, args):
    cur=conn.cursor();db._execute(cur,sql,args);row=cur.fetchone()
    return dict(zip([c[0] for c in cur.description],row)) if row else None


def _records(conn,lid,lock=False):
    work=_row(conn,'SELECT * FROM lucrari WHERE id=?'+(' FOR UPDATE' if lock and db.DATABASE_URL else ''),(lid,))
    if not work or work['tip_lucrare']!=rules.WORK_TYPE:
        raise ValueError('Contractul IUGN este disponibil pentru instalatia de utilizare noua.')
    client=_row(conn,'SELECT * FROM clienti WHERE id=?'+(' FOR SHARE' if lock and db.DATABASE_URL else ''),(work['client_id'],))
    if not client: raise ValueError('Clientul nu mai exista.')
    client.pop('cnp',None)
    return client,work


# Reuse identity/contact only; work address, prices, signatures and document numbers
# always belong to their own work and must never cross this boundary.
BENEFICIARY_FIELDS = set(contract.CLIENT_FIELDS) | {
    'beneficiar_tip','beneficiar_cui','beneficiar_regcom','beneficiar_reprezentant_calitate',
    'beneficiar_banca','beneficiar_iban'}


def _beneficiary_defaults(conn,client,lid):
    if client.get('profile_saved'):
        return {k:client.get(src) or '' for k,src in contract.CLIENT_FIELDS.items()},False
    cur=conn.cursor()
    db._execute(cur,"""SELECT d.payload AS content,d.updated_at AS saved_at,'draft' AS source_kind
        FROM iugn_contract_drafts d JOIN lucrari l ON l.id=d.lucrare_id
        WHERE l.client_id=? AND l.id<>?
        UNION ALL
        SELECT i.snapshot AS content,i.issued_at AS saved_at,'issued' AS source_kind
        FROM iugn_contract_issues i JOIN lucrari l ON l.id=i.lucrare_id
        WHERE l.client_id=? AND l.id<>?
        ORDER BY saved_at DESC LIMIT 20""",(client['id'],lid,client['id'],lid))
    fallback={}
    for content,_,kind in cur.fetchall():
        saved=json.loads(content)
        values=saved['context'] if kind=='issued' else saved
        fallback={k:v for k,v in values.items() if k in BENEFICIARY_FIELDS and str(v or '').strip()}
        if fallback:break
    inherited=bool(fallback)
    # A partially updated address or identity document is one coherent group:
    # never complete a new CI number with an old CI series/date, or a new address
    # with pieces of a previous address.
    for group in (
        {'beneficiar_'+p for p in contract.ADDRESS_PARTS},
        {'beneficiar_ci_serie','beneficiar_ci_nr','beneficiar_ci_emitent','beneficiar_ci_data'},
    ):
        def normalized(k,v):
            text=str(v or '').strip()
            if k=='beneficiar_ci_data' and text:
                try:return contract.deadlines.as_date(text).isoformat()
                except ValueError:pass
            return text.casefold()
        changed=any(normalized(k,client.get(contract.CLIENT_FIELDS[k])) and
                    normalized(k,client.get(contract.CLIENT_FIELDS[k]))!=normalized(k,fallback.get(k))
                    for k in group if k in contract.CLIENT_FIELDS)
        if changed:
            for k in group:fallback.pop(k,None)
    current_firm=str(client.get('firma') or '').strip()
    if current_firm and fallback.get('beneficiar_firma') and current_firm!=fallback['beneficiar_firma']:
        for k in ('beneficiar_cui','beneficiar_regcom','beneficiar_reprezentant_calitate'):
            fallback.pop(k,None)
    fallback.update({k:client[src] for k,src in contract.CLIENT_FIELDS.items() if str(client.get(src) or '').strip()})
    return fallback,inherited


def open_form(lid):
    permissions.require('write')
    with closing(db._connect()) as conn:
        client,work=_records(conn,int(lid))
        draft=_row(conn,'SELECT * FROM iugn_contract_drafts WHERE lucrare_id=?',(lid,))
        issued=_row(conn,'SELECT * FROM iugn_contract_issues WHERE lucrare_id=?',(lid,))
        beneficiary_defaults,inherited=_beneficiary_defaults(conn,client,int(lid))
    return {'client':client,'work':work,'company':company.get(),
            'beneficiary_defaults':beneficiary_defaults,'beneficiary_inherited':inherited,
            'draft_revision':draft['revision'] if draft else 0,
            'terms':{k:v for k,v in json.loads(draft['payload']).items() if k!='beneficiar_cnp'} if draft else {},'issued':issued,
            'template_hash':hashlib.sha256(contract.TEMPLATE.read_bytes()).hexdigest()}


def save_draft(lid,terms,*,expected_revision):
    permissions.require('write')
    if type(expected_revision) is not int or expected_revision<0:
        raise ValueError('Revizie de ciorna invalida.')
    # Persist only contract fields; company data is controlled through Date generale.
    from config.company_fields import COMPANY_FIELDS
    terms=contract.offer_as_estimate({name:value for name,value in terms.items() if name!='beneficiar_cnp'})
    names=contract.template_variables() | set(contract.deadlines.STAGE_DEFAULTS)
    if set(terms)-names or set(terms)&COMPANY_FIELDS.keys() or 'nr_contract' in terms:
        raise ValueError('Ciorna contine campuri nepermise.')
    actor=permissions.actor_username() or 'mentenanta locala'
    with closing(db._connect()) as conn, conn:
        if not db.DATABASE_URL: conn.execute('BEGIN IMMEDIATE')
        client,work=_records(conn,int(lid),True)
        if client.get('profile_saved'):
            terms={k:v for k,v in terms.items() if k not in BENEFICIARY_FIELDS and not k.startswith('adresa_')}
        if _row(conn,'SELECT number FROM iugn_contract_issues WHERE lucrare_id=?',(lid,)):
            raise ValueError('Contractul este deja emis; documentul se pastreaza nemodificat.')
        cur=conn.cursor()
        db._execute(cur,"INSERT INTO iugn_contract_drafts VALUES (?,0,'{}','','') ON CONFLICT(lucrare_id) DO NOTHING",(lid,))
        db._execute(cur,'''UPDATE iugn_contract_drafts SET payload=?,revision=revision+1,updated_by=?,updated_at=?
            WHERE lucrare_id=? AND revision=?''',(_dump(terms),actor,datetime.now(timezone.utc).isoformat(),lid,expected_revision))
        if cur.rowcount!=1: raise ValueError('Ciorna a fost modificata in alta sesiune. Reincarca documentele.')
    return expected_revision+1


def canonical_terms(client,work,terms):
    values=dict(terms)
    if client.get('profile_saved'):
        values.update({k:client.get(src) or '' for k,src in contract.CLIENT_FIELDS.items()})
    # Work addresses belong to the work, including intentional empty components.
    values.update({k:work.get(k) or '' for k in contract.WORK_FIELDS if k.startswith('adresa_')})
    return values


def preview(bundle,terms):
    permissions.require('write')
    firm=dict(bundle['company']['values'])
    for name in ('gdpr_pastrare_acte','gdpr_pastrare_contabil','gdpr_pastrare_contract','gdpr_pastrare_tehnic','gdpr_transferuri'):
        if not str(firm.get(name) or '').strip():
            firm[name]='NECONFIGURAT - numai pentru previzualizare'
    draft=contract.offer_as_estimate(dict(canonical_terms(bundle['client'],bundle['work'],terms),nr_contract='PREVIZUALIZARE'))
    if not str(draft.get('nr_deviz') or '').strip():draft['nr_deviz']='NECOMPLETAT'
    if not draft.get('data_deviz'):draft['data_deviz']=draft.get('data_contract') or date.today().isoformat()
    return contract.generate_contract(bundle['client'],bundle['work'],firm,draft)


def issue(lid,bundle,terms):
    permissions.require('write')
    filepath=None
    created=False
    try:
        with closing(db._connect()) as conn, conn:
            if not db.DATABASE_URL: conn.execute('BEGIN IMMEDIATE')
            client,work=_records(conn,int(lid),True)
            existing=_row(conn,'SELECT * FROM iugn_contract_issues WHERE lucrare_id=?',(lid,))
            if existing: raise ValueError('Contractul este deja emis. Foloseste documentul salvat.')
            if fingerprint(client)!=fingerprint(bundle['client']) or fingerprint(work)!=fingerprint(bundle['work']):
                raise ValueError('Clientul sau lucrarea s-a modificat. Reincarca documentele.')
            firm=_row(conn,'SELECT revision,payload FROM firma_config WHERE id=1'+(' FOR SHARE' if db.DATABASE_URL else ''),())
            draft=_row(conn,'SELECT revision,payload FROM iugn_contract_drafts WHERE lucrare_id=?',(lid,))
            if firm['revision']!=bundle['company']['revision'] or (draft['revision'] if draft else 0)!=bundle['draft_revision']:
                raise ValueError('Configuratia firmei sau ciorna s-a modificat. Reincarca documentele.')
            template_hash=hashlib.sha256(contract.TEMPLATE.read_bytes()).hexdigest()
            if template_hash!=bundle['template_hash']: raise ValueError('Sablonul s-a modificat. Reincarca documentele.')
            values=json.loads(firm['payload'])
            for item in company.authorizations(values):
                if not item['complete'] or item['status']=='expirata':
                    raise ValueError('Completeaza o autorizatie ANRE valabila pentru '+item['kind']+' in Date generale.')
            flow=iugn._load(conn,lid)
            if 'contract_emis' in flow['state']['facts']:
                raise ValueError('Exista deja o confirmare de emitere in flux. Verifica documentul existent.')
            if not iugn.can_record(flow['state'],'contract_emis'):
                raise PermissionError('Emiterea necesita persoana desemnata pentru rolul comercial.')
            reason=rules.blocked_reason(flow['state'],'contract_emis')
            if reason: raise ValueError(reason)
            if not client.get('profile_saved'):
                raise ValueError('Verifica si salveaza fisa clientului inainte de emiterea contractului.')
            terms=canonical_terms(client,work,terms)
            # Validate before allocating the number, then render inside the same transaction.
            contract.prepare_context(client,work,values,dict(terms,nr_contract='VALIDARE'))
            year=date.today().year;cur=conn.cursor()
            db._execute(cur,'''INSERT INTO contracte_seq(an,last_ctr) VALUES (?,1)
                ON CONFLICT(an) DO UPDATE SET last_ctr=contracte_seq.last_ctr+1 RETURNING last_ctr''',(year,))
            number=f'CTR-{year}-{int(cur.fetchone()[0]):04d}'
            final_terms=dict(terms,nr_contract=number)
            data=contract.generate_contract(client,work,values,final_terms)
            if len(data)>db.MAX_UPLOAD_BYTES: raise ValueError('Documentul depaseste limita pentru atasamente.')
            if hashlib.sha256(contract.TEMPLATE.read_bytes()).hexdigest()!=template_hash:
                raise ValueError('Sablonul s-a modificat in timpul generarii. Reincarca documentele.')
            context=contract.prepare_context(client,work,values,final_terms)
            filename=f'{number}_IUGN_L-{lid}_{secrets.token_hex(4)}.docx'
            directory=Path(db.UPLOAD_DIR)/str(client['id']);directory.mkdir(parents=True,exist_ok=True)
            filepath=directory/filename
            with filepath.open('xb') as output:
                created=True
                output.write(data)
            at=datetime.now(timezone.utc).isoformat();actor=permissions.actor_username() or 'mentenanta locala'
            sha=hashlib.sha256(data).hexdigest()
            snapshot=_dump({'context':context,'client':client,'work':work,
                'company_revision':firm['revision'],'template_sha256':template_hash})
            db._execute(cur,'INSERT INTO iugn_contract_issues VALUES (?,?,?,?,?,?,?,?)',
                        (lid,number,filename,str(filepath),sha,snapshot,actor,at))
            db._execute(cur,'''INSERT INTO atasamente(client_id,filename,path,uploaded_by,upload_date,lucrare_id,sarcina_id)
                VALUES (?,?,?,?,?,?,NULL)''',(client['id'],filename,str(filepath),actor,at,lid))
            occurred=datetime.strptime(context['data_contract'],'%d.%m.%Y').date().isoformat()
            iugn.record_event_in_transaction(conn,lid,'contract_emis',occurred,expected_revision=flow['revision'],
                note=f'{number}; document {filename}; SHA256 {sha}')
        return {'number':number,'filename':filename,'data':data}
    except BaseException:
        if created:
            # A lost commit acknowledgement is ambiguous. Never delete an issued
            # document unless a fresh read confirms it was not committed.
            try:
                with closing(db._connect()) as check:
                    saved=_row(check,'SELECT number FROM iugn_contract_issues WHERE lucrare_id=? AND path=?',(lid,str(filepath)))
                if not saved:filepath.unlink(missing_ok=True)
            except Exception:
                pass  # Keep the file for reconciliation if the DB is unavailable.
        raise


def contract_deadlines(lid,state):
    """Read immutable issued terms without exposing a client/company snapshot."""
    permissions.require('read')
    with closing(db._connect()) as conn:
        issued=_row(conn,'SELECT snapshot FROM iugn_contract_issues WHERE lucrare_id=?',(lid,))
    if not issued:return []
    return contract.deadlines.report(json.loads(issued['snapshot'])['context'],state)
