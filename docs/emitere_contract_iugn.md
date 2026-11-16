# Emiterea contractului IUGN

Pentru o instalatie de utilizare noua, in Documente pentru lucrare se alege Contract IUGN cu anexe. Formularul preia clientul si adresa lucrarii; campurile lipsa sau specifice contractului se completeaza in ciorna. Modificarile din ciorna nu rescriu fisa clientului sau adresa lucrarii.

Datele firmei, autorizatiile si informarea GDPR se citesc din Date generale. Emiterea necesita ambele autorizatii completate si neexpirate. Ciorna poate fi salvata inainte de completarea tuturor datelor.

Sablonul aprobat se instaleaza separat ca `templates/contract_iugn.docx`. Nu este inclus in aceasta schimbare publica deoarece contine antetul si datele firmei. Testele automate folosesc un document sintetic fara date reale, cu aceleasi variabile. Sablonul real a fost verificat separat prin completare PF/PJ si inspectie vizuala; validarea de test nu certifica respectarea legislatiei.

## Ciorna si previzualizare

Salveaza ciorna contractului pastreaza datele in baza activa, cu revizie, autor si data. O salvare concurenta cu revizie veche este respinsa. Verifica si previzualizeaza salveaza ciorna, verifica datele si calculele si produce un DOCX cu numarul PREVIZUALIZARE. Acest pas nu consuma un numar si nu confirma o etapa in flux.

Preturile detaliate cu TVA trebuie sa insumeze valoarea contractata din lucrare. Avansul convenit este separat de avansul deja incasat. Generatorul calculeaza transele si subtotalurile si nu lasa variabile necompletate. Previzualizarea se descarca pentru verificare; pentru schimbari se solicita o noua previzualizare.

## Emitere

Emite si salveaza contractul in dosar foloseste datele previzualizate. Serviciul reciteste clientul, lucrarea, configuratia firmei, ciorna si fluxul. Datele schimbate sau un sablon modificat impun reincarcarea. Persoana trebuie sa aiba drept de scriere si dreptul comercial prevazut in flux; conditiile etapei Contract emis trebuie indeplinite.

Contorul numarului, documentul din atasamente, inregistrarea de emitere si evenimentul Contract emis sunt confirmate in aceeasi tranzactie. O eroare anuleaza modificarile din baza si elimina fisierul creat in acea incercare. Documentul ramane in UPLOAD_DIR si trebuie inclus in backupul fisierelor externe; backupul exclusiv al bazei nu contine DOCX-ul.

Se pastreaza contextul complet folosit, revizia configuratiei, amprenta sablonului, amprenta documentului, autorul si data. Contractul emis este pastrat nemodificat si poate fi descarcat ulterior. O repetare a emiterii pentru aceeasi lucrare este respinsa, inclusiv din doua sesiuni.

Se confirma numai Contract emis. Contract semnat ramane o etapa separata; incarcarea si verificarea exemplarului semnat si emiterea contractului de mandat nu sunt introduse de aceasta schimbare. Nu exista conversie PDF pe Linux in aceasta livrare. Contractele de bransament existente pastreaza generarea anterioara.
