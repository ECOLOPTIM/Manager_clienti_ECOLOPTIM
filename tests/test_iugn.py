"""Business rules exercised through the persistence API on disposable data."""
import concurrent.futures
from contextlib import closing
from datetime import date, timedelta
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from db import db, iugn, iugn_rules as rules, permissions


class IUGNChecks:
    def create_iugn(self):
        permissions.clear_actor()
        db.seteaza_must_change_password('admin', 0)
        for username in ('responsible', 'designer', 'commercial'):
            if not db.get_utilizator(username):
                db.adauga_utilizator(username, 'Test-password-123', 'birou', must_change_password=0)
        db.adauga_lucrare({'client_id': 1, 'tip_lucrare': rules.WORK_TYPE, 'status': 'OFERTAT'})
        self.lid = int(db.lista_lucrari_client(1).iloc[0]['id'])
        self.day = date.today().isoformat()
        return self.lid

    def event(self, key, **kw):
        return iugn.record_event(self.lid, key, self.day,
                                 expected_revision=iugn.get(self.lid)['revision'], **kw)

    def bind(self, username):
        permissions.bind_actor(username, permissions.password_marker(db.get_utilizator(username)))

    def contract(self):
        self.create_iugn()
        for key in ('oferta_acceptata', 'documente_complete', 'contract_emis', 'contract_semnat'):
            self.event(key)
        self.assign()

    def assign(self):
        iugn.assign_roles(self.lid, {'responsabil': 'responsible', 'proiectant': 'designer',
                                    'comercial': 'commercial'}, expected_revision=iugn.get(self.lid)['revision'])

    def notified(self):
        self.contract()
        for key in ('avans_confirmat', 'cerere_depusa', 'nota_analiza_transmisa', 'notificare_primita'):
            self.event(key)

    def test_iugn_new_work_uses_specific_tasks_other_types_keep_legacy(self):
        self.create_iugn()
        tasks = db.lista_sarcini_lucrare(self.lid)
        self.assertEqual(set(tasks['cod_flux']), set(rules.BY_KEY))
        self.assertEqual(len(tasks), len(rules.STEPS))
        db.adauga_lucrare({'client_id': 1, 'tip_lucrare': 'Instalatie termica noua'})
        self.assertEqual(len(db.lista_sarcini_lucrare(self.lid + 1)), 5)

    def test_iugn_migration_and_activation_are_idempotent_preserve_legacy(self):
        self.create_iugn()
        with closing(db._connect()) as conn, conn:
            db._execute(conn.cursor(), "INSERT INTO sarcini(client_id,lucrare_id,tip_sarcina,status) VALUES (1,?,'Legacy','FINALIZAT')", (self.lid,))
        db.init_db()
        iugn.activate(self.lid)
        iugn.activate(self.lid)
        self.assertEqual(len(db.lista_sarcini_lucrare(self.lid)), len(rules.STEPS) + 1)
        self.assertEqual(len(iugn.history(self.lid)), 1)

    def test_iugn_real_legacy_work_activation_preserves_completed_tasks(self):
        db.adauga_lucrare({'client_id': 1, 'tip_lucrare': 'Instalatie termica noua'})
        lid = int(db.lista_lucrari_client(1).iloc[0]['id'])
        task_id = int(db.lista_sarcini_lucrare(lid).iloc[0]['id'])
        db.update_sarcina(task_id, status='FINALIZAT', observatii='De pastrat')
        old = db.get_lucrare(lid)
        db.modifica_lucrare(lid, dict(old, tip_lucrare=rules.WORK_TYPE), expected_revision=old['revision'])
        self.assertIsNone(iugn.get(lid))
        iugn.activate(lid)
        tasks = db.lista_sarcini_lucrare(lid)
        legacy = tasks[tasks['id'] == task_id].iloc[0]
        self.assertEqual((legacy['status'], legacy['observatii']), ('FINALIZAT', 'De pastrat'))
        self.assertEqual(len(tasks), 5 + len(rules.STEPS))

    def test_iugn_contract_advance_and_all_roles_gate_portal(self):
        self.create_iugn()
        for key in ('oferta_acceptata', 'documente_complete', 'contract_emis'):
            self.event(key)
        with self.assertRaises(ValueError):
            self.assign()
        with self.assertRaises(ValueError):
            self.event('cerere_depusa')
        self.event('contract_semnat')
        self.assign()
        with self.assertRaises(ValueError):
            self.event('cerere_depusa')
        self.event('avans_confirmat')
        self.event('cerere_depusa')

    def test_iugn_only_manager_approves_exceptions_and_assigns_people(self):
        self.create_iugn()
        for key in ('oferta_acceptata', 'documente_complete', 'contract_emis'):
            self.event(key)
        self.bind('commercial')
        for key in ('exceptie_contract', 'exceptie_avans'):
            with self.assertRaises(PermissionError):
                self.event(key, note='Test')
        with self.assertRaises(PermissionError):
            self.assign()
        self.bind('admin')
        self.event('exceptie_contract', note='Client in strainatate')
        self.event('exceptie_avans', note='Exceptie convenita')
        self.assign()
        self.event('cerere_depusa')
        self.assertEqual(len(rules.outstanding_exceptions(iugn.get(self.lid)['state'])), 2)
        self.event('contract_semnat')
        self.event('avans_confirmat')
        self.assertEqual(rules.outstanding_exceptions(iugn.get(self.lid)['state']), [])

    def test_iugn_second_admin_is_not_implicitly_gelu(self):
        self.contract()
        db.adauga_utilizator('other_admin', 'Test-password-123', 'admin', must_change_password=0)
        self.bind('other_admin')
        with self.assertRaises(PermissionError):
            self.assign()
        with self.assertRaises(PermissionError):
            self.event('exceptie_avans', note='Cannot approve')

    def test_iugn_parallel_design_and_execution_with_responsible_decision(self):
        self.notified()
        self.event('notificare_proiectant')
        self.bind('admin')
        self.event('executie_programata', scheduled_for=self.day, team='Echipa A')
        self.event('ordin_executie_predat')
        with self.assertRaises(ValueError):
            self.event('executie_finalizata')
        with self.assertRaises(PermissionError):
            self.event('executie_fara_proiect', note='Decision belongs to responsible')
        self.bind('responsible')
        self.event('executie_fara_proiect', note='Proiectul este in lucru')
        self.event('executie_finalizata')
        state = iugn.get(self.lid)['state']
        self.assertEqual(rules.stream_states(state)['Proiect'], 'La proiectant')
        self.assertEqual(rules.stream_states(state)['Executie'], 'Executata')
        self.assertEqual(len(rules.outstanding_exceptions(state)), 1)
        with self.assertRaises(ValueError):
            self.event('solicitare_pif')
        self.bind('designer')
        self.event('proiect_intocmit')
        self.bind('responsible')
        self.event('proiect_avizat')
        self.event('contract_furnizare')
        self.event('solicitare_pif')
        self.assertFalse(rules.outstanding_exceptions(iugn.get(self.lid)['state']))

    def test_iugn_successful_path_keeps_pif_completion_separate_from_archive(self):
        self.notified()
        for key in ('notificare_proiectant', 'proiect_intocmit', 'proiect_avizat'):
            self.event(key)
        self.event('executie_programata', scheduled_for=self.day, team='Echipa A')
        for key in ('ordin_executie_predat', 'executie_finalizata', 'ordin_executie_arhivat',
                    'contract_furnizare', 'solicitare_pif', 'nota_pif_transmisa'):
            self.event(key)
        self.event('programare_pif_primita', scheduled_for=self.day)
        with self.assertRaises(ValueError):
            self.event('pif_efectuata')
        self.event('echipa_pif_alocata', team='Echipa PIF')
        self.event('dosar_pif_predat')
        self.event('pif_efectuata')
        self.assertNotIn('copie_pv_pif_arhivata', iugn.get(self.lid)['state']['facts'])
        self.event('copie_pv_pif_arhivata')
        self.assertEqual(db.get_lucrare(self.lid)['status'], 'FINALIZAT')
        self.assertEqual(db.get_lucrare(self.lid)['data_programare_pif'], self.day)
        self.assertEqual(db.get_lucrare(self.lid)['echipa_pif'], 'Echipa PIF')

    def test_iugn_stale_saves_keep_first_event_and_audit(self):
        self.create_iugn()
        self.event('oferta_acceptata', note='A')
        with self.assertRaises(iugn.WorkflowConflict):
            iugn.record_event(self.lid, 'oferta_acceptata', self.day, expected_revision=0, note='B')
        self.assertEqual(iugn.get(self.lid)['state']['facts']['oferta_acceptata']['note'], 'A')
        self.assertEqual(len(iugn.history(self.lid)), 2)

    def test_iugn_concurrent_saves_one_winner_and_one_event(self):
        self.create_iugn()
        barrier = threading.Barrier(2)
        def save(note):
            barrier.wait(timeout=10)
            try:
                iugn.record_event(self.lid, 'oferta_acceptata', self.day, expected_revision=0, note=note)
                return 'saved'
            except iugn.WorkflowConflict:
                return 'conflict'
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(save, ['A', 'B'])), ['conflict', 'saved'])
        self.assertEqual(len(iugn.history(self.lid)), 2)

    def test_iugn_managed_tasks_cannot_bypass_workflow_api(self):
        self.create_iugn()
        task_id = int(db.lista_sarcini_lucrare(self.lid).iloc[0]['id'])
        with self.assertRaises(ValueError):
            db.update_sarcina(task_id, status='FINALIZAT')
        row = db.get_lucrare(self.lid)
        for field, value in [('responsabil', 'Fake'), ('status', 'INCHIS'), ('tip_lucrare', 'Other'),
                             ('data_programare', '2026-11-01'), ('client_id', 2)]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                db.modifica_lucrare(self.lid, dict(row, **{field: value}), expected_revision=row['revision'])
        db.modifica_lucrare(self.lid, dict(row, descriere='Allowed text'), expected_revision=row['revision'])

    def test_iugn_viewer_deactivated_and_password_reset_cannot_write(self):
        self.create_iugn()
        db.adauga_utilizator('viewer_iugn', 'Test-password-123', 'vizualizare', must_change_password=0)
        self.bind('viewer_iugn')
        with self.assertRaises(PermissionError):
            self.event('oferta_acceptata')
        permissions.clear_actor()
        self.bind('commercial')
        permissions.clear_actor()
        marker = permissions.password_marker(db.get_utilizator('commercial'))
        db.seteaza_activ_utilizator('commercial', 0)
        permissions.bind_actor('commercial', marker)
        with self.assertRaises(PermissionError):
            iugn.activate(self.lid)
        with self.assertRaises(PermissionError):
            self.event('oferta_acceptata')

    def test_iugn_no_unknown_duplicate_future_or_backdated_event(self):
        self.create_iugn()
        with self.assertRaises(ValueError):
            self.event('unknown')
        with self.assertRaises(ValueError):
            iugn.record_event(self.lid, 'oferta_acceptata', str(date.today()+timedelta(days=1)), expected_revision=0)
        self.event('oferta_acceptata')
        with self.assertRaises(ValueError):
            self.event('oferta_acceptata')
        with self.assertRaises(ValueError):
            iugn.record_event(self.lid, 'documente_complete', str(date.today()-timedelta(days=1)), expected_revision=1)

    def test_iugn_only_assigned_designer_can_confirm_design(self):
        self.notified()
        self.event('notificare_proiectant')
        self.bind('commercial')
        with self.assertRaises(PermissionError):
            self.event('proiect_intocmit')
        self.bind('designer')
        self.event('proiect_intocmit')
        event = iugn.history(self.lid).iloc[0]
        self.assertEqual(event['actor'], 'designer')

    def test_iugn_rescheduling_reopens_work_order_and_preserves_history(self):
        self.notified()
        self.event('executie_programata', scheduled_for=self.day, team='Echipa A')
        self.event('ordin_executie_predat')
        self.event('reprogramare_executie', scheduled_for=str(date.today()+timedelta(days=2)),
                   team='Echipa B', note='Clientul a solicitat amanarea')
        state = iugn.get(self.lid)['state']
        self.assertNotIn('ordin_executie_predat', state['facts'])
        self.assertEqual(state['facts']['executie_programata']['team'], 'Echipa B')
        self.assertTrue((iugn.history(self.lid)['event_key'] == 'ordin_executie_predat').any())
        self.assertEqual(db.get_lucrare(self.lid)['echipa'], 'Echipa B')

    def test_iugn_event_audit_and_tasks_roll_back_together(self):
        self.create_iugn()
        with patch.object(iugn, '_audit', side_effect=RuntimeError('Simulated audit failure')):
            with self.assertRaises(RuntimeError):
                self.event('oferta_acceptata')
        self.assertEqual(iugn.get(self.lid)['revision'], 0)
        self.assertFalse(iugn.get(self.lid)['state']['facts'])
        self.assertEqual(len(iugn.history(self.lid)), 1)
        self.assertEqual(db.lista_sarcini_lucrare(self.lid).iloc[0]['status'], 'NOU')

    def test_iugn_pif_reschedule_reopens_fee_team_and_dossier(self):
        self.notified()
        for key in ('notificare_proiectant', 'proiect_intocmit', 'proiect_avizat'):
            self.event(key)
        self.event('executie_programata', scheduled_for=self.day, team='A')
        for key in ('ordin_executie_predat', 'executie_finalizata', 'contract_furnizare',
                    'solicitare_pif', 'nota_pif_transmisa'):
            self.event(key)
        self.event('programare_pif_primita', scheduled_for=self.day)
        self.event('echipa_pif_alocata', team='PIF A')
        self.event('dosar_pif_predat')
        self.bind('responsible')
        self.event('reprogramare_pif', scheduled_for=str(date.today()+timedelta(days=1)),
                   note='Programare noua primita de la operator')
        state = iugn.get(self.lid)['state']
        for key in ('nota_pif_transmisa', 'echipa_pif_alocata', 'dosar_pif_predat'):
            self.assertNotIn(key, state['facts'])
        self.assertEqual(db.get_lucrare(self.lid)['echipa_pif'], '')
        self.assertIn('nota_pif_transmisa', set(iugn.history(self.lid)['event_key']))


class SQLiteIUGN(IUGNChecks, unittest.TestCase):
    def setUp(self):
        permissions.clear_actor()
        self.tmp = tempfile.TemporaryDirectory()
        self.old = db.DB_PATH, db.DATABASE_URL
        db.DB_PATH, db.DATABASE_URL = str(Path(self.tmp.name)/'test.db'), ''
        db.init_db()
        db.adauga_client({'nume': 'TEST A'})
        db.adauga_client({'nume': 'TEST B'})

    def tearDown(self):
        permissions.clear_actor()
        db.DB_PATH, db.DATABASE_URL = self.old
        self.tmp.cleanup()


if __name__ == '__main__':
    unittest.main(verbosity=2)
