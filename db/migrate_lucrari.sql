-- 1. Renumește coloanele vechi dacă ai date existente
ALTER TABLE lucrari RENAME COLUMN data_start TO data_contract;
ALTER TABLE lucrari RENAME COLUMN data_sfarsit TO data_programare;

-- 2. (Opțional/recomandat) Șterge coloanele de oră dacă există
-- Notă: SQLite nu suportă DROP COLUMN înainte de v3.35.
-- Dacă folosești o versiune nouă, poți rula direct:
ALTER TABLE lucrari DROP COLUMN ora_start;
ALTER TABLE lucrari DROP COLUMN ora_sfarsit;

-- Dacă ai o versiune mai veche de SQLite sau vrei să fii 100% safe:
-- Creezi o tabelă temporară cu schema dorită, copiezi datele, ștergi vechea și redenumești noua.
BEGIN TRANSACTION;

CREATE TABLE lucrari_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    tip_lucrare TEXT,
    valoare_contractata REAL,
    responsabil TEXT,
    status TEXT,
    data_contract TEXT,
    data_programare TEXT,
    observatii TEXT,
    descriere TEXT
);

INSERT INTO lucrari_new (id, client_id, tip_lucrare, valoare_contractata, responsabil, status, data_contract, data_programare, observatii, descriere)
SELECT id, client_id, tip_lucrare, valoare_contractata, responsabil, status, data_contract, data_programare, observatii, descriere
FROM lucrari;

DROP TABLE lucrari;
ALTER TABLE lucrari_new RENAME TO lucrari;

COMMIT;