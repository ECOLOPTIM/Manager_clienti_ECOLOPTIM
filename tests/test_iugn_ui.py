"""Independent browser sessions and workflow form integration on temporary data."""
import tempfile
import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest
from db import db, permissions, iugn, iugn_rules as rules

APP = '''
import streamlit as st
from db import db, permissions
from tabs.components.lucrari_client_components import PREFIX, render_flux_birou_panel
permissions.clear_actor()
username = st.session_state.get('test_username', 'admin')
profile = db.get_utilizator(username)
permissions.bind_actor(username, permissions.password_marker(profile))
st.session_state[f'{PREFIX}flow_lucrare_id_1'] = 1
render_flux_birou_panel(username, 1)
'''


class IUGNUI(unittest.TestCase):
    def setUp(self):
        permissions.clear_actor()
        self.tmp = tempfile.TemporaryDirectory()
        self.old = db.DB_PATH, db.DATABASE_URL
        db.DB_PATH, db.DATABASE_URL = str(Path(self.tmp.name)/'ui.db'), ''
        db.init_db()
        db.seteaza_must_change_password('admin', 0)
        db.adauga_client({'nume': 'TEST'})
        db.adauga_lucrare({'client_id': 1, 'tip_lucrare': rules.WORK_TYPE,
                          'adresa_judet': 'Galati', 'adresa_localitate': 'Galati',
                          'adresa_strada': 'Test', 'adresa_numar': '1'})

    def tearDown(self):
        permissions.clear_actor()
        db.DB_PATH, db.DATABASE_URL = self.old
        self.tmp.cleanup()

    def open(self, username='admin'):
        app = AppTest.from_string(APP, default_timeout=10)
        app.session_state['test_username'] = username
        app.run()
        self.assertFalse(app.exception)
        return app

    def save_event(self, app, key=None, note=''):
        if key is not None:
            next(x for x in app.selectbox if x.label == 'Eveniment').select(key).run()
        next(x for x in app.text_area if x.label == 'Observatii / referinta documentului').set_value(note)
        next(b for b in app.button if b.label == 'Inregistreaza evenimentul').click().run()
        self.assertFalse(app.exception)

    def test_parallel_streams_and_next_tasks_visible(self):
        app = self.open()
        self.assertEqual(len(app.metric), 4)
        self.assertEqual(next(x for x in app.selectbox if x.label == 'Eveniment').value, 'oferta_acceptata')
        self.save_event(app, note='Client a acceptat')
        self.assertEqual(next(x for x in app.selectbox if x.label == 'Eveniment').value, 'documente_complete')
        self.assertEqual(iugn.get(1)['revision'], 1)

    def test_two_sessions_warn_and_preserve_first_confirmation(self):
        a, b = self.open(), self.open()
        self.save_event(a, note='A')
        self.save_event(b, note='B')
        self.assertTrue(any('alta sesiune' in x.value for x in b.error))
        self.assertEqual(iugn.get(1)['state']['facts']['oferta_acceptata']['note'], 'A')
        next(x for x in b.button if x.label == 'Reincarca fluxul').click().run()
        self.assertFalse(b.exception)
        self.assertFalse(b.error)
        self.assertEqual(next(x for x in b.selectbox if x.label == 'Eveniment').value, 'documente_complete')

    def test_manager_assigns_accounts_after_contract(self):
        for key in ('oferta_acceptata', 'documente_complete', 'contract_emis', 'contract_semnat'):
            iugn.record_event(1, key, str(__import__('datetime').date.today()),
                              expected_revision=iugn.get(1)['revision'])
        app = self.open()
        for label in rules.ROLES.values():
            next(x for x in app.selectbox if x.label == label).select('admin')
        next(x for x in app.button if x.label == 'Salveaza persoanele desemnate').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(set(iugn.get(1)['state']['roles'].values()), {'admin'})

    def test_contract_emission_is_automatic_and_unlinked_confirmation_can_be_corrected(self):
        for key in ('oferta_acceptata','documente_complete'):
            iugn.record_event(1,key,str(__import__('datetime').date.today()),expected_revision=iugn.get(1)['revision'])
        app=self.open()
        self.assertFalse(any('contract_emis' in field.options for field in app.selectbox if field.label=='Eveniment'))
        permissions.clear_actor()
        iugn.record_event(1,'contract_emis',str(__import__('datetime').date.today()),expected_revision=iugn.get(1)['revision'])
        app=self.open()
        self.assertTrue(any('confirmat manual' in item.value for item in app.warning))
        next(x for x in app.text_input if x.label=='Motivul corectiei').set_value('Confirmare accidentala in test')
        next(x for x in app.button if x.label=='Anuleaza confirmarea manuala Contract emis').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertNotIn('contract_emis',iugn.get(1)['state']['facts'])
        self.assertIn('corectie_contract_emis',set(iugn.history(1)['event_key']))

    def test_details_form_can_edit_text_without_rewriting_roles_or_dates(self):
        code = '''
import streamlit as st
from db import db
from tabs.components.lucrari_client_components import PREFIX, render_edit_lucrare_form
st.session_state[f'{PREFIX}edit_lucrare_id_1'] = 1
render_edit_lucrare_form(1, db.lista_lucrari_client(1))
'''
        app = AppTest.from_string(code, default_timeout=10).run()
        self.assertFalse(app.exception)
        self.assertFalse(any(x.label == 'Responsabil' for x in app.selectbox))
        next(x for x in app.text_area if x.label == 'Descriere lucrare').set_value('Detaliu nou')
        next(x for x in app.button if x.label == 'Salveaza detaliile lucrarii').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(db.get_lucrare(1)['descriere'], 'Detaliu nou')
        self.assertEqual(db.get_lucrare(1)['data_contract'], '')

    def test_copy_home_address_is_persisted_once_and_independent_of_client(self):
        db.modifica_client(1,{'domiciliu_judet':'Galati','domiciliu_localitate':'Tecuci',
                              'domiciliu_strada':'Domiciliu','domiciliu_numar':'25',
                              'domiciliu_scara':'B','domiciliu_etaj':'2','domiciliu_cod_postal':'800001'})
        code = """
import streamlit as st
from db import db
from tabs.components.lucrari_client_components import PREFIX, render_edit_lucrare_form
st.session_state[f'{PREFIX}edit_lucrare_id_1'] = 1
render_edit_lucrare_form(1, db.lista_lucrari_client(1))
"""
        app=AppTest.from_string(code,default_timeout=10).run()
        next(x for x in app.checkbox if x.label.startswith('Adresa lucrarii')).check().run()
        self.assertEqual(next(x for x in app.text_input if x.label=='Strada').value,'Domiciliu')
        next(x for x in app.button if x.label=='Salveaza detaliile lucrarii').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(db.get_lucrare(1)['adresa_scara'],'B')
        self.assertEqual(db.get_lucrare(1)['adresa_strada'],'Domiciliu')
        db.modifica_client(1,{'domiciliu_strada':'Alta strada'})
        self.assertEqual(db.get_lucrare(1)['adresa_strada'],'Domiciliu')

    def test_client_editor_has_no_consumption_address_and_keeps_legacy_values(self):
        db.modifica_client(1,{'telefon':'0700000000','consum_strada':'Istoric'})
        code = """
import streamlit as st
from tabs.components.client_profile import render_editor
render_editor(1)
"""
        app=AppTest.from_string(code,default_timeout=10).run()
        self.assertFalse(app.exception)
        self.assertFalse(any('consum' in x.label.lower() or x.label=='CNP' for x in app.text_input))
        next(x for x in app.text_input if x.label=='Serie CI').set_value('AB')
        next(x for x in app.button if x.label=='Salveaza clientul').click().run()
        self.assertFalse(app.exception);self.assertFalse(app.error)
        row=db.lista_clienti().iloc[0]
        self.assertEqual(row['ci_serie'],'AB')
        self.assertEqual(row['consum_strada'],'Istoric')
        self.assertEqual(row['profile_saved'],1)

    def test_two_client_editors_detect_conflict(self):
        db.modifica_client(1,{'telefon':'0700000000'})
        code="from tabs.components.client_profile import render_editor\nrender_editor(1)"
        a=AppTest.from_string(code).run();b=AppTest.from_string(code).run()
        next(x for x in a.text_input if x.label=='Numar CI').set_value('111111')
        next(x for x in a.button if x.label=='Salveaza clientul').click().run()
        next(x for x in b.text_input if x.label=='Numar CI').set_value('222222')
        next(x for x in b.button if x.label=='Salveaza clientul').click().run()
        self.assertTrue(any('alta sesiune' in x.value for x in b.error))
        self.assertEqual(db.lista_clienti().iloc[0]['ci_numar'],'111111')


if __name__ == '__main__':
    unittest.main(verbosity=2)
