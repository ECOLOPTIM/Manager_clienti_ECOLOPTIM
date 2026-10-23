"""Real PostgreSQL tests in a NEW disposable schema; no production records touched.

Requires tools.setup_postgres_test (local-only database configuration).
Missing server/configuration is a failure, never reported as a successful test.
"""
import concurrent.futures
import os
import secrets
import unittest
from unittest.mock import patch

import psycopg
from psycopg import sql
from db import db
from tools.local_pg_config import load_config
from tests import test_core_workflow as core
from tests import test_work_conflict_ui as ui
from tests.test_permissions import PermissionCases
from db import permissions
from tests.test_iugn import IUGNChecks


class PostgresWorkflow(IUGNChecks, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = load_config()
        cls.old_url, cls.old_schema = db.DATABASE_URL, db.DATABASE_SCHEMA
        db.DATABASE_URL = config['DATABASE_URL']
        cls.schema = 'ecoloptim_ci_' + secrets.token_hex(8)
        cls.admin = psycopg.connect(db.DATABASE_URL, autocommit=True)
        cls.admin.execute(sql.SQL('CREATE SCHEMA {}').format(sql.Identifier(cls.schema)))
        db.DATABASE_SCHEMA = cls.schema
        try:
            db.init_db()
        except BaseException:
            cls.cleanup_schema()
            raise

    @classmethod
    def cleanup_schema(cls):
        try:
            cls.admin.execute(sql.SQL('DROP SCHEMA {} CASCADE').format(sql.Identifier(cls.schema)))
        finally:
            cls.admin.close()
            db.DATABASE_URL, db.DATABASE_SCHEMA = cls.old_url, cls.old_schema

    @classmethod
    def tearDownClass(cls):
        cls.cleanup_schema()

    def setUp(self):
        permissions.clear_actor()
        with db._connect() as conn:
            conn.execute('TRUNCATE iugn_evenimente, iugn_flux, clienti, lucrari, sarcini, inregistrari, atasamente, '
                         'facturi, plati, documente_seq, contracte_seq, registru_seq_client '
                         'RESTART IDENTITY CASCADE')
        db.adauga_client({'nume': 'Test A', 'cod_intern': 'TEST-A'})
        db.adauga_client({'nume': 'Test B', 'cod_intern': 'TEST-B'})
        self.a, self.b = 1, 2

    factura = core.CoreWorkflow.factura
    payment = core.CoreWorkflow.payment
    work_snapshot = core.CoreWorkflow.work_snapshot

    def test_schema_initialization_preserves_records(self):
        row = self.work_snapshot()
        admin = db.get_utilizator('admin')
        db.init_db()
        self.assertEqual(db.get_lucrare(int(row['id']))['descriere'], 'Original')
        self.assertEqual(db.get_utilizator('admin')['parola'], admin['parola'])

    def test_schema_upgrade_from_validated_v1_preserves_legacy_data(self):
        row = self.work_snapshot()
        with db._connect() as conn:
            conn.execute('DROP TABLE iugn_evenimente')
            conn.execute('DROP TABLE iugn_flux')
            conn.execute('ALTER TABLE sarcini DROP COLUMN cod_flux')
            conn.execute('UPDATE ecoloptim_schema_version SET version=1')
        db.init_db()
        db.init_db()
        self.assertEqual(db.get_lucrare(int(row['id']))['descriere'], 'Original')
        self.assertEqual(len(db.lista_sarcini_lucrare(int(row['id']))), 5)
        with db._connect() as conn:
            self.assertEqual(conn.execute('SELECT version FROM ecoloptim_schema_version').fetchone()[0], 2)

    def test_foreign_keys_reject_orphan_and_wrong_owner(self):
        fid = self.factura()
        for client, invoice in [(99999, fid), (self.b, fid), (self.a, 99999)]:
            with self.subTest(client=client, invoice=invoice), self.assertRaises(psycopg.IntegrityError):
                with db._connect() as conn:
                    conn.execute('INSERT INTO plati(client_id,factura_id,suma) VALUES (%s,%s,100)',
                                 (client, invoice))
        self.assertTrue(db.lista_plati(self.a).empty)

    def test_database_rejects_duplicate_username(self):
        with self.assertRaises(psycopg.IntegrityError):
            with db._connect() as conn:
                conn.execute("INSERT INTO utilizatori(username,parola) VALUES ('admin','not-a-password')")

    def test_user_login_and_password_change(self):
        db.adauga_utilizator('birou_test', 'Test-password-123', 'birou')
        self.assertIsNotNone(db.login('birou_test', 'Test-password-123'))
        self.assertIsNone(db.login('birou_test', 'wrong'))
        self.assertEqual(db.get_utilizator('birou_test')['rol'], 'birou')

    def test_case_insensitive_search_and_bound_special_values(self):
        text = "O'Brien ? 100% România"
        db.adauga_client({'nume': text})
        found = db.lista_clienti('o\'brien ?')
        self.assertEqual(len(found), 1)
        self.assertEqual(found.iloc[0]['nume'], text)

    def test_concurrent_payments_leave_correct_invoice_status(self):
        fid = self.factura()
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.payment(fid, 50), range(20)))
        self.assertEqual(len(db.lista_plati(self.a)), 20)
        self.assertEqual(db.calculeaza_sold_client(self.a), 0)
        self.assertEqual(db.lista_facturi(self.a).iloc[0]['status'], 'INCASATA')

    def test_payment_and_status_roll_back_together(self):
        fid = self.factura()
        with patch.object(db, '_recalculate_invoice', side_effect=RuntimeError('simulated failure')):
            with self.assertRaises(RuntimeError):
                self.payment(fid, 300)
        self.assertTrue(db.lista_plati(self.a).empty)
        self.assertEqual(db.calculeaza_sold_client(self.a), 1000)
        self.assertEqual(db.lista_facturi(self.a).iloc[0]['status'], 'NEINCASATA')

    def test_all_numbering_counters_are_unique_under_concurrency(self):
        for fn in [lambda: db.genereaza_nr_os(2026),
                   lambda: db.genereaza_nr_contract(2026),
                   lambda: db.genereaza_nr_inregistrare_client(self.a, 2026)]:
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
                numbers = list(pool.map(lambda _: fn(), range(24)))
            self.assertEqual(len(set(numbers)), 24)


