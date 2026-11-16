from contextlib import closing
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
    def test_preview_marks_missing_settings_but_final_issue_still_requires_them(self):
        lid,bundle,terms=self.setup_contract()
        settings=company.get()
        values=dict(settings['values'])
        for name in values:
            if name.startswith('gdpr_'):values[name]=''
        company.save(values,expected_revision=settings['revision'])
        terms=dict(terms,nr_deviz='',data_deviz='',defalcare_avize='',descriere_lucrare='',documente_detectoare_beneficiar='')
        bundle=docs.open_form(lid)
        data=docs.preview(bundle,terms)
        from docx import Document
        from io import BytesIO
        text='\n'.join(p.text for p in Document(BytesIO(data)).paragraphs)
        self.assertIn('NECONFIGURAT - numai pentru previzualizare',text)
        self.assertIn('PREVIZUALIZARE',text)
        self.assertNotIn('NECOMPLETAT',text)
        self.assertIn(terms['nr_oferta'],text)
        self.assertEqual(company.get()['values']['gdpr_pastrare_acte'],'')
        self.assertEqual(terms['nr_deviz'],'')
        self.assertIsNone(docs.open_form(lid)['issued'])
        with self.assertRaises(ValueError):docs.issue(lid,bundle,terms)

    def test_offer_is_used_for_preview_and_final_issue_without_separate_estimate(self):
        lid,bundle,terms=self.setup_contract()
        terms=dict(terms,nr_oferta='OF-42',data_oferta='2026-10-29',nr_deviz='',data_deviz='')
        docs.save_draft(lid,terms,expected_revision=bundle['draft_revision'])
        bundle=docs.open_form(lid)
        self.assertEqual(bundle['terms']['nr_deviz'],'OF-42')
        docs.preview(bundle,terms)
        docs.issue(lid,bundle,terms)
        import json
        snapshot=json.loads(docs.open_form(lid)['issued']['snapshot'])
        self.assertEqual(snapshot['context']['nr_deviz'],'OF-42')
        self.assertEqual(snapshot['context']['data_deviz'],'29.10.2026')
        self.assertIn('contract_emis',iugn.get(lid)['state']['facts'])

    def test_impossible_durations_do_not_issue_or_advance_workflow(self):
        lid,bundle,terms=self.setup_contract()
        terms=dict(terms,durata_contract_zile=1,**ic.deadlines.STAGE_DEFAULTS)
        before=iugn.get(lid)
        with self.assertRaisesRegex(ValueError,'nu se incadreaza'):docs.issue(lid,bundle,terms)
        self.assertIsNone(docs.open_form(lid)['issued'])
        self.assertEqual(iugn.get(lid),before)
        self.assertTrue(db.lista_atasamente(1,lucrare_id=lid).empty)

    def new_contract_work(self,client_id=1):
        db.adauga_lucrare({'client_id':client_id,'tip_lucrare':'Instalatie de utilizare noua',
                          'valoare_contractata':3100,'descriere':'Lucrare noua'})
        return int(db.lista_lucrari_client(client_id)['id'].max())

    def test_new_work_reuses_identity_from_issued_contract_without_other_work_data(self):
        lid,bundle,terms=self.setup_contract()
        docs.issue(lid,bundle,terms)
        with closing(db._connect()) as conn,conn:
            db._execute(conn.cursor(),'UPDATE clienti SET ci_numar=? WHERE id=1',('012345',))
        new_lid=self.new_contract_work()
        new=docs.open_form(new_lid)
        values=new['beneficiary_defaults']
        self.assertEqual(values['beneficiar_ci_nr'],'012345')
        self.assertEqual(values['beneficiar_ci_serie'],terms['beneficiar_ci_serie'])
        self.assertEqual(values['beneficiar_judet'],terms['beneficiar_judet'])
        self.assertFalse(new['beneficiary_inherited'])
        self.assertEqual(new['terms'],{})
        for key in ('beneficiar_cnp','nr_contract','nr_oferta','data_contract','valoare_proiectare','adresa_strada','corespondenta_strada'):
            self.assertNotIn(key,values)
        self.assertIsNone(new['issued'])
        self.assertNotIn('contract_emis',iugn.get(new_lid)['state']['facts'])

    def test_saved_identity_does_not_cross_clients_and_current_profile_wins(self):
        lid,bundle,terms=self.setup_contract()
        db.adauga_client({'nume':'Alt client'})
        other_id=int(db.lista_clienti().query("nume == 'Alt client'").iloc[0]['id'])
        other=docs.open_form(self.new_contract_work(other_id))
        self.assertFalse(other['beneficiary_inherited'])
        self.assertNotIn('beneficiar_ci_nr',other['beneficiary_defaults'])
        with closing(db._connect()) as conn,conn:
            db._execute(conn.cursor(),'UPDATE clienti SET ci_numar=?,telefon=? WHERE id=1',('999999','0700000000'))
        new=docs.open_form(self.new_contract_work())
        self.assertEqual(new['beneficiary_defaults']['beneficiar_ci_nr'],'999999')
        self.assertEqual(new['beneficiary_defaults']['client_telefon'],'0700000000')
        self.assertEqual(new['beneficiary_defaults']['beneficiar_ci_serie'],bundle['client']['ci_serie'])
        self.assertEqual(new['beneficiary_defaults']['beneficiar_nume'],new['client']['nume'])

    def test_current_draft_is_not_replaced_by_beneficiary_prefill(self):
        lid,bundle,terms=self.setup_contract()
        new_lid=self.new_contract_work()
        own=dict(terms,beneficiar_ci_nr='444444',beneficiar_strada='')
        docs.save_draft(new_lid,own,expected_revision=0)
        new=docs.open_form(new_lid)
        self.assertNotIn('beneficiar_ci_nr',new['terms'])
        self.assertNotIn('beneficiar_strada',new['terms'])
        self.assertEqual(docs.canonical_terms(new['client'],new['work'],own)['beneficiar_ci_nr'],'012345')

    def test_cnp_is_not_copied_from_client_or_legacy_draft_into_contract_snapshot(self):
        lid,bundle,terms=self.setup_contract()
        with closing(db._connect()) as conn,conn:
            db._execute(conn.cursor(),'UPDATE clienti SET cnp=? WHERE id=1',('0000000000000',))
        rev=docs.save_draft(lid,dict(terms,beneficiar_cnp='0000000000000'),expected_revision=bundle['draft_revision'])
        bundle=docs.open_form(lid)
        self.assertNotIn('cnp',bundle['client'])
        self.assertNotIn('beneficiar_cnp',bundle['terms'])
        docs.issue(lid,bundle,terms)
        snapshot=docs.open_form(lid)['issued']['snapshot']
        self.assertNotIn('0000000000000',snapshot)

    def test_client_profile_wins_over_work_draft_and_issued_snapshot_stays_fixed(self):
        import json
        lid,bundle,terms=self.setup_contract()
        terms=dict(terms,beneficiar_ci_nr='999999',adresa_strada='Adresa gresita')
        docs.issue(lid,bundle,terms)
        original=docs.open_form(lid)['issued']['snapshot']
        ctx=json.loads(original)['context']
        self.assertEqual(ctx['beneficiar_ci_nr'],'012345')
        self.assertNotEqual(ctx['adresa_strada'],'Adresa gresita')
        work=db.get_lucrare(lid)
        db.modifica_client(1,{'domiciliu_strada':'Domiciliu nou','ci_numar':'888888'})
        self.assertEqual(db.get_lucrare(lid),work)
        self.assertEqual(docs.open_form(lid)['issued']['snapshot'],original)
        new=docs.open_form(self.new_contract_work())
        self.assertEqual(new['beneficiary_defaults']['beneficiar_ci_nr'],'888888')
        self.assertEqual(new['beneficiary_defaults']['beneficiar_strada'],'Domiciliu nou')

    def test_reviewed_profile_blank_fields_stay_blank_and_stale_save_is_rejected(self):
        lid,bundle,terms=self.setup_contract()
        before=bundle['client']
        db.modifica_client(1,{'ci_emitent':''},expected_revision=before['profile_revision'])
        self.assertEqual(docs.open_form(lid)['beneficiary_defaults']['beneficiar_ci_emitent'],'')
        with self.assertRaisesRegex(ValueError,'alta sesiune'):
            db.modifica_client(1,{'ci_numar':'999999'},expected_revision=before['profile_revision'])
        self.assertEqual(docs.open_form(lid)['client']['ci_numar'],'012345')

    def test_legacy_client_profile_recovers_own_contract_data_for_review(self):
        lid,bundle,terms=self.setup_contract()
        with closing(db._connect()) as conn,conn:
            db._execute(conn.cursor(),"UPDATE clienti SET profile_saved=0,ci_serie='',ci_numar='',ci_emitent='',ci_data='' WHERE id=1",())
            db._execute(conn.cursor(),'UPDATE iugn_contract_drafts SET payload=? WHERE lucrare_id=?',(docs._dump(terms),lid))
        with closing(db._connect()) as conn:
            client=docs._row(conn,'SELECT * FROM clienti WHERE id=1',())
            recovered,inherited=docs._beneficiary_defaults(conn,client,0)
        self.assertTrue(inherited)
        self.assertEqual(recovered['beneficiar_ci_nr'],'012345')
        self.assertNotIn('adresa_strada',recovered)

    def test_contract_and_mandate_are_issued_together_from_same_snapshot(self):
        import json
        from db import iugn_mandates
        lid,bundle,terms=self.setup_contract()
        docs.issue(lid,bundle,terms)
        service=docs.open_form(lid)['issued'];mandate=iugn_mandates.get(lid)
        self.assertEqual(mandate['number'],service['number'].replace('CTR-','MDT-',1))
        ctx=json.loads(mandate['snapshot'])
        self.assertEqual(ctx['contract_sha256'],service['sha256'])
        self.assertEqual(ctx['context']['nr_contract'],service['number'])
        self.assertIn('012345',ctx['context']['mandant_identificare'])
        self.assertNotIn('CNP',ctx['context']['mandant_identificare'])
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),2)
        self.assertNotIn('contract_semnat',iugn.get(lid)['state']['facts'])

    def old_contract_without_mandate(self):
        from db import iugn_mandates
        lid,bundle,terms=self.setup_contract();docs.issue(lid,bundle,terms)
        mandate=iugn_mandates.get(lid)
        with closing(db._connect()) as conn,conn:
            db._execute(conn.cursor(),'DELETE FROM iugn_mandate_issues WHERE lucrare_id=?',(lid,))
            db._execute(conn.cursor(),'DELETE FROM atasamente WHERE path=?',(mandate['path'],))
        Path(mandate['path']).unlink()
        return lid

    def test_add_mandate_to_old_contract_uses_original_identity_and_address(self):
        import json
        from db import iugn_mandates
        lid=self.old_contract_without_mandate()
        original=docs.open_form(lid)['issued'];flow=iugn.get(lid)
        db.modifica_client(1,{'ci_numar':'999999','nume':'Alt nume'})
        work=db.get_lucrare(lid);db.modifica_lucrare(lid,dict(work,adresa_strada='Alta strada'),expected_revision=work['revision'])
        approved=iugn_mandates.preview(lid)
        result=iugn_mandates.issue_existing(lid,approved)
        ctx=json.loads(iugn_mandates.get(lid)['snapshot'])['context']
        self.assertIn('012345',ctx['mandant_identificare'])
        self.assertNotIn('Alt nume',ctx['mandant_identificare'])
        self.assertNotIn('Alta strada',ctx['adresa_lucrare'])
        self.assertEqual(docs.open_form(lid)['issued'],original)
        self.assertEqual(iugn.get(lid),flow)
        with self.assertRaisesRegex(ValueError,'deja emis'):iugn_mandates.issue_existing(lid,approved)
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),2)

    def test_mandate_failure_rolls_back_both_documents_and_counter(self):
        from utils import iugn_mandate
        lid,bundle,terms=self.setup_contract()
        with closing(db._connect()) as conn:
            row=db._execute(conn.cursor(),'SELECT last_ctr FROM contracte_seq WHERE an=?',(date.today().year,)).fetchone()
        before=row[0] if row else 0
        with patch.object(iugn_mandate,'generate',side_effect=OSError('mandate generation failed')):
            with self.assertRaises(OSError):docs.issue(lid,bundle,terms)
        with closing(db._connect()) as conn:
            row=db._execute(conn.cursor(),'SELECT last_ctr FROM contracte_seq WHERE an=?',(date.today().year,)).fetchone()
        self.assertEqual(row[0] if row else 0,before)
        self.assertIsNone(docs.open_form(lid)['issued'])
        self.assertTrue(db.lista_atasamente(1,lucrare_id=lid).empty)
        self.assertFalse(list(Path(db.UPLOAD_DIR).rglob('*.docx')))
        self.assertNotIn('contract_emis',iugn.get(lid)['state']['facts'])

    def test_changed_mandate_template_rejects_stale_preview(self):
        from db import iugn_mandates
        from utils import iugn_mandate
        from docx import Document
        lid=self.old_contract_without_mandate()
        approved=iugn_mandates.preview(lid)
        d=Document(iugn_mandate.TEMPLATE);d.add_paragraph('Changed');d.save(iugn_mandate.TEMPLATE)
        with self.assertRaisesRegex(ValueError,'Sablonul'):iugn_mandates.issue_existing(lid,approved)
        self.assertIsNone(iugn_mandates.get(lid))
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),1)

    def test_mandate_issuance_rechecks_write_permission(self):
        from db import iugn_mandates
        lid=self.old_contract_without_mandate()
        approved=iugn_mandates.preview(lid)
        db.adauga_utilizator('mandate_viewer','Temporary-password-123','vizualizare',must_change_password=0)
        permissions.bind_actor('mandate_viewer',permissions.password_marker(db.get_utilizator('mandate_viewer')))
        try:
            with self.assertRaises(PermissionError):iugn_mandates.issue_existing(lid,approved)
        finally:permissions.clear_actor()
        self.assertIsNone(iugn_mandates.get(lid))

    def bind_contract_admin(self):
        permissions.clear_actor()
        db.seteaza_must_change_password('admin',0)
        permissions.bind_actor('admin',permissions.password_marker(db.get_utilizator('admin')))
        self.addCleanup(permissions.clear_actor)

    def test_browser_cannot_confirm_contract_without_document(self):
        lid,bundle,terms=self.setup_contract()
        self.bind_contract_admin()
        before=iugn.get(lid)
        with self.assertRaisesRegex(ValueError,'Documente'):
            iugn.record_event(lid,'contract_emis',date.today().isoformat(),expected_revision=before['revision'])
        self.assertEqual(iugn.get(lid),before)
        self.assertIsNone(docs.open_form(lid)['issued'])

    def test_browser_issue_confirms_contract_with_saved_document(self):
        lid,bundle,terms=self.setup_contract()
        self.bind_contract_admin()
        result=docs.issue(lid,bundle,terms)
        self.assertIn('contract_emis',iugn.get(lid)['state']['facts'])
        self.assertEqual(docs.open_form(lid)['issued']['number'],result['number'])

    def test_unlinked_confirmation_is_corrected_with_audit(self):
        lid,bundle,terms=self.setup_contract()
        iugn.record_event(lid,'contract_emis',date.today().isoformat(),expected_revision=iugn.get(lid)['revision'])
        revision=iugn.get(lid)['revision']
        self.bind_contract_admin()
        with self.assertRaisesRegex(ValueError,'Motivul'):
            iugn.correct_unlinked_contract(lid,expected_revision=revision,reason='')
        iugn.correct_unlinked_contract(lid,expected_revision=revision,reason='Confirmare facuta din greseala')
        state=iugn.get(lid)
        self.assertNotIn('contract_emis',state['state']['facts'])
        self.assertIn('documente_complete',state['state']['facts'])
        self.assertEqual(db.get_lucrare(lid)['status'],'OFERTAT')
        self.assertEqual(db.get_lucrare(lid)['valoare_contractata'],bundle['work']['valoare_contractata'])
        self.assertIn('contract_emis',set(iugn.history(lid)['event_key']))
        self.assertIn('corectie_contract_emis',set(iugn.history(lid)['event_key']))
        with self.assertRaises(ValueError):
            iugn.correct_unlinked_contract(lid,expected_revision=revision,reason='Repetare')
        self.assertTrue(db.lista_atasamente(1,lucrare_id=lid).empty)

    def test_correction_never_cancels_registered_contract(self):
        lid,bundle,terms=self.setup_contract()
        self.bind_contract_admin()
        result=docs.issue(lid,bundle,terms)
        before=iugn.get(lid)
        with self.assertRaisesRegex(ValueError,'Exista un contract emis'):
            iugn.correct_unlinked_contract(lid,expected_revision=before['revision'],reason='Nu se poate anula documentul')
        self.assertEqual(iugn.get(lid),before)
        self.assertEqual(docs.open_form(lid)['issued']['number'],result['number'])

    def test_correction_rejects_downstream_confirmations(self):
        lid,bundle,terms=self.setup_contract()
        for key in ('contract_emis','contract_semnat'):
            iugn.record_event(lid,key,date.today().isoformat(),expected_revision=iugn.get(lid)['revision'])
        before=iugn.get(lid)
        self.bind_contract_admin()
        with self.assertRaisesRegex(ValueError,'Exista etape'):
            iugn.correct_unlinked_contract(lid,expected_revision=before['revision'],reason='Corectie')
        self.assertEqual(iugn.get(lid),before)

    def setup_contract(self):
        permissions.clear_actor()
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        path=Path(temp.name)
        p=patch.object(ic,'TEMPLATE',make_template(path/'synthetic.docx'));p.start();self.addCleanup(p.stop)
        from utils import iugn_mandate
        from docx import Document
        m=Document();m.add_paragraph('Mandat {{ nr_mandat }} contract {{ nr_contract }} {{ mandant_identificare }} {{ adresa_lucrare }} {{ mandatar_identificare }}');m.save(path/'mandate.docx')
        p=patch.object(iugn_mandate,'TEMPLATE',path/'mandate.docx');p.start();self.addCleanup(p.stop)
        p=patch.object(db,'UPLOAD_DIR',str(path/'uploads'));p.start();self.addCleanup(p.stop)
        client,work,firm,terms=fixture()
        terms.pop('nr_contract')
        terms['beneficiar_ci_nr']='012345'
        # Use a valid example licence, never an actual company's credentials.
        firm['autorizatie_executie_numar']='TEST-1';firm['autorizatie_proiectare_numar']='TEST-2'
        terms['data_contract']=date.today().isoformat()
        firm.update(autorizatie_proiectare_expirare='2099-12-31',autorizatie_executie_expirare='2099-12-31')
        s=company.get();company.save(firm,expected_revision=s['revision'])
        identity={source:terms.get(name,client.get(source,'')) for name,source in ic.CLIENT_FIELDS.items()}
        identity.update(profile_saved=1,nume='Client demonstrativ',email='client@example.invalid')
        db.modifica_client(1,identity)
        db.adauga_lucrare({'client_id':1,'tip_lucrare':'Instalatie de utilizare noua',
                          'valoare_contractata':2800,'descriere':'Centrala & aragaz',
                          **{k:v for k,v in terms.items() if k.startswith('adresa_')}})
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
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),2)
        current=iugn.get(lid)
        self.assertEqual(current['revision'],before+1)
        self.assertIn('contract_emis',current['state']['facts'])
        self.assertNotIn('contract_semnat',current['state']['facts'])
        self.assertEqual(Path(docs.open_form(lid)['issued']['path']).read_bytes(),result['data'])
        with self.assertRaisesRegex(ValueError,'deja emis'):docs.issue(lid,bundle,terms)
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),2)

    def test_changed_configuration_rejects_issue_without_consuming_number(self):
        lid,bundle,terms=self.setup_contract()
        s=company.get();company.save(dict(s['values'],executant_email='changed@example.invalid'),expected_revision=s['revision'])
        with self.assertRaisesRegex(ValueError,'Configuratia'):docs.issue(lid,bundle,terms)
        self.assertTrue(db.lista_atasamente(1,lucrare_id=lid).empty)
        self.assertNotIn('contract_emis',iugn.get(lid)['state']['facts'])

    def test_file_failure_rolls_back_counter_and_flow(self):
        lid,bundle,terms=self.setup_contract()
        with closing(db._connect()) as conn:
            row=db._execute(conn.cursor(),'SELECT last_ctr FROM contracte_seq WHERE an=?',(date.today().year,)).fetchone()
        before=row[0] if row else 0
        with patch.object(ic,'generate_contract',side_effect=OSError('test write error')):
            with self.assertRaises(OSError):docs.issue(lid,bundle,terms)
        with closing(db._connect()) as conn:
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
