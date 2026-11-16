from datetime import date
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from db import db, permissions, iugn, iugn_step_documents as documents
from tests import test_iugn_step_documents as step_tests
from tests.test_iugn_documents import ContractIssueCases

APP='''
import streamlit as st
from db import db, permissions
from tabs.components.iugn_panel import render
username=st.session_state.get('test_username','admin')
permissions.bind_actor(username,permissions.password_marker(db.get_utilizator(username)))
render(st.session_state['test_lid'],1)
'''

class Uploaded:
    name='Contract_semnat.pdf'
    def getvalue(self):return b'%PDF-signed-ui-test'

class StepDocumentsUI(unittest.TestCase):
    setUp=step_tests.StepDocumentsSQLite.setUp
    tearDown=step_tests.StepDocumentsSQLite.tearDown
    setup_contract=ContractIssueCases.setup_contract
    prepared_step_work=step_tests.StepDocumentCases.prepared_step_work

    def open(self,lid,username='admin'):
        app=AppTest.from_string(APP,default_timeout=20)
        app.session_state['test_lid']=lid;app.session_state['test_username']=username
        app.run();self.assertFalse(app.exception)
        return app

    def test_upload_button_on_contract_row_saves_and_confirms_then_downloads_in_place(self):
        lid=self.prepared_step_work();app=self.open(lid)
        prefix=f'iugn_1_{lid}'
        next(b for b in app.button if b.key==prefix+'_up_contract_semnat').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(next(s for s in app.selectbox if s.label=='Tip document').value,'contract_semnat')
        self.assertTrue(next(c for c in app.checkbox if c.label.startswith('Confirma etapa')).value)
        with patch('streamlit.file_uploader',return_value=[Uploaded()]):
            next(b for b in app.button if b.label=='Salveaza documentele').click().run()
        self.assertFalse(app.exception);self.assertFalse(app.error)
        self.assertIn('contract_semnat',iugn.get(lid)['state']['facts'])
        next(b for b in app.button if b.key==prefix+'_down_contract_semnat').click().run()
        self.assertFalse(app.exception)
        self.assertTrue(any('Contract_semnat.pdf' in x.label for x in app.get('download_button')))
        next(b for b in app.button if b.key==prefix+'_down_contract_emis').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(len(app.get('download_button')),2)
        self.assertTrue(any('Mandat emis' in c.value for c in app.caption))

    def test_mandate_upload_does_not_offer_contract_confirmation(self):
        lid=self.prepared_step_work();app=self.open(lid);prefix=f'iugn_1_{lid}'
        next(b for b in app.button if b.key==prefix+'_up_contract_semnat').click().run()
        next(s for s in app.selectbox if s.label=='Tip document').select('mandat_semnat').run()
        field=next(c for c in app.checkbox if c.label.startswith('Confirma etapa'))
        self.assertFalse(field.value);self.assertTrue(field.disabled)
        with patch('streamlit.file_uploader',return_value=[Uploaded()]):
            next(b for b in app.button if b.label=='Salveaza documentele').click().run()
        self.assertFalse(app.exception);self.assertFalse(app.error)
        self.assertNotIn('contract_semnat',iugn.get(lid)['state']['facts'])
        self.assertTrue(any('Mandat semnat incarcat' in x.value for x in app.caption))

    def test_stale_session_cannot_upload_and_refresh_restores_controls(self):
        lid=self.prepared_step_work();app=self.open(lid);prefix=f'iugn_1_{lid}'
        permissions.clear_actor()
        documents.upload(lid,'contract_semnat','mandat_semnat',[('mandat.pdf',b'test')],
            expected_revision=iugn.get(lid)['revision'],occurred_on=date.today().isoformat())
        app.run()
        self.assertTrue(any('alta sesiune' in x.value for x in app.warning))
        self.assertTrue(next(b for b in app.button if b.key==prefix+'_up_contract_semnat').disabled)
        next(b for b in app.button if b.label=='Reincarca fluxul').click().run()
        self.assertFalse(next(b for b in app.button if b.key==prefix+'_up_contract_semnat').disabled)
