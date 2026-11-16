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
    new_contract_work=cases.ContractIssueCases.new_contract_work
    old_contract_without_mandate=cases.ContractIssueCases.old_contract_without_mandate
    # Reuse persistence setup while adding a complete browser form scenario.
    def test_single_deviz_offer_fields_preview_and_issue(self):
        lid,bundle,terms=self.setup_contract()
        terms.update(nr_oferta='DO-17',data_oferta='2026-11-16',nr_deviz='',data_deviz='')
        docs.save_draft(lid,terms,expected_revision=bundle['draft_revision'])
        app=AppTest.from_string(APP,default_timeout=15)
        app.session_state['test_lid']=lid
        app.run()
        self.assertFalse(app.exception)
        self.assertEqual(sum(x.label=='Numar deviz-oferta' for x in app.text_input),1)
        self.assertEqual(sum(x.label=='Data devizului-oferta' for x in app.date_input),1)
        self.assertFalse(any('deviz separat' in x.label for x in app.checkbox))
        next(b for b in app.button if b.label=='Verifica si previzualizeaza').click().run()
        self.assertFalse(app.error)
        saved=docs.open_form(lid)['terms']
        self.assertEqual(saved['nr_deviz'],saved['nr_oferta'])
        self.assertEqual(saved['data_deviz'],saved['data_oferta'])
        next(b for b in app.button if b.label=='Emite si salveaza contractul in dosar').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertIsNotNone(docs.open_form(lid)['issued'])

    def test_stage_durations_are_saved_and_impossible_total_blocks_preview(self):
        lid,bundle,terms=self.setup_contract()
        app=AppTest.from_string(APP,default_timeout=15);app.session_state['test_lid']=lid
        app.run()
        next(x for x in app.number_input if x.label=='Proiectare - zile lucratoare').set_value(7)
        next(b for b in app.button if b.label=='Verifica si previzualizeaza').click().run()
        self.assertFalse(app.exception);self.assertFalse(app.error)
        self.assertEqual(docs.open_form(lid)['terms']['durata_proiectare_zile'],7)
        next(x for x in app.number_input if x.label=='Durata contractului in zile calendaristice').set_value(1)
        next(b for b in app.button if b.label=='Verifica si previzualizeaza').click().run()
        self.assertTrue(app.error)
        self.assertFalse(any(b.label=='Emite si salveaza contractul in dosar' for b in app.button))

    def test_new_work_form_prefills_prior_beneficiary_without_copying_price(self):
        lid,bundle,terms=self.setup_contract()
        docs.issue(lid,bundle,terms)
        new_lid=self.new_contract_work()
        app=AppTest.from_string(APP,default_timeout=15);app.session_state['test_lid']=new_lid
        app.run()
        self.assertFalse(app.exception)
        self.assertFalse(any(x.label in ('Numar CI','Nume beneficiar / reprezentant','Serie CI') for x in app.text_input))
        self.assertTrue(any(b.label=='Editeaza clientul' for b in app.button))
        self.assertEqual(next(x for x in app.text_input if x.label=='Numar deviz-oferta').value,'')
        self.assertEqual(next(x for x in app.number_input if x.label=='Proiectare cu TVA').value,0)
        self.assertTrue(any('Client demonstrativ' in x.value for x in app.markdown))

    def test_existing_contract_mandate_can_be_previewed_and_saved_from_documents(self):
        from db import iugn_mandates
        lid=self.old_contract_without_mandate()
        app=AppTest.from_string(APP,default_timeout=15);app.session_state['test_lid']=lid
        app.run();self.assertFalse(app.exception)
        next(x for x in app.selectbox if x.label=='Documente IUGN').select('Contract de mandat IUGN').run()
        next(x for x in app.button if x.label=='Previzualizeaza mandatul').click().run()
        self.assertFalse(app.exception);self.assertFalse(app.error)
        next(x for x in app.button if x.label=='Emite si salveaza mandatul in dosar').click().run()
        self.assertFalse(app.exception);self.assertFalse(app.error)
        self.assertTrue(any('Mandat emis:' in x.value for x in app.success))
        self.assertIsNotNone(iugn_mandates.get(lid))

    def test_browser_preview_then_issue_and_reopen(self):
        lid,bundle,terms=self.setup_contract()
        app=AppTest.from_string(APP,default_timeout=15)
        app.session_state['test_lid']=lid
        app.run();self.assertFalse(app.exception)
        self.assertFalse(any('CNP' in x.label for x in app.text_input))
        next(b for b in app.button if b.label=='Verifica si previzualizeaza').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        next(b for b in app.button if b.label=='Emite si salveaza contractul in dosar').click().run()
        self.assertFalse(app.exception)
        self.assertFalse(app.error)
        self.assertTrue(any('Contract emis:' in b.value for b in app.success))
        self.assertIsNotNone(docs.open_form(lid)['issued'])
        self.assertNotIn('contract_semnat',iugn.get(lid)['state']['facts'])
