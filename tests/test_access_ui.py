"""Full-app permission routing and session invalidation using temporary SQLite."""
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from db import db, permissions


class AccessUI(unittest.TestCase):
    def setUp(self):
        permissions.clear_actor()
        self.tmp = tempfile.TemporaryDirectory()
        self.old_path, self.old_url = db.DB_PATH, db.DATABASE_URL
        db.DATABASE_URL = ''
        db.DB_PATH = str(Path(self.tmp.name) / 'access.db')
        db.init_db()
        db.seteaza_must_change_password('admin', 0)
        for name, role, mandatory in [('office', 'birou', 0), ('viewer', 'vizualizare', 0),
                                       ('pending', 'birou', 1)]:
            db.adauga_utilizator(name, 'Initial-password-123', role, must_change_password=mandatory)
        db.adauga_client({'nume': 'Test client', 'email': 'test@example.com'})
        db.adauga_lucrare({'client_id': 1, 'tip_lucrare': 'Instalatie termica noua',
                          'status': 'OFERTAT', 'valoare_contractata': 1000})

    def tearDown(self):
        permissions.clear_actor()
        db.DB_PATH, db.DATABASE_URL = self.old_path, self.old_url
        self.tmp.cleanup()

    def session(self, username, marker=None, cached_role='admin'):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'ECOLOPTIM_clienti.py'), default_timeout=15)
        app.session_state['user'] = username
        app.session_state['role'] = cached_role
        app.session_state['auth_password_marker'] = marker or permissions.password_marker(db.get_utilizator(username))
        app.run()
        self.assertFalse(app.exception)
        return app

    def test_actual_login_binds_password_version_and_live_role(self):
        app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / 'ECOLOPTIM_clienti.py'), default_timeout=15).run()
        next(field for field in app.text_input if field.label == 'Utilizator').set_value('office')
        next(field for field in app.text_input if field.label == 'Parolă').set_value('Initial-password-123')
        next(button for button in app.button if button.label == 'Login').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['user'], 'office')
        self.assertEqual(app.session_state['role'], 'birou')
        self.assertEqual(app.session_state['auth_password_marker'], permissions.password_marker(db.get_utilizator('office')))
        self.assertGreater(len(app.tabs), 0)

    def test_office_never_gets_user_admin_tab_from_cached_admin_role(self):
        app = self.session('office')
        self.assertFalse(any(t.label == '👤 Utilizatori' for t in app.tabs))
        self.assertEqual(app.session_state['role'], 'birou')

    def test_viewer_has_no_business_edit_forms(self):
        app = self.session('viewer')
        self.assertEqual(len(app.tabs), 5)
        self.assertFalse(any(t.label == '👤 Utilizatori' for t in app.tabs))
        self.assertTrue(any('consultare' in x.value for x in app.info))
        # Sidebar account password and logout are the only ordinary buttons.
        self.assertEqual({b.label for b in app.button}, {'Actualizează parola', '⛔ Renunță', 'Reset'})
        self.assertTrue(app.dataframe)

    def test_mandatory_password_stops_all_business_tabs(self):
        app = self.session('pending')
        self.assertEqual(len(app.tabs), 0)
        self.assertTrue(any(x.label == 'Parola curentă' for x in app.text_input))
        for field in app.text_input:
            if field.label == 'Parola curentă': field.set_value('Initial-password-123')
            if field.label in ('Parola nouă', 'Confirmă parola nouă'): field.set_value('Changed-password-123')
        next(b for b in app.button if b.label == 'Actualizează parola').click().run()
        self.assertFalse(app.exception)
        self.assertGreater(len(app.tabs), 0)
        self.assertEqual(db.get_utilizator('pending')['must_change_password'], 0)

    def test_deactivated_existing_session_returns_to_login(self):
        app = self.session('office')
        db.seteaza_activ_utilizator('office', 0)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 0)
        self.assertTrue(any(x.label == 'Utilizator' for x in app.text_input))

    def test_password_reset_invalidates_existing_session(self):
        app = self.session('office')
        db.reseteaza_parola_admin('office', 'Reset-password-123', must_change_password=0)
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.tabs), 0)
        self.assertTrue(any(x.label == 'Utilizator' for x in app.text_input))

    def test_role_change_refreshes_existing_session(self):
        app = self.session('office')
        db.seteaza_rol_utilizator('office', 'vizualizare')
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(app.session_state['role'], 'vizualizare')
        self.assertEqual(len(app.tabs), 5)

    def test_admin_has_user_administration_and_logout_clears_editor_state(self):
        app = self.session('admin')
        self.assertTrue(any(t.label == '👤 Utilizatori' for t in app.tabs))
        app.session_state['lucrari_client_edit_snapshot_1'] = {'id': 1, 'descriere': 'private draft'}
        next(b for b in app.button if b.label == '⛔ Renunță').click().run()
        self.assertFalse(app.exception)
        with self.assertRaises(KeyError):
            app.session_state['lucrari_client_edit_snapshot_1']
        self.assertEqual(len(app.tabs), 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
