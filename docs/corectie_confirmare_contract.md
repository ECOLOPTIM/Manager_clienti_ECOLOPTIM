# Confirmarea emiterii contractului IUGN

Contract emis nu se mai selecteaza din lista de evenimente manuale. In sesiunea autentificata, serverul verifica inregistrarea contractului in dosar inainte de a confirma etapa. Generarea din Documente ramane calea pentru emitere; ea salveaza documentul si evenimentul in aceeasi tranzactie.

Pentru o confirmare manuala anterioara fara document emis de aplicatie, contul de coordonare are butonul Anuleaza confirmarea manuala Contract emis. Motivul este obligatoriu. Corectia este admisa numai daca nu exista contract inregistrat, etape ulterioare, exceptii sau persoane deja desemnate. Orice conflict de revizie este respins.

Corectia elimina confirmarea doar din starea curenta, reseteaza statusul lucrarii la OFERTAT si data de emitere, resincronizeaza sarcinile si consemneaza separat in istoric motivul, confirmarea initiala si valorile anterioare ale statusului/datei. Istoricul initial nu este sters. Clientul, pretul, ciorna si documentele nu se sterg. Un contract emis de aplicatie nu poate fi anulat prin aceasta operatie.

Conventia existenta pentru mentenanta locala de incredere, fara actor de sesiune, permite in continuare reluarea confirmarilor istorice. Aceste operatii nu sunt expuse in formularele aplicatiei.

Verificari automate: respingerea confirmarii fara document in sesiune, emiterea autentificata, corectia auditata, blocarea corectiei dupa etape ulterioare sau pentru contractul efectiv emis si traseul complet de corectie in interfata. Aceleasi verificari de persistenta sunt rulate si pe PostgreSQL.
