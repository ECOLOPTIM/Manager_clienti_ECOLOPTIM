"""Local-only configuration. Never print connection strings or passwords."""
import json
import os
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.local-postgres.json'
DB_NAME = 'ecoloptim_pg_test'
ROLE_NAME = 'ecoloptim_pg_test_app'


def load_config():
    value = json.loads(CONFIG.read_text(encoding='utf-8'))
    url = urlsplit(value['DATABASE_URL'])
    if (url.scheme != 'postgresql' or url.hostname not in ('127.0.0.1', 'localhost', '::1')
            or url.path != '/' + DB_NAME):
        raise ValueError('Configuratia nu indica baza locala de test.')
    return value


def write_config(value):
    # Never overwrite an existing configuration containing user secrets.
    fd = os.open(CONFIG, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as file:
        json.dump(value, file, indent=2)