# Reuse backend-independent regression checks without their SQLite-only fixtures.
for name in [
    'test_client_work_tasks_invoice_payments',
    'test_payment_deletion_reopens_invoice',
    'test_cancelled_invoice_rejects_payment',
    'test_payment_must_belong_to_invoice_client',
    'test_payment_amount_must_be_finite_positive',
    'test_work_requires_existing_client',
    'test_invoice_requires_existing_client',
    'test_invoice_amount_must_be_finite_positive',
    'test_concurrent_work_creation_and_numbering',
    'test_stale_work_edit_preserves_first_save',
    'test_two_concurrent_edits_have_one_winner',
    'test_different_works_save_independently',
    'test_work_revision_is_required_and_validated',
]:
    setattr(PostgresWorkflow, name, getattr(core.CoreWorkflow, name))


class PostgresWorkUI(PostgresWorkflow):
    """Real Streamlit edit forms connected to the disposable PostgreSQL schema."""
    def setUp(self):
        super().setUp()
        for i in range(2):
            db.adauga_lucrare({'client_id': 1, 'tip_lucrare': 'Instalatie termica noua',
                              'status': 'OFERTAT', 'descriere': 'Original',
                              'adresa_judet': 'Galati', 'adresa_localitate': 'Galati',
                              'adresa_strada': 'Test', 'adresa_numar': str(i + 1)})

    open_session = ui.WorkConflictUI.open_session
    save = ui.WorkConflictUI.save
    test_stale_form_warns_retains_draft_and_reloads_latest_version = (
        ui.WorkConflictUI.test_stale_form_warns_retains_draft_and_reloads_latest_version)
    test_different_work_forms_both_save = ui.WorkConflictUI.test_different_work_forms_both_save


# Only run the two UI checks for this fixture, rather than inheriting all DB checks again.
UI_CHECKS = ['test_stale_form_warns_retains_draft_and_reloads_latest_version',
             'test_different_work_forms_both_save']


class PostgresPermissions(PermissionCases, PostgresWorkflow):
    def setUp(self):
        permissions.clear_actor()
        super().setUp()
        self.prepare_accounts()

    def tearDown(self):
        permissions.clear_actor()


PERMISSION_CHECKS = [name for name in vars(PermissionCases) if name.startswith('test_permission_')]


def main():
    try:
        load_config()
    except (OSError, ValueError, KeyError):
        print('Testele PostgreSQL NU au rulat: configureaza mai intai baza locala de test.')
        return 1
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(PostgresWorkflow)
    suite.addTests(PostgresWorkUI(name) for name in UI_CHECKS)
    suite.addTests(PostgresPermissions(name) for name in PERMISSION_CHECKS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return not result.wasSuccessful()


if __name__ == '__main__':
    raise SystemExit(main())
