# Date client si date lucrare

Identitatea, contactul, actul de identitate, domiciliul/sediul, datele firmei si contul bancar se salveaza in fisa clientului. Formularul contractului afiseaza un rezumat si permite deschiderea aceluiasi editor de client. Nu cere CNP.

Adresa locului de consum apartine fiecarei lucrari. Bifa de copiere a domiciliului/sediului completeaza campurile editabile; salvarea pastreaza o copie independenta. Schimbarile ulterioare la client nu modifica lucrarea. Sunt pastrate si scara, etajul si codul postal.

Pentru clientii vechi, editorul propune spre verificare datele din documentele aceluiasi client. Salvarea confirma fisa drept sursa pentru contractele viitoare, inclusiv campurile lasate intentionat goale. Datele istorice de loc consum din clienti raman in baza, fara a mai fi cerute in formularul clientului sau copiate automat in lucrari noi.

La emitere, serviciul preia identitatea din clientul verificat si adresa din lucrare, chiar daca exista valori diferite intr-o ciorna veche. Ciornele noi pentru clientii verificati pastreaza numai datele contractuale. Documentele si snapshoturile deja emise nu se regenereaza. Modificarile concurente ale clientului sunt respinse prin revizie; se redeschide editorul pentru reincarcare.

Campurile scurte ale contractului si adresele sunt grupate pe coloane; duratele si regulile de calcul existente sunt pastrate. Migrarile SQLite si PostgreSQL sunt aditive si se pot relua.
