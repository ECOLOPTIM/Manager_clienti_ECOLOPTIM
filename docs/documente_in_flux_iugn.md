# Documente langa fiecare etapa IUGN

Fluxul afiseaza controale compacte langa fiecare etapa: sageata in sus deschide
incarcarea, iar sageata in jos arata numarul documentelor si permite descarcarea.
Contractul si mandatul emise apar la Contract emis. Exemplarele semnate se
incarca separat, alegand tipul potrivit la Contract semnat; mandatul are propria
confirmare vizuala si nu poate tine loc de contract semnat.

Documentele sunt legate de lucrare, etapa si tip. Se pot incarca mai multe
fisiere, cu data, numar/referinta si observatii. Originalele emise raman intacte.
Se pot pastra documente si inainte ca etapa sa devina disponibila, dar fluxul
nu sare peste conditiile existente. Semnaturile se incarca dupa emiterea
originalului corespunzator.

Formularul arata explicit daca salvarea confirma si etapa. Pentru documentele
care atesta etapa, confirmarea este preselectata cand toate tipurile necesare
sunt prezente; pentru transmitere, incasare, programare, predare si executie,
operatorul confirma separat actiunea in acelasi formular. Incarcarea unei note
de plata nu inregistreaza o incasare si nu creeaza o plata contabila.

Proiectul avizat necesita si izometria pentru confirmare. Arhivarea finala PIF
necesita copia PV si ordinul completat. Documentele clientului si dosarul PIF
necesita verificarea operatorului pentru completitudine si aplicabilitate.
O incarcare nu verifica automat autenticitatea sau semnaturile fisierului.

Salvarea documentelor, atasamentelor si confirmarea etapei sunt in aceeasi
tranzactie. Fiecare salvare are autor, data, amprenta si istoric; versiunile
vechi se pastreaza. Doua sesiuni nu pot salva pe aceeasi versiune de flux.
Documentele din flux nu se sterg prin pagina generala de atasamente.

Migrarea este aditiva, la pornirea aplicatiei, pentru SQLite si PostgreSQL.
Etapele deja confirmate si documentele emise anterior sunt pastrate.
Backupul PostgreSQL acopera metadatele; fisierele din UPLOAD_DIR trebuie
incluse in continuare in backupul documentelor externe.
