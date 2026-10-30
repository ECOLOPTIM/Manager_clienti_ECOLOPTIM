from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from db import company, db, iugn, iugn_documents as docs, permissions
from utils import iugn_contract as ic
from tests.test_iugn_contract import fixture
from tests.iugn_template_fixture import make_template


class ContractIssueCases:
    def setup_contract(self):
        permissions.clear_actor()
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)
        p=patch.object(ic,'TEMPLATE',make_template(path/'synthetic.docx'));p.start();self.addCleanup(p.stop)
        p=patch.object(db,'UPLOAD_DIR',str(path/'uploads'));p.start();self.addCleanup(p.stop)
        client,work,firm,terms=fixture()
        terms.pop('nr_contract')
        terms['beneficiar_ci_nr']='012345'
        # Use a valid example licence, never an actual company's credentials.
        firm['autorizatie_executie_numar']='TEST-1';firm['autorizatie_proiectare_numar']='TEST-2'
        terms['data_contract']=date.today().isoformat()
        firm.update(autorizatie_proiectare_expirare='2099-12-31',autorizatie_executie_expirare='2099-12-31')
        s=company.get();company.save(firm,expected_revision=s['revision'])
        db.adauga_lucrare({'client_id':1,'tip_lucrare':'Instalatie de utilizare noua',
                          'valoare_contractata':2800,'descriere':'Centrala & aragaz'})
        lid=int(db.lista_lucrari_client(1).iloc[0]['id'])
        for key in ('oferta_acceptata','documente_complete'):
            iugn.record_event(lid,key,date.today().isoformat(),expected_revision=iugn.get(lid)['revision'])
        rev=docs.save_draft(lid,terms,expected_revision=0)
        return lid,docs.open_form(lid),terms

    def test_issue_links_document_and_flow_but_not_signature(self):
        lid,bundle,terms=self.setup_contract()
        before=iugn.get(lid)['revision']
        result=docs.issue(lid,bundle,terms)
        self.assertTrue(result['number'].startswith('CTR-'))
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),1)
        current=iugn.get(lid)
        self.assertEqual(current['revision'],before+1)
        self.assertIn('contract_emis',current['state']['facts'])
        self.assertNotIn('contract_semnat',current['state']['facts'])
        self.assertEqual(Path(docs.open_form(lid)['issued']['path']).read_bytes(),result['data'])
        with self.assertRaisesRegex(ValueError,'deja emis'):docs.issue(lid,bundle,terms)
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),1)

    def test_changed_configuration_rejects_issue_without_consuming_number(self):
        lid,bundle,terms=self.setup_contract()
        s=company.get();company.save(dict(s['values'],executant_email='changed@example.invalid'),expected_revision=s['revision'])
        with self.assertRaisesRegex(ValueError,'Configuratia'):docs.issue(lid,bundle,terms)
        self.assertTrue(db.lista_atasamente(1,lucrare_id=lid).empty)
        self.assertNotIn('contract_emis',iugn.get(lid)['state']['facts'])

    def test_file_failure_rolls_back_counter_and_flow(self):
        lid,bundle,terms=self.setup_contract()
        with db._connect() as conn:
            row=db._execute(conn.cursor(),'SELECT last_ctr FROM contracte_seq WHERE an=?',(date.today().year,)).fetchone()
        before=row[0] if row else 0
        with patch.object(ic,'generate_contract',side_effect=OSError('test write error')):
            with self.assertRaises(OSError):docs.issue(lid,bundle,terms)
        with db._connect() as conn:
            row=db._execute(conn.cursor(),'SELECT last_ctr FROM contracte_seq WHERE an=?',(date.today().year,)).fetchone()
        self.assertEqual(row[0] if row else 0,before)
        self.assertNotIn('contract_emis',iugn.get(lid)['state']['facts'])

    def test_stale_draft_save_preserves_first(self):
        lid,bundle,terms=self.setup_contract()
        docs.save_draft(lid,dict(terms,nr_oferta='FIRST'),expected_revision=bundle['draft_revision'])
        with self.assertRaisesRegex(ValueError,'alta sesiune'):
            docs.save_draft(lid,dict(terms,nr_oferta='SECOND'),expected_revision=bundle['draft_revision'])
        self.assertEqual(docs.open_form(lid)['terms']['nr_oferta'],'FIRST')

    def test_workflow_failure_removes_file_and_rolls_back_attachment(self):
        lid,bundle,terms=self.setup_contract()
        with patch.object(iugn,'record_event_in_transaction',side_effect=ValueError('test failure')):
            with self.assertRaisesRegex(ValueError,'test failure'):docs.issue(lid,bundle,terms)
        self.assertTrue(db.lista_atasamente(1,lucrare_id=lid).empty)
        self.assertFalse(list(Path(db.UPLOAD_DIR).rglob('*.docx')))
        self.assertIsNone(docs.open_form(lid)['issued'])

    def test_expired_authorization_blocks_issue(self):
        lid,bundle,terms=self.setup_contract()
        s=company.get();company.save(dict(s['values'],autorizatie_executie_expirare='2000-01-01'),expected_revision=s['revision'])
        bundle=docs.open_form(lid)
        with self.assertRaisesRegex(ValueError,'valabila'):docs.issue(lid,bundle,terms)


class ContractIssueSQLite(ContractIssueCases,unittest.TestCase):
    def setUp(self):
        permissions.clear_actor();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.old=db.DB_PATH,db.DATABASE_URL
        db.DB_PATH,db.DATABASE_URL=str(Path(self.tmp.name)/'contracts.db'),''
        db.init_db();db.seteaza_must_change_password('admin',0)
        db.adauga_client({'nume':'Client demonstrativ'})

    def tearDown(self):
        permissions.clear_actor();db.DB_PATH,db.DATABASE_URL=self.old
