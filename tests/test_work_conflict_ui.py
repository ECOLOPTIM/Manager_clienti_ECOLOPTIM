"""Two independent Streamlit sessions on disposable data; run separately."""
import tempfile
import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest
from db import db

APP = '''
import streamlit as st
from db import db
from tabs.components.lucrari_client_components import PREFIX, render_edit_lucrare_form
client_id = 1
work_id = st.session_state.get('test_work_id', 1)
if st.button('Open work'):
    st.session_state[f'{PREFIX}edit_lucrare_id_{client_id}'] = work_id
    st.session_state.pop(f'{PREFIX}edit_snapshot_{client_id}', None)
    st.session_state.pop(f'{PREFIX}edit_conflict_{client_id}', None)
render_edit_lucrare_form(client_id, db.lista_lucrari_client(client_id))
'''


class WorkConflictUI(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_url = db.DATABASE_URL
        db.DATABASE_URL = ""
        self.old_path = db.DB_PATH
        db.DB_PATH = str(Path(self.tmp.name) / 'ui.db')
        db.init_db()
        db.adauga_client({'nume': 'TEST'})
        for i in range(2):
            db.adauga_lucrare({'client_id': 1, 'tip_lucrare': 'Instalatie termica noua',
                              'status': 'OFERTAT', 'descriere': 'Original',
                              'adresa_judet': 'Galati', 'adresa_localitate': 'Galati',
                              'adresa_strada': 'Test', 'adresa_numar': str(i + 1)})

    def tearDown(self):
        db.DATABASE_URL = self.old_url
        db.DB_PATH = self.old_path
        self.tmp.cleanup()

    def open_session(self, work_id=1):
        app = AppTest.from_string(APP, default_timeout=10)
        app.session_state['test_work_id'] = work_id
        app.run().button[0].click().run()
        self.assertFalse(app.exception)
        return app

    def save(self, app, text):
        description = next(x for x in app.text_area if x.label == 'Descriere lucrare')
        description.set_value(text)
        next(x for x in app.button if x.label == '💾 Salvează modificările').click().run()
        self.assertFalse(app.exception)

    def test_stale_form_warns_retains_draft_and_reloads_latest_version(self):
        a, b = self.open_session(), self.open_session()
        self.save(a, 'MODIFICARE A')
        self.save(b, 'MODIFICARE B')
        self.assertEqual(db.get_lucrare(1)['descriere'], 'MODIFICARE A')
        self.assertTrue(any('nu au fost salvate' in x.value for x in b.error))
        self.assertEqual(next(x.value for x in b.text_area
                              if x.label == 'Descriere lucrare'), 'MODIFICARE B')
        # A second click cannot bypass the conflict by refreshing its revision.
        self.save(b, 'MODIFICARE B din nou')
        self.assertEqual(db.get_lucrare(1)['descriere'], 'MODIFICARE A')
        next(x for x in b.button if x.label.startswith('Reîncarcă lucrarea')).click().run()
        self.assertFalse(b.exception)
        self.assertFalse(b.error)
        self.assertEqual(next(x.value for x in b.text_area
                              if x.label == 'Descriere lucrare'), 'MODIFICARE A')
        self.save(b, 'MODIFICARE A + B revizuit')
        self.assertEqual(db.get_lucrare(1)['descriere'], 'MODIFICARE A + B revizuit')

    def test_different_work_forms_both_save(self):
        a, b = self.open_session(1), self.open_session(2)
        self.save(a, 'A')
        self.save(b, 'B')
        self.assertEqual(db.get_lucrare(1)['descriere'], 'A')
        self.assertEqual(db.get_lucrare(2)['descriere'], 'B')
        self.assertFalse(a.error)
        self.assertFalse(b.error)


if __name__ == '__main__':
    unittest.main(verbosity=2)
