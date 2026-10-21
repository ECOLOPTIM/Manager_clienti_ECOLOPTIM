"""Authorization regressions; SQLite fixture and reusable PostgreSQL cases."""
import concurrent.futures
import secrets
import tempfile
import unittest
from pathlib import Path
from db import db, permissions


class PermissionCases:
    def prepare_accounts(self):
        permissions.clear_actor()
        suffix = secrets.token_hex(4)
        self.office = 'perm_birou_' + suffix
        self.viewer = 'perm_view_' + suffix
        self.second_admin = 'perm_admin_' + suffix
        for name, role in [(self.office, 'birou'), (self.viewer, 'vizualizare'),
                           (self.second_admin, 'admin')]:
            db.adauga_utilizator(name, 'Initial-password-123', role, must_change_password=0)
        self.office_marker = permissions.password_marker(db.get_utilizator(self.office))
        self.viewer_marker = permissions.password_marker(db.get_utilizator(self.viewer))

    def bind(self, name):
        permissions.bind_actor(name, permissions.password_marker(db.get_utilizator(name)))

    def test_permission_viewer_cannot_use_any_business_mutation(self):
        self.bind(self.viewer)
        for name in permissions.BUSINESS_WRITES:
            with self.subTest(function=name), self.assertRaises(PermissionError):
                getattr(db, name)()

    def test_permission_office_cannot_administer_accounts(self):
        self.bind(self.office)
        for name in permissions.ADMIN_OPERATIONS:
            with self.subTest(function=name), self.assertRaises(PermissionError):
                getattr(db, name)()

    def test_permission_office_can_create_business_data(self):
        self.bind(self.office)
        before = len(db.lista_clienti())
        db.adauga_client({'nume': 'Permitted office client'})
        self.assertEqual(len(db.lista_clienti()), before + 1)

    def test_permission_admin_can_administer_accounts(self):
        self.bind(self.second_admin)
        name = 'permitted_' + secrets.token_hex(4)
        db.adauga_utilizator(name, 'New-password-123', 'birou', must_change_password=0)
        self.assertEqual(db.get_utilizator(name)['rol'], 'birou')

    def test_permission_disabled_account_cannot_save_stale_form(self):
        permissions.clear_actor()
        db.seteaza_activ_utilizator(self.office, 0)
        permissions.bind_actor(self.office, self.office_marker)
        with self.assertRaises(PermissionError):
            db.adauga_client({'nume': 'Must not be saved'})

    def test_permission_live_downgrade_to_viewer_blocks_existing_form(self):
        db.seteaza_rol_utilizator(self.office, 'vizualizare')
        permissions.bind_actor(self.office, self.office_marker)
        with self.assertRaises(PermissionError):
            db.adauga_client({'nume': 'Must not be saved'})

    def test_permission_live_admin_downgrade_blocks_admin_operation(self):
        marker = permissions.password_marker(db.get_utilizator(self.second_admin))
        db.seteaza_rol_utilizator(self.second_admin, 'birou')
        permissions.bind_actor(self.second_admin, marker)
        with self.assertRaises(PermissionError):
            db.seteaza_activ_utilizator(self.office, 0)

    def test_permission_password_reset_invalidates_old_session(self):
        db.reseteaza_parola_admin(self.office, 'Reset-password-123', must_change_password=0)
        permissions.bind_actor(self.office, self.office_marker)
        with self.assertRaises(PermissionError):
            db.adauga_client({'nume': 'Must not be saved'})

    def test_permission_mandatory_password_blocks_business_but_allows_own_change(self):
        db.seteaza_must_change_password(self.office, 1)
        self.bind(self.office)
        with self.assertRaises(PermissionError):
            db.adauga_client({'nume': 'Must not be saved'})
        db.schimba_parola(self.office, 'Initial-password-123', 'Changed-password-123')
        self.assertEqual(db.get_utilizator(self.office)['must_change_password'], 0)
        self.assertIsNotNone(db.login(self.office, 'Changed-password-123'))

    def test_permission_own_password_requires_old_password_and_own_identity(self):
        self.bind(self.office)
        with self.assertRaises(ValueError):
            db.schimba_parola(self.office, 'wrong', 'Changed-password-123')
        with self.assertRaises(PermissionError):
            db.schimba_parola(self.viewer, 'Initial-password-123', 'Changed-password-123')

    def test_permission_unknown_roles_and_short_password_are_rejected(self):
        with self.assertRaises(ValueError):
            db.seteaza_rol_utilizator(self.office, 'unknown')
        with self.assertRaises(ValueError):
            db.adauga_utilizator('invalid_' + secrets.token_hex(4), 'Long-password-123', 'unknown')
        with self.assertRaises(ValueError):
            db.reseteaza_parola_admin(self.office, 'short')

    def test_permission_default_admin_remains_available(self):
        with self.assertRaises(ValueError):
            db.seteaza_activ_utilizator('admin', 0)
        with self.assertRaises(ValueError):
            db.seteaza_rol_utilizator('admin', 'birou')

    def test_permission_session_contexts_are_isolated(self):
        def check(name, expected):
            try:
                self.bind(name)
                try:
                    permissions.require('write')
                    result = True
                except PermissionError:
                    result = False
                return result == expected
            finally:
                permissions.clear_actor()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda pair: check(*pair), [(self.office, True), (self.viewer, False)]))
        self.assertTrue(all(results))


class SQLitePermissions(PermissionCases, unittest.TestCase):
    def setUp(self):
        permissions.clear_actor()
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path, self.old_url = db.DB_PATH, db.DATABASE_URL
        db.DATABASE_URL = ''
        db.DB_PATH = str(Path(self.tmp.name) / 'permissions.db')
        db.init_db()
        self.prepare_accounts()

    def tearDown(self):
        permissions.clear_actor()
        db.DB_PATH, db.DATABASE_URL = self.old_path, self.old_url
        self.tmp.cleanup()


if __name__ == '__main__':
    unittest.main(verbosity=2)
