"""One immutable mandate per issued IUGN contract, sharing its source snapshot."""
from contextlib import closing
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import secrets
from db import db,permissions,iugn
from db import iugn_documents as docs
from utils import iugn_mandate as mandate


def migrate(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS iugn_mandate_issues (
        lucrare_id INTEGER PRIMARY KEY REFERENCES iugn_contract_issues(lucrare_id) ON DELETE CASCADE,
        number TEXT UNIQUE NOT NULL, filename TEXT NOT NULL, path TEXT NOT NULL,
        sha256 TEXT NOT NULL, snapshot TEXT NOT NULL, issued_by TEXT NOT NULL, issued_at TEXT NOT NULL)''')


def template_hash():
    return hashlib.sha256(mandate.TEMPLATE.read_bytes()).hexdigest() if mandate.TEMPLATE.is_file() else None


def get(lid):
    permissions.require('read')
    with closing(db._connect()) as conn:
        return docs._row(conn,'SELECT * FROM iugn_mandate_issues WHERE lucrare_id=?',(int(lid),))


def persist(conn,lid,service,journal,expected_hash):
    if not expected_hash or template_hash()!=expected_hash:
        raise ValueError('Sablonul mandatului lipseste sau s-a modificat. Reincarca documentele.')
    if docs._row(conn,'SELECT number FROM iugn_mandate_issues WHERE lucrare_id=?',(lid,)):
        raise ValueError('Mandatul este deja emis. Foloseste documentul salvat.')
    source=json.loads(service['snapshot'])['context']
    number='MDT-'+service['number'].removeprefix('CTR-')
    values=mandate.context(source,number)
    data=mandate.generate(values)
    if len(data)>db.MAX_UPLOAD_BYTES:raise ValueError('Mandatul depaseste limita pentru atasamente.')
    if template_hash()!=expected_hash:raise ValueError('Sablonul mandatului s-a modificat. Reincarca documentele.')
    work=docs._row(conn,'SELECT client_id FROM lucrari WHERE id=?',(lid,))
    directory=Path(db.UPLOAD_DIR)/str(work['client_id']);directory.mkdir(parents=True,exist_ok=True)
    filename=f'{number}_MANDAT_IUGN_L-{lid}_{secrets.token_hex(4)}.docx'
    path=directory/filename
    with path.open('xb') as out:
        journal.append((lid,str(path)));out.write(data)
    sha=hashlib.sha256(data).hexdigest()
    snapshot=docs._dump({'context':values,'contract_number':service['number'],
                         'contract_sha256':service['sha256'],'template_sha256':expected_hash})
    at=datetime.now(timezone.utc).isoformat();actor=permissions.actor_username() or 'mentenanta locala'
    cur=conn.cursor()
    db._execute(cur,'INSERT INTO iugn_mandate_issues VALUES (?,?,?,?,?,?,?,?)',
                (lid,number,filename,str(path),sha,snapshot,actor,at))
    db._execute(cur,'''INSERT INTO atasamente(client_id,filename,path,uploaded_by,upload_date,lucrare_id,sarcina_id)
                      VALUES (?,?,?,?,?,?,NULL)''',(work['client_id'],filename,str(path),actor,at,lid))
    return {'number':number,'filename':filename,'data':data}


def cleanup(journal):
    # Preserve files after an ambiguous commit until reconciliation is possible.
    for lid,path in journal:
        try:
            with closing(db._connect()) as conn:
                saved=docs._row(conn,'SELECT number FROM iugn_mandate_issues WHERE lucrare_id=? AND path=?',(lid,path))
            if not saved:Path(path).unlink(missing_ok=True)
        except Exception:pass


def preview(lid):
    permissions.require('write')
    with closing(db._connect()) as conn:
        _,work=docs._records(conn,int(lid))
        service=docs._row(conn,'SELECT * FROM iugn_contract_issues WHERE lucrare_id=?',(lid,))
        if not service:raise ValueError('Emite mai intai contractul de prestari servicii.')
        if not iugn.can_record(iugn._load(conn,int(lid))['state'],'contract_emis'):
            raise PermissionError('Emiterea mandatului necesita rolul comercial al lucrarii.')
    digest=template_hash()
    values=mandate.context(json.loads(service['snapshot'])['context'],'PREVIZUALIZARE')
    data=mandate.generate(values)
    if template_hash()!=digest:raise ValueError('Sablonul mandatului s-a modificat. Reincarca documentele.')
    return {'data':data,'template_hash':digest,'contract_sha256':service['sha256'],
            'date':values['data_mandat']}


def issue_existing(lid,approved):
    permissions.require('write')
    journal=[]
    try:
        with closing(db._connect()) as conn,conn:
            if not db.DATABASE_URL:conn.execute('BEGIN IMMEDIATE')
            docs._records(conn,int(lid),True)
            service=docs._row(conn,'SELECT * FROM iugn_contract_issues WHERE lucrare_id=?',(int(lid),))
            if not service:raise ValueError('Emite mai intai contractul de prestari servicii.')
            if not iugn.can_record(iugn._load(conn,int(lid))['state'],'contract_emis'):
                raise PermissionError('Emiterea mandatului necesita rolul comercial al lucrarii.')
            if service['sha256']!=approved.get('contract_sha256') or approved.get('date')!=datetime.now().strftime('%d.%m.%Y'):
                raise ValueError('Previzualizarea nu mai este actuala. Reincarca documentele.')
            result=persist(conn,int(lid),service,journal,approved.get('template_hash'))
        return result
    except BaseException:
        cleanup(journal);raise
