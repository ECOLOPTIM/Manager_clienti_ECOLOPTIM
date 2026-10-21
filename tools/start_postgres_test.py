"""Launch only the dedicated local PostgreSQL test application."""
import os
import subprocess
import sys
from tools.local_pg_config import ROOT, load_config


def main():
    try:
        config = load_config()
    except (OSError, ValueError, KeyError):
        print('Lipseste configuratia locala valida. Ruleaza mai intai tools.setup_postgres_test.')
        return 1
    env = dict(os.environ, **config)
    env["DATABASE_SCHEMA"] = "public"
    print('Pornesc varianta PostgreSQL de test: http://127.0.0.1:8503')
    return subprocess.call([sys.executable, '-m', 'streamlit', 'run', 'ECOLOPTIM_clienti.py',
                            '--server.address', '127.0.0.1', '--server.port', '8503'],
                           cwd=ROOT, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
