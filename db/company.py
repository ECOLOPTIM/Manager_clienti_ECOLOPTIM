"""Versioned company configuration persisted in the active SQLite/PostgreSQL DB."""
from calendar import monthrange
from contextlib import closing
from datetime import date, datetime, timezone
import json

from config.company_fields import COMPANY_FIELDS
from db import permissions


class SettingsConflict(ValueError):
    pass


def migrate(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS firma_config (
        id INTEGER PRIMARY KEY CHECK (id=1), revision INTEGER NOT NULL,
        payload TEXT NOT NULL, updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS firma_config_istoric (
        revision INTEGER PRIMARY KEY, payload TEXT NOT NULL,
        updated_at TEXT NOT NULL, updated_by TEXT NOT NULL)''')
    conn.execute("INSERT INTO firma_config VALUES (1,0,'{}','','') ON CONFLICT(id) DO NOTHING")


def get():
    from db import db
    with closing(db._connect()) as conn:
        row=conn.execute('SELECT revision,payload,updated_at,updated_by FROM firma_config WHERE id=1').fetchone()
    return {'revision':row[0], 'values':{**dict.fromkeys(COMPANY_FIELDS, ''), **json.loads(row[1])},
            'updated_at':row[2], 'updated_by':row[3]}


def save(values, *, expected_revision):
    permissions.require('admin')
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError('Versiune configuratie invalida.')
    if set(values) - COMPANY_FIELDS.keys():
        raise ValueError('Configuratia contine campuri necunoscute.')
    clean={}
    for name in COMPANY_FIELDS:
        value=values.get(name, '')
        if value is None: value=''
        if isinstance(value, date): value=value.isoformat()
        if not isinstance(value,str) or len(value)>5000:
            raise ValueError('Valoare invalida pentru ' + COMPANY_FIELDS[name])
        value=value.strip()
        if name.endswith('_expirare') and value:
            try:
                value=date.fromisoformat(value).isoformat()
            except ValueError:
                raise ValueError('Data invalida pentru ' + COMPANY_FIELDS[name]) from None
        clean[name]=value
    payload=json.dumps(clean, ensure_ascii=False, sort_keys=True)
    at=datetime.now(timezone.utc).isoformat()
    actor=permissions.actor_username() or 'mentenanta locala'
    from db import db
    with closing(db._connect()) as conn, conn:
        cur=conn.cursor()
        db._execute(cur, '''UPDATE firma_config SET revision=revision+1,payload=?,updated_at=?,updated_by=?
            WHERE id=1 AND revision=?''', (payload,at,actor,expected_revision))
        if cur.rowcount != 1:
            raise SettingsConflict('Datele generale au fost modificate in alta sesiune. Reincarca inainte de salvare.')
        db._execute(cur, 'INSERT INTO firma_config_istoric VALUES (?,?,?,?)',
                    (expected_revision+1,payload,at,actor))
    return expected_revision+1


def warning_date(expiry):
    """Three calendar months before expiry, clamped to the last day of month."""
    month_index=expiry.year*12+expiry.month-1-3
    year, month=divmod(month_index,12)
    return date(year,month+1,min(expiry.day,monthrange(year,month+1)[1]))


def authorizations(values, today=None):
    today=today or date.today()
    result=[]
    for kind in ('proiectare','executie'):
        prefix=f'autorizatie_{kind}_'
        raw=values.get(prefix+'expirare','')
        expiry=date.fromisoformat(raw) if raw else None
        status=('expirata' if expiry and today>expiry else
                'expira_curand' if expiry and today>=warning_date(expiry) else
                'valabila' if expiry else 'necompletata')
        # An entered expiry still alerts even when the type/number is missing.
        complete=all(values.get(prefix+p) for p in ('tip','numar','expirare'))
        result.append({'kind':kind, 'tip':values.get(prefix+'tip',''),
                       'numar':values.get(prefix+'numar',''), 'expiry':expiry,
                       'status':status,'complete':complete,
                       'days':(expiry-today).days if expiry else None,
                       'warning_from':warning_date(expiry) if expiry else None})
    return result
