from contextlib import closing
from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from db import db, permissions, iugn, iugn_documents as issued, iugn_step_documents as documents
from tests.test_iugn_documents import ContractIssueCases


class StepDocumentCases:
    def prepared_step_work(self):
        lid,bundle,terms=self.setup_contract()
        issued.issue(lid,bundle,terms)
        return lid

    def put_step_file(self,lid,step='contract_semnat',kind='contract_semnat',content=b'%PDF-test-signed',**kwargs):
        return documents.upload(lid,step,kind,[('exemplar_semnat.pdf',content)],
            expected_revision=kwargs.pop('expected_revision',iugn.get(lid)['revision']),
            occurred_on=kwargs.pop('occurred_on',date.today().isoformat()),**kwargs)

    def test_signed_contract_confirms_atomically_and_originals_remain_downloadable(self):
        lid=self.prepared_step_work();originals=documents.list_for_work(lid)
        self.assertEqual({x['kind'] for x in originals},{'contract_emis','mandat_emis'})
        before=iugn.get(lid)['revision']
        result=self.put_step_file(lid,confirm=True,reference='CTR-SIGN')
        self.assertTrue(result['confirmed'])
        state=iugn.get(lid)
        self.assertEqual(state['revision'],before+1)
        self.assertIn('contract_semnat',state['state']['facts'])
        files=documents.list_for_work(lid)
        signed=next(x for x in files if x['kind']=='contract_semnat')
        data,name,mime=documents.download(lid,'uploaded',signed['id'])
        self.assertEqual(data,b'%PDF-test-signed');self.assertEqual(mime,'application/pdf')
        self.assertEqual(signed['reference'],'CTR-SIGN')
        for item in originals:
            data,_,_=documents.download(lid,item['origin'],lid)
            self.assertEqual(data,Path(item['path']).read_bytes())
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),3)

    def test_signed_mandate_does_not_confirm_service_contract(self):
        lid=self.prepared_step_work()
        result=self.put_step_file(lid,kind='mandat_semnat',confirm=True)
        self.assertFalse(result['confirmed'])
        self.assertNotIn('contract_semnat',iugn.get(lid)['state']['facts'])
        self.assertEqual(iugn.history(lid).iloc[0]['event_key'],'document_incarcat')

    def test_duplicate_stale_and_cross_work_download_are_rejected(self):
        lid=self.prepared_step_work();revision=iugn.get(lid)['revision']
        self.put_step_file(lid)
        with self.assertRaises(iugn.WorkflowConflict):self.put_step_file(lid,content=b'other',expected_revision=revision)
        with self.assertRaisesRegex(ValueError,'deja incarcat'):self.put_step_file(lid)
        other=self.new_contract_work()
        signed=next(x for x in documents.list_for_work(lid) if x['kind']=='contract_semnat')
        with self.assertRaisesRegex(ValueError,'nu apartine'):documents.download(other,'uploaded',signed['id'])
        self.assertEqual(len(documents.list_for_work(lid)),3)

    def test_failed_confirmation_rolls_back_file_attachment_and_audit(self):
        lid=self.prepared_step_work();before=iugn.get(lid)
        paths=set(Path(db.UPLOAD_DIR).rglob('*'))
        with patch.object(iugn,'record_event_in_transaction',side_effect=ValueError('test failure')):
            with self.assertRaisesRegex(ValueError,'test failure'):self.put_step_file(lid,confirm=True)
        self.assertEqual(iugn.get(lid),before)
        self.assertEqual(set(Path(db.UPLOAD_DIR).rglob('*')),paths)
        self.assertEqual(len(documents.list_for_work(lid)),2)
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),2)

    def test_blocked_stage_can_store_document_but_cannot_confirm(self):
        lid=self.prepared_step_work();before=iugn.get(lid)
        self.put_step_file(lid,step='notificare_primita',kind='notificare')
        self.assertNotIn('notificare_primita',iugn.get(lid)['state']['facts'])
        with self.assertRaisesRegex(ValueError,'Lipseste'):
            self.put_step_file(lid,step='notificare_primita',kind='notificare',content=b'next',confirm=True)
        self.assertEqual(len(documents.list_for_work(lid)),3)
        self.assertEqual(iugn.get(lid)['revision'],before['revision']+1)

    def test_missing_required_kind_does_not_advance_or_leave_partial_upload(self):
        lid=self.prepared_step_work()
        with self.assertRaisesRegex(ValueError,'Izometrie'):
            self.put_step_file(lid,step='proiect_avizat',kind='proiect_avizat',confirm=True)
        self.assertEqual(len(documents.list_for_work(lid)),2)

    def test_wrong_owner_and_viewer_cannot_upload_or_confirm(self):
        lid=self.prepared_step_work()
        db.adauga_utilizator('other_step_user','Temporary-password-123','birou',must_change_password=0)
        with closing(db._connect()) as conn,conn:
            state=iugn._load(conn,lid)['state'];state['roles']['comercial']='admin'
            db._execute(conn.cursor(),'UPDATE iugn_flux SET payload=? WHERE lucrare_id=?',(iugn._dump(state),lid))
        permissions.bind_actor('other_step_user',permissions.password_marker(db.get_utilizator('other_step_user')))
        with self.assertRaises(PermissionError):self.put_step_file(lid,confirm=True)
        permissions.clear_actor()
        db.adauga_utilizator('step_viewer','Temporary-password-123','vizualizare',must_change_password=0)
        permissions.bind_actor('step_viewer',permissions.password_marker(db.get_utilizator('step_viewer')))
        with self.assertRaises(PermissionError):self.put_step_file(lid)
        self.assertEqual(len(documents.list_for_work(lid)),2)

    def test_tampered_or_missing_file_is_reported_and_generic_delete_is_blocked(self):
        lid=self.prepared_step_work();self.put_step_file(lid)
        signed=next(x for x in documents.list_for_work(lid) if x['kind']=='contract_semnat')
        att=db.lista_atasamente(1,lucrare_id=lid)
        aid=int(att[att['path']==signed['path']].iloc[0]['id'])
        with self.assertRaisesRegex(ValueError,'istoricul fluxului'):db.sterge_atasament(aid)
        Path(signed['path']).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'modificat'):documents.download(lid,'uploaded',signed['id'])
        Path(signed['path']).unlink()
        with self.assertRaisesRegex(ValueError,'lipseste'):documents.download(lid,'uploaded',signed['id'])

    def test_concurrent_uploads_keep_one_revision_and_one_file(self):
        import concurrent.futures
        lid=self.prepared_step_work();before=iugn.get(lid)['revision']
        def attempt(index):
            try:
                self.put_step_file(lid,content=('document-'+str(index)).encode(),expected_revision=before)
                return 'saved'
            except iugn.WorkflowConflict:return 'stale'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(attempt,range(2)))
        self.assertEqual(sorted(results),['saved','stale'])
        self.assertEqual(iugn.get(lid)['revision'],before+1)
        self.assertEqual(len(documents.list_for_work(lid)),3)
        self.assertEqual(len(db.lista_atasamente(1,lucrare_id=lid)),3)

    def test_manual_browser_confirmation_requires_signed_contract_evidence(self):
        lid=self.prepared_step_work()
        db.seteaza_must_change_password('admin',0)
        permissions.bind_actor('admin',permissions.password_marker(db.get_utilizator('admin')))
        with self.assertRaisesRegex(ValueError,'Incarca exemplarul semnat'):
            iugn.record_event(lid,'contract_semnat',date.today().isoformat(),expected_revision=iugn.get(lid)['revision'])
        self.put_step_file(lid,kind='mandat_semnat')
        with self.assertRaisesRegex(ValueError,'Incarca exemplarul semnat'):
            iugn.record_event(lid,'contract_semnat',date.today().isoformat(),expected_revision=iugn.get(lid)['revision'])
        self.put_step_file(lid,content=b'signed contract')
        iugn.record_event(lid,'contract_semnat',date.today().isoformat(),expected_revision=iugn.get(lid)['revision'])
        self.assertIn('contract_semnat',iugn.get(lid)['state']['facts'])

    def test_write_failure_leaves_no_documents_or_flow_changes(self):
        lid=self.prepared_step_work();before=iugn.get(lid)
        with patch.object(Path,'open',side_effect=OSError('write failed')):
            with self.assertRaises(OSError):self.put_step_file(lid,confirm=True)
        self.assertEqual(iugn.get(lid),before)
        self.assertEqual(len(documents.list_for_work(lid)),2)

    def test_empty_oversized_and_wrong_kind_do_not_write(self):
        lid=self.prepared_step_work();before=iugn.get(lid)
        for kind,data in (('bad',b'a'),('contract_semnat',b'')):
            with self.assertRaises(ValueError):self.put_step_file(lid,kind=kind,content=data)
        with patch.object(db,'MAX_UPLOAD_BYTES',2):
            with self.assertRaises(ValueError):self.put_step_file(lid,content=b'big')
        self.assertEqual(iugn.get(lid),before)
        self.assertEqual(len(documents.list_for_work(lid)),2)


class StepDocumentsSQLite(StepDocumentCases,unittest.TestCase):
    setup_contract=ContractIssueCases.setup_contract
    new_contract_work=ContractIssueCases.new_contract_work
    def setUp(self):
        permissions.clear_actor();self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.old=db.DB_PATH,db.DATABASE_URL
        db.DB_PATH,db.DATABASE_URL=str(Path(self.tmp.name)/'steps.db'),''
        db.init_db();db.seteaza_must_change_password('admin',0)
        db.adauga_client({'nume':'Client demonstrativ'})
    def tearDown(self):
        permissions.clear_actor();db.DB_PATH,db.DATABASE_URL=self.old
