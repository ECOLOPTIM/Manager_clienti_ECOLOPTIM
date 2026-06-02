# Manager clienți / lucrări — ECOLOPTIM

Aplicație Streamlit pentru administrarea:
- clienților
- lucrărilor
- sarcinilor / fluxului de birou
- documentelor generate
- atașamentelor
- facturilor și plăților

## Funcționalități principale
- autentificare utilizatori
- roluri (`admin`, `birou`, `vizualizare`)
- administrare clienți
- administrare lucrări per client
- workflow de sarcini per lucrare
- atașamente pe client / lucrare / sarcină
- financiar per client:
  - facturi
  - plăți
  - sold
- alerte pentru facturi restante
- overview cu KPI
- generare documente DOCX
- generare fișiere Excel din template

## Structură proiect

- `ECOLOPTIM_clienti.py` — fișierul principal al aplicației Streamlit
- `db/db.py` — acces la baza de date SQLite, inițializare și migrare schemă
- `tabs/` — modulele UI ale aplicației
- `assets/` — CSS, logo, resurse UI
- `templates/` — template-uri DOCX/XLSX pentru documente
- `uploads/` — fișiere încărcate de utilizatori

## Cerințe
- Python 3.10+
- pip

## Instalare locală

### 1. Creează și activează mediu virtual

#### Windows
```bash
python -m venv .venv
.venv\Scripts\activate
```

#### Linux / macOS
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2. Instalează dependențele
```bash
pip install -r requirements.txt
```

## Configurare

Aplicația folosește următoarele variabile de mediu:

- `DB_PATH` — calea către baza de date SQLite
- `UPLOAD_DIR` — folderul pentru fișiere încărcate
- `DEFAULT_ADMIN_PASSWORD` — parola inițială pentru utilizatorul `admin` la prima inițializare

Dacă nu sunt setate, valorile implicite sunt:
- `DB_PATH=manager_clienti_modern.db`
- `UPLOAD_DIR=uploads`
- `DEFAULT_ADMIN_PASSWORD=admin`

## Exemplu configurare

### Windows PowerShell
```powershell
$env:DB_PATH="manager_clienti_modern.db"
$env:UPLOAD_DIR="uploads"
$env:DEFAULT_ADMIN_PASSWORD="admin"
```

### Linux / macOS
```bash
export DB_PATH=manager_clienti_modern.db
export UPLOAD_DIR=uploads
export DEFAULT_ADMIN_PASSWORD=admin
```

## Rulare
```bash
streamlit run ECOLOPTIM_clienti.py
```

## Prima rulare
La prima pornire:
- baza de date SQLite este creată automat dacă nu există
- schema este inițializată / migrată automat
- se creează utilizatorul implicit:
  - user: `admin`
  - parolă: valoarea din `DEFAULT_ADMIN_PASSWORD` sau `admin`

## Observații
- atașamentele se salvează în folderul configurat prin `UPLOAD_DIR`
- template-urile DOCX/XLSX trebuie să existe local în proiect
- generarea PDF din DOCX prin Microsoft Word funcționează doar pe Windows, dacă este disponibil `pywin32`
- în medii Linux / cloud, conversia DOCX → PDF prin Word poate să nu funcționeze

## Fișiere importante
- `ECOLOPTIM_clienti.py` — entry point
- `db/db.py` — logică DB
- `requirements.txt` — dependențe Python
- `.env.example` — exemplu de configurare
- `tabs/tab_clienti.py` — management clienți
- `tabs/tab_lucrari_client.py` — management lucrări + documente + flux birou
- `tabs/tab_financiar_client.py` — facturi / plăți / sold