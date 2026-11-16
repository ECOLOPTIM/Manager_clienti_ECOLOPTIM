# Contractul de mandat IUGN

Sablonul privat se instaleaza separat ca `templates/contract_mandat_iugn.docx`. Modelul pastrat de firma este completat cu identificarea PF/PJ, domiciliul/sediul, reprezentantul, datele prestatorului, locul de consum si referinta contractului de prestari servicii. Nu se cere CNP. Numele firmei din corpul documentului provine din Date generale, prin contextul contractului emis.

Pentru contractele noi, aceeasi emitere salveaza contractul si mandatul intr-o singura tranzactie, impreuna cu atasamentele si confirmarea Contract emis. Previzualizarile se descarca separat. Numarul `MDT-2026-0001` este corelat cu `CTR-2026-0001`, fara consumarea unui al doilea numar de contract. Lipsa sau modificarea sablonului impiedica emiterea. O eroare la generarea mandatului anuleaza emiterea ambelor documente si consumarea numarului; fisierele neconfirmate se elimina dupa verificarea rollbackului.

Pentru contractele emise inaintea acestei functionalitati: Documente IUGN / Contract de mandat IUGN / Previzualizeaza mandatul / Emite si salveaza mandatul in dosar. Contractul existent nu se reemite si fluxul sau contorul sau nu se modifica. Mandatul foloseste snapshotul contractului emis, inclusiv cand clientul sau lucrarea au fost editate intre timp. Data mandatului este data emiterii lui; nu se antedateaza.

Fiecare mandat pastreaza contextul, referinta si amprenta contractului, amprenta sablonului, autorul si amprenta fisierului. Se permite un singur mandat emis per lucrare. Drepturile se verifica din nou la salvare. Documentele emise raman nemodificate si se descarca din dosar dupa verificarea amprentei.

Emiterea nu confirma semnatura contractului sau a mandatului si nu confirma depunerea in portal. Incarcarea exemplarelor semnate ramane un pas separat. Documentele necesita backupul UPLOAD_DIR impreuna cu baza de date. Migrarile sunt aditive pentru SQLite si PostgreSQL; testele folosesc un sablon sintetic, fara antetul privat.

Identificarea completa a partilor poate fi asezata direct in sablon, cu ramura
PF/PJ pentru beneficiar. Contextul mandatului include campurile de identitate,
adresele `beneficiar_adresa` si `executant_adresa`, conturile si bancile, precum
si reprezentantii si functiile acestora. Datele provin din contextul inghetat la
emiterea contractului, fara o noua introducere in formular. Campurile agregate
`mandant_identificare` si `mandatar_identificare` raman compatibile cu sabloanele
anterioare. CNP-ul nu este transmis. Sablonul privat se inlocuieste separat;
actualizarea codului prin Git nu instaleaza documentul Word.
