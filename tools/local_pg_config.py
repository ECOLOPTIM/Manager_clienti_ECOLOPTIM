"""Local-only configuration. Never print connection strings or passwords."""
import json
import os
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.local-postgres.json'
DB_NAME = 'ecoloptim_pg_test'
ROLE_NAME = 'ecoloptim_pg_test_app'


def validate_test_database(name):
    if (not isinstance(name, str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,58}', name)
            or not name.startswith('ecoloptim_') or not name.endswith('_test')):
        raise ValueError('Numele bazei trebuie sa fie de forma ecoloptim_nume_test.')
    return name


def load_config():
    value = json.loads(CONFIG.read_text(encoding='utf-8'))
    database = validate_test_database(value.get('TEST_DATABASE', DB_NAME))
    url = urlsplit(value['DATABASE_URL'])
    if (url.scheme != 'postgresql' or url.hostname not in ('127.0.0.1', 'localhost', '::1')
            or url.path != '/' + database):
        raise ValueError('Configuratia nu indica baza locala de test.')
    return value


def write_config(value):
    # Never overwrite an existing configuration containing user secrets.
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as file:
        json.dump(value, file, indent=2)
