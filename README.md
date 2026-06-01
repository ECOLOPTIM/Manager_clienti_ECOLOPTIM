# Manager clienți / lucrări

Aplicație Streamlit pentru:
- clienți
- lucrări
- documente generate
- atașamente
- flux birou
- facturi și plăți

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

- `DB_PATH` - calea către baza de date SQLite
- `UPLOAD_DIR` - folderul pentru fișiere încărcate

Dacă nu sunt setate, valorile implicite sunt:
- `DB_PATH=manager_clienti_modern.db`
- `UPLOAD_DIR=uploads`

## Exemplu configurare

### Windows PowerShell
```powershell
$env:DB_PATH="manager_clienti_modern.db"
$env:UPLOAD_DIR="uploads"
```

### Linux / macOS
```bash
export DB_PATH=manager_clienti_modern.db
export UPLOAD_DIR=uploads
```

## Rulare
Înlocuiește `app.py` cu numele real al fișierului principal dacă este diferit.

```bash
streamlit run ECOLOPTIM_clienti.py
```

## Prima rulare
La prima pornire:
- baza de date SQLite este creată automat dacă nu există
- schema este migrată automat
- se creează utilizatorul implicit:
  - user: `admin`
  - parolă: `admin`

## Observații
- atașamentele se salvează în folderul configurat prin `UPLOAD_DIR`
- template-urile DOCX/XLSX trebuie să existe local în proiect
- conversia DOCX -> PDF poate depinde de mediul de rulare și poate să nu funcționeze pe un VPS Linux, dacă implementarea depinde de Microsoft Word

## Fișiere importante
- `db.py` - acces baza de date
- `requirements.txt` - dependențe Python
- `.env.example` - exemplu de configurare
- `tabs/` - tab-urile aplicației