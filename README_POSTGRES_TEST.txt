ECOLOPTIM - VARIANTA POSTGRESQL PENTRU TEST LOCAL

STARE
Codul este pregatit intr-o copie separata. Nu este o versiune pentru productie.
Validare efectuata in mediul de dezvoltare: 38 teste SQLite si 2 teste Streamlit.
Pe calculatorul utilizatorului: 36 teste PostgreSQL trecute pe Windows,
plus fluxul manual, backup/restaurare si probele de permisiuni confirmate.
Detalii actualizate in docs/VALIDARE_2026-10-22.md.
Serverul PostgreSQL nu ruleaza in mediul de dezvoltare al asistentului.
Se pastreaza protectia la editarea aceleiasi lucrari din doua sesiuni.
Nu se importa clientii, lucrarile, parolele sau documentele din baza SQLite.

INSTALARE PE WINDOWS
1. Pastreaza folderele originale si TEST deja validate.
2. Extrage Manager_clienti_ECOLOPTIM_PG_TEST in D:\Aplicatii.
3. Instaleaza PostgreSQL pentru Windows de pe pagina oficiala:
   https://www.postgresql.org/download/windows/
   Alege un pachet stabil Windows x86-64. Pastreaza PostgreSQL Server,
   pgAdmin si Command Line Tools. Stack Builder nu este necesar aici.
   Retine parola de administrator PostgreSQL pe calculatorul tau.
   Portul implicit este 5432; daca este ocupat, retine portul ales.
4. Deschide CMD in noul folder si creeaza un mediu Python separat:
   D:\Aplicatii\Manager_clienti_ECOLOPTIM_TEST\.venv\Scripts\python.exe -m venv .venv
   .venv\Scripts\python.exe -m pip install -r requirements.txt
5. Ruleaza:
   .venv\Scripts\python.exe -m tools.setup_postgres_test
   Introdu local parola PostgreSQL si alege parola adminului aplicatiei noi.
   Parolele nu se afiseaza. Nu este necesar sa le trimiti in conversatie.
   Scriptul creeaza NUMAI ecoloptim_pg_test pe 127.0.0.1, cu un rol propriu.
   Daca baza sau rolul exista deja, se opreste fara sa le inlocuiasca.
   Configuratia privata este .local-postgres.json. Nu o distribui.
6. Ruleaza testele PostgreSQL:
   .venv\Scripts\python.exe -m tests.test_postgres
   Testele folosesc o schema temporara proprie si o sterg la final.
   Datele din schema public a bazei de test nu sunt sterse de aceste teste.
   Lipsa serverului/configuratiei este raportata ca esec, nu ca test trecut.
7. Dupa rezultate OK:
   .venv\Scripts\python.exe -m tools.start_postgres_test
   Deschide http://127.0.0.1:8503
   Utilizator: admin; parola: cea aleasa la pasul 5.
   Aplicatia initiala TEST poate ramane separat pe portul 8502.
8. Repeta fluxul client -> doua lucrari -> factura 1000 -> plati 300 + 700.
   Repeta editarea din doua sesiuni, inclusiv conflictul pe aceeasi lucrare.
   Autentifica doua conturi distincte pentru verificarea rolurilor.

CE ESTE ADAPTAT
- Conectare PostgreSQL explicita prin DATABASE_URL; o eroare PostgreSQL nu
  determina trecerea automata la SQLite.
- Schema noua, versionata; initializarea nu reseteaza datele sau parolele.
- Chei straine pentru legaturile client/lucrare/sarcina/factura/plata.
- Valori financiare NUMERIC(14,2), cu precizie de doi zecimale in baza.
- Numerotare atomica pentru OS, contracte si registrul clientului.
- Plata si recalcularea statusului se salveaza in aceeasi tranzactie,
  cu blocare pe factura in PostgreSQL.
- Verificarea versiunii lucrarii ramane atomica la fiecare salvare.
- Configurarea si pornirea din tools sunt limitate la baza locala de test.

LIMITARI SI PASI RAMASI
- Verificarea modulelor ramase inainte de lansarea pe web.
- Compararea cu sursa versiunii web existente, deja identificata ca diferita.
- Protectia la editari concurente a fost implementata pentru lucrari;
  celelalte formulare necesita verificare separata.
- Datele calendaristice raman TEXT pentru compatibilitate cu formularele
  existente; restructurarea lor nu este inclusa in acest pachet.
- Nicio actualizare a aplicatiei web nu a fost efectuata.

DEPENDENTE SI COMPATIBILITATE
Driver: psycopg[binary]>=3.2,<4. Server recomandat pentru test: PostgreSQL 17 sau 18.
SQLite din copia separata ramane pentru regresii si revenire.
Nu sincroniza fisierele serverului PostgreSQL cu Google Drive.
Documentele lucrarilor pot ramane in Google Drive conform fluxului existent.
