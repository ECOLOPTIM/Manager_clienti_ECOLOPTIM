# Date generale si expirarea autorizatiilor

Administratorul completeaza firma, sediul social, banca, contactul, autorizatiile ANRE de proiectare si executie si configuratia GDPR in fila Date generale. Rubricile pornesc goale; datele firmei se completeaza direct in aplicatie si se pastreaza in baza de date.

Fiecare autorizatie are tip, numar si data expirarii. Data poate ramane goala in timpul completarii; nu este presupusa o valabilitate. Rubricile incomplete sunt semnalate in Date generale.

La fiecare incarcare sau interactiune cu aplicatia, dupa autentificare si schimbarea parolei obligatorii, se afiseaza:

- avertizare incepand cu data expirarii minus trei luni calendaristice, inclusiv ziua expirarii;
- eroare din ziua urmatoare expirarii;
- nicio avertizare de expirare daca noua data, dupa reinnoire, este in afara intervalului.

Scaderea lunilor ajusteaza ziua la ultima zi din luna tinta: pentru 31 mai, pragul este 28 februarie sau 29 februarie intr-un an bisect. Avertizarile folosesc data locala a serverului aplicatiei si se vad pentru toate rolurile. Nu sunt trimise e-mailuri sau notificari pe telefon.

Configuratia se pastreaza in firma_config din baza activa, cu revizie, utilizator si data. Fiecare salvare este arhivata in firma_config_istoric. Permisiunea admin este verificata la salvare din contul autentificat, iar o salvare cu revizie veche este respinsa. Backupul complet PostgreSQL include aceste tabele. Migrarea este aditiva si idempotenta si nu schimba lucrarile sau starea fluxului.

Datele sunt disponibile pentru generatorul IUGN prin `company.get()['values']`. Formularul de emitere a contractelor si legarea la flux raman pasi separati.
