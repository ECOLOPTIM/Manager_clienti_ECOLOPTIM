from datetime import date
from streamlit.testing.v1 import AppTest
from db import iugn_documents as docs, iugn
from tests import test_iugn_documents as cases
import unittest

APP='''
import streamlit as st
from db import db,permissions
from tabs.components.iugn_contract_dispatch import render_documente_panel
permissions.bind_actor('admin',permissions.password_marker(db.get_utilizator('admin')))
st.session_state['lucrari_client_doc_lucrare_id_1']=st.session_state['test_lid']
render_documente_panel('admin',1,{})
'''


class ContractFormUI(unittest.TestCase):
    setUp=cases.ContractIssueSQLite.setUp
    tearDown=cases.ContractIssueSQLite.tearDown
    setup_contract=cases.ContractIssueCases.setup_contract
    # Reuse persistence setup while adding a complete browser form scenario.
    def test_browser_preview_then_issue_and_reopen(self):
        lid,bundle,terms=self.setup_contract()
        app=AppTest.from_string(APP,default_timeout=15)
        app.session_state['test_lid']=lid
        app.run();self.assertFalse(app.exception)
        next(b for b in app.button if b.label=='Verifica si previzualizeaza').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        next(b for b in app.button if b.label=='Emite si salveaza contractul in dosar').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any('Contract emis:' in b.value for b in app.success))
        self.assertIsNotNone(docs.open_form(lid)['issued'])
        self.assertNotIn('contract_semnat',iugn.get(lid)['state']['facts'])
