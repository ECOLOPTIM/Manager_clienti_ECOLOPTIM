"""Core workflow checks on disposable SQLite databases; never touch live data."""
import concurrent.futures
import importlib
import math
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from db import db


class CoreWorkflow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_url = db.DATABASE_URL
        db.DATABASE_URL = ""
        self.old_path = db.DB_PATH
        db.DB_PATH = str(Path(self.tmp.name) / 'test.db')
        db.init_db()
        db.adauga_client({'nume': 'Test A', 'cod_intern': 'TEST-A'})
        db.adauga_client({'nume': 'Test B', 'cod_intern': 'TEST-B'})
        self.a, self.b = 1, 2

    def tearDown(self):
        db.DATABASE_URL = self.old_url
        db.DB_PATH = self.old_path
        self.tmp.cleanup()

    def factura(self):
        db.adauga_factura({'client_id': self.a, 'numar': 'TEST-1', 'total': 1000})
        return int(db.lista_facturi(self.a).iloc[0]['id'])

    def payment(self, fid, amount, client=None):
        return db.adauga_plata({'client_id': client or self.a, 'factura_id': fid,
                               'suma': amount, 'data_platii': '2026-10-21'})

    def test_client_work_tasks_invoice_payments(self):
        db.adauga_lucrare({'client_id': self.a, 'tip_lucrare': 'IU gaze',
                          'status': 'CONTRACTAT', 'valoare_contractata': 1000,
                          'responsabil': 'Birou test'})
        work = db.lista_lucrari_client(self.a).iloc[0]
        tasks = db.lista_sarcini_lucrare(int(work['id']))
        self.assertEqual(len(tasks), 5)
        db.update_sarcina(int(tasks.iloc[0]['id']), status='IN_LUCRU',
                          responsabil='Birou test', data_scadenta='2026-10-22')
        fid = self.factura()
        self.payment(fid, 250)
        self.assertEqual(db.calculeaza_sold_client(self.a), 750)
        self.assertEqual(db.lista_facturi(self.a).iloc[0]['status'], 'PARTIAL')
        self.payment(fid, 750)
        self.assertEqual(db.calculeaza_sold_client(self.a), 0)
        self.assertEqual(db.lista_facturi(self.a).iloc[0]['status'], 'INCASATA')
        aggregate = db.agregate_financiare_clienti().set_index('client_id').loc[self.a]
        self.assertEqual(aggregate['valoare_contract'], 1000)
        self.assertEqual(aggregate['platit'], 1000)
        self.assertEqual(aggregate['sold'], 0)
        with self.assertRaises(ValueError):
            db.sterge_client(self.a)

    def test_payment_deletion_reopens_invoice(self):
        fid = self.factura()
        self.payment(fid, 1000)
        db.sterge_plata(int(db.lista_plati(self.a).iloc[0]['id']))
        self.assertEqual(db.calculeaza_sold_client(self.a), 1000)
        self.assertEqual(db.lista_facturi(self.a).iloc[0]['status'], 'NEINCASATA')

    def test_cancelled_invoice_rejects_payment(self):
        fid = self.factura()
        db.anuleaza_factura(fid)
        with self.assertRaises(ValueError):
            self.payment(fid, 100)

    def test_payment_must_belong_to_invoice_client(self):
        fid = self.factura()
        with self.assertRaises(ValueError):
            self.payment(fid, 100, self.b)
        self.assertEqual(len(db.lista_plati(self.b)), 0)

    def test_payment_amount_must_be_finite_positive(self):
        fid = self.factura()
        for amount in [0, -1, math.inf, -math.inf, math.nan]:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.payment(fid, amount)
        self.assertEqual(len(db.lista_plati(self.a)), 0)

    def test_work_requires_existing_client(self):
        with self.assertRaises(ValueError):
            db.adauga_lucrare({'client_id': 99999, 'tip_lucrare': 'IU gaze'})
        self.assertTrue(db.lista_lucrari().empty)

    def test_invoice_requires_existing_client(self):
        with self.assertRaises(ValueError):
            db.adauga_factura({'client_id': 99999, 'total': 1000})

    def test_invoice_amount_must_be_finite_positive(self):
        for amount in [0, -1, math.inf, -math.inf, math.nan, None, 'invalid']:
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                db.adauga_factura({'client_id': self.a, 'total': amount})
        self.assertTrue(db.lista_facturi(self.a).empty)

    def test_sqlite_backup_and_restore(self):
        self.factura()
        backup = str(Path(self.tmp.name) / 'backup.db')
        with closing(sqlite3.connect(db.DB_PATH)) as src, closing(sqlite3.connect(backup)) as dst:
            src.backup(dst)
        with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
            conn.execute('DELETE FROM facturi')
        with closing(sqlite3.connect(backup)) as src, closing(sqlite3.connect(db.DB_PATH)) as dst:
            src.backup(dst)
        self.assertEqual(db.calculeaza_sold_client(self.a), 1000)
        with closing(sqlite3.connect(db.DB_PATH)) as conn:
            self.assertEqual(conn.execute('PRAGMA integrity_check').fetchone()[0], 'ok')

    def test_read_write_and_exception_release_connections(self):
        connections = []
        real_connect = sqlite3.connect

        def tracked_connect(*args, **kwargs):
            connection = real_connect(*args, **kwargs)
            connections.append(connection)
            return connection

        with patch.object(db.sqlite3, 'connect', side_effect=tracked_connect):
            db.adauga_client({'nume': 'Lifecycle test'})
            self.assertEqual(len(db.lista_clienti()), 3)
            with self.assertRaises(ValueError):
                db.adauga_lucrare({'client_id': 99999})
        self.assertEqual(len(connections), 3)
        for connection in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                connection.execute('SELECT 1')

    def work_snapshot(self):
        db.adauga_lucrare({'client_id': self.a, 'tip_lucrare': 'IU gaze',
                          'descriere': 'Original', 'status': 'OFERTAT',
                          'adresa_judet': 'Galati', 'adresa_localitate': 'Galati',
                          'adresa_strada': 'Test', 'adresa_numar': '1'})
        return db.lista_lucrari_client(self.a).iloc[0].to_dict()

    def test_stale_work_edit_preserves_first_save(self):
        original = self.work_snapshot()
        lid = int(original['id'])
        a, b = dict(original), dict(original)
        a['descriere'], b['descriere'] = 'MODIFICARE A', 'MODIFICARE B'
        self.assertEqual(db.modifica_lucrare(lid, a, expected_revision=0), 1)
        with self.assertRaises(db.ConcurrentWorkEditError):
            db.modifica_lucrare(lid, b, expected_revision=0)
        self.assertEqual(db.get_lucrare(lid)['descriere'], 'MODIFICARE A')
        fresh = db.get_lucrare(lid)
        fresh['descriere'] += ' + B revizuit'
        db.modifica_lucrare(lid, fresh, expected_revision=fresh['revision'])
        self.assertEqual(db.get_lucrare(lid)['revision'], 2)

    def test_two_concurrent_edits_have_one_winner(self):
        import threading
        original = self.work_snapshot()
        barrier = threading.Barrier(2)
        def save(text):
            values = dict(original, descriere=text)
            barrier.wait(timeout=10)
            try:
                db.modifica_lucrare(int(original['id']), values, expected_revision=0)
                return 'saved', text
            except db.ConcurrentWorkEditError:
                return 'conflict', text
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(save, ['A', 'B']))
        self.assertEqual(sorted(r[0] for r in results), ['conflict', 'saved'])
        winner = next(text for status, text in results if status == 'saved')
        self.assertEqual(db.get_lucrare(int(original['id']))['descriere'], winner)

    def test_different_works_save_independently(self):
        a, b = self.work_snapshot(), self.work_snapshot()
        for row, text in [(a, 'A'), (b, 'B')]:
            db.modifica_lucrare(int(row['id']), dict(row, descriere=text),
                               expected_revision=int(row['revision']))
        self.assertEqual(db.get_lucrare(int(a['id']))['descriere'], 'A')
        self.assertEqual(db.get_lucrare(int(b['id']))['descriere'], 'B')

    def test_deleted_work_is_reported_as_conflict(self):
        row = self.work_snapshot()
        lid = int(row['id'])
        with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
            conn.execute('DELETE FROM lucrari WHERE id=?', (lid,))
        with self.assertRaises(db.ConcurrentWorkEditError):
            db.modifica_lucrare(lid, row, expected_revision=0)

    def test_revision_migration_keeps_existing_work_and_is_idempotent(self):
        row = self.work_snapshot()
        lid = int(row['id'])
        with closing(sqlite3.connect(db.DB_PATH)) as conn, conn:
            conn.execute('ALTER TABLE lucrari DROP COLUMN revision')
        db.init_db()
        self.assertEqual(db.get_lucrare(lid)['descriere'], 'Original')
        self.assertEqual(db.get_lucrare(lid)['revision'], 0)
        db.modifica_lucrare(lid, row, expected_revision=0)
        db.init_db()
        self.assertEqual(db.get_lucrare(lid)['revision'], 1)

    def test_work_revision_is_required_and_validated(self):
        row = self.work_snapshot()
        lid = int(row['id'])
        with self.assertRaises(TypeError):
            db.modifica_lucrare(lid, row)
        for revision in [None, -1, True, '0']:
            with self.subTest(revision=revision), self.assertRaises(ValueError):
                db.modifica_lucrare(lid, row, expected_revision=revision)
        self.assertEqual(db.get_lucrare(lid)['revision'], 0)

    def test_concurrent_work_creation_and_numbering(self):
        def add(i):
            db.adauga_lucrare({'client_id': self.a, 'tip_lucrare': 'IU gaze',
                              'descriere': f'Test concurent {i}'})
            return db.genereaza_nr_contract(2026)
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(add, range(24)))
        self.assertEqual(len(set(numbers)), 24)
        self.assertEqual(len(db.lista_lucrari_client(self.a)), 24)
        # Use the same configured backend/schema as the concurrent writes.
        with closing(db._connect()) as conn, conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM sarcini').fetchone()[0], 120)


if __name__ == '__main__':
    # Run the original 21 plain-function checks without requiring pytest.
    reporting = importlib.import_module('tests.test_utils_reporting')
    suite = unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in
                               vars(reporting).items() if name.startswith('test_') and callable(fn))
    suite.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(CoreWorkflow))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
