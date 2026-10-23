# IUGN 01 - prima etapa de dezvoltare

Baza: versiunea validata `494bce2`, fara modificarea productiei.
Referinta functionala: ECOLOPTIM IUGN 01, versiunea 2.0, 23.10.2026.

## Comportament

La o lucrare noua de tip **Instalatie de utilizare noua**, Flux birou deschide
patru situatii independente: dosar, proiect, executie si PIF. Cele 23 de sarcini
specifice se actualizeaza prin evenimente, cu verificarea conditiilor in baza de
date. Nu exista blocarea globala pe un singur lant de cinci sarcini.

Contractul semnat sau exceptia aprobata permite desemnarea responsabilului,
proiectantului si persoanei comerciale. Cererea de racordare necesita toate
rolurile, contractul si avansul confirmat sau exceptiile aprobate.
Proiectarea si programarea executiei pot avansa in paralel dupa notificare.
Responsabilul desemnat consemneaza decizia de executie cu proiectul nefinalizat;
proiectul ramane restant. Solicitarea PIF necesita proiectul avizat.

Gelu stabileste programarea si echipele. Reprogramarea necesita motiv si pastreaza
istoricul; ordinul executiei sau pregatirile PIF se redeschid pentru noua data.
La reprogramarea PIF se urmareste din nou nota de plata, conform regulii convenite.
PIF efectuata si arhivarea copiei PV sunt evenimente distincte. Statusul general
FINALIZAT consemneaza PIF efectuata; nu inseamna dosar INCHIS.

Fiecare eveniment are data efectiva, momentul inregistrarii, autorul autentificat,
observatii si versiunea fluxului. Salvarea starii, istoricului, sarcinilor si a
campurilor comune ale lucrarii este tranzactionala. Un formular vechi nu poate
suprascrie o confirmare salvata intre timp in alta sesiune.

## Grupuri de flux

Catalogul separa familiile **executie fara proiectare**, **proiectare si executie**
si **doar proiectare**. Tipurile de lucrari raman distincte pentru evidenta si
ofertare. Mai multe tipuri pot utiliza un flux comun. Numai IUGN are acum un
sablon activat; celelalte incadrari si particularitati se stabilesc cu utilizatorul,
fara a presupune ca o anumita instalatie nu necesita proiectare.

## Drepturi

Rolurile sunt legate de conturi active de lucru, nu de lista de nume libera.
Desemnarea persoanelor, exceptiile de contract/avans, programarea executiei si
alocarea echipei PIF sunt rezervate contului de coordonare.
Configuratia `IUGN_MANAGER_USERNAME` indica acel cont; implicit este `admin`.
Acesta trebuie sa aiba rolul admin. Un alt administrator nu primeste automat
dreptul de a aproba in locul lui Gelu. Decizia de executie cu proiectul nefinalizat
apartine exclusiv responsabilului desemnat in sesiunile aplicatiei.

Sarcinile gestionate de flux nu pot fi finalizate din API-ul generic al sarcinilor.
Formularul de editare generala pastreaza pentru aceste lucrari numai adresa,
descrierea si observatiile. Datele si rolurile operationale se modifica prin flux.

## Date existente si migrare

Migrarea este aditiva: coloana `sarcini.cod_flux`, tabelele `iugn_flux` si
`iugn_evenimente`, index unic pentru sarcinile specifice. PostgreSQL trece de la
versiunea 1 la 2 intr-o tranzactie, sub blocarea de initializare deja existenta.
Reinitializarea nu reseteaza datele sau parolele.

Lucrarile IUGN existente se activeaza explicit. Sarcinile vechi nu sunt sterse sau
interpretate automat ca etape noi finalizate; raman vizibile separat. Confirmarile
se fac pe baza dosarului real. Celelalte tipuri pastreaza fluxul anterior.

Inainte de testarea pe o copie existenta: backup baza + documente + cod/configuratie.
Nu rula aceasta ramura peste aplicatia publica. O revenire dupa migrare necesita
restaurarea copiei bazei impreuna cu versiunea veche de cod; codul vechi accepta
numai schema PostgreSQL 1.

## Limita acestei etape

Evenimentele consemneaza declaratiile operatorului. Confirmarea avansului nu
inregistreaza automat o plata si nu genereaza o factura. Confirmarile documentelor
nu verifica inca existenta scanarii sau semnaturii.

Urmatoarele etape adauga dosarul documentar cu versiuni, generarea ordinelor si
celorlalte documente, termenele in zile lucratoare, alertele, transele, regularizarea,
anularea si verificarea inchiderii. Tratarea detaliata a documentelor lipsa,
corecturilor proiectului si PIF nereusite urmeaza impreuna cu dosarul documentar.

## Verificare

Rulari locale: `python -m tests.test_core_workflow` si
`python -m unittest tests.test_iugn tests.test_iugn_ui tests.test_permissions
tests.test_access_ui tests.test_work_conflict_ui tests.test_lucrari_report_ui
tests.test_backup_restore_helpers`.

Suita `python -m tests.test_postgres` include aceleasi reguli IUGN, concurenta,
rollback tranzactional si migrarea unei scheme v1 populate. Ruleaza numai in schema
temporara generata de teste, intr-o baza locala dedicata.
Workflow-ul GitHub Actions porneste un PostgreSQL 16 temporar; nu foloseste serverul
Hetzner sau date din productie. Validarea privata manuala si aprobarea publicarii
raman obligatorii inaintea unei lansari.
