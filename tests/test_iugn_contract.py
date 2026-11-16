import unittest
from io import BytesIO
from docx import Document
from docxtpl import DocxTemplate
import tempfile
from pathlib import Path
from unittest.mock import patch
from tests.iugn_template_fixture import make_template
from utils import iugn_contract as ic
from utils.iugn_contract import (
    TEMPLATE, ContractDataError, generate_contract, prepare_context,
)


def fixture(kind='PF'):
    names = DocxTemplate(ic.TEMPLATE).get_undeclared_template_variables()
    company = {n: 'Exemplu' for n in names if n.startswith(('executant_', 'autorizatie_', 'gdpr_'))}
    terms = {n: 'Exemplu' for n in names if n not in company}
    company.update(executant_denumire='ECOLOPTIM SRL', executant_email='test@example.invalid',
                   autorizatie_proiectare_expirare='2030-12-31',
                   autorizatie_executie_expirare='2030-12-31', gdpr_contact_dpo='')
    for name in ('valoare_totala', 'valoare_proiect_verificare', 'valoare_executie',
                 'avans_suma', 'executie_procent', 'executie_suma', 'pif_suma'):
        terms.pop(name)
    for n in ('beneficiar_nume','client_email','beneficiar_ci_nr','data_contract','descriere_lucrare'):
        terms.pop(n)
    terms.update(beneficiar_tip=kind, beneficiar_firma='Firma Client SRL',
                 corespondenta_diferita=False, beneficiar_banca='', beneficiar_iban='',
                 beneficiar_ci_data='2020-01-01', nr_contract='DEMO-1',
                 data_oferta='2026-10-30', data_deviz='2026-10-30',
                 durata_contract_zile=90, **ic.deadlines.STAGE_DEFAULTS, avans_procent=50,
                 valoare_proiectare=500, valoare_verificare=100, valoare_avize=0,
                 valoare_executie_receptie=2100, valoare_asistenta_pif=100)
    client={'id': 1, 'nume': 'Ion & Ana <Test>', 'email': 'client@example.invalid', 'ci_numar': '012345'}
    work={'id': 2, 'client_id': 1, 'valoare_contractata': 2800,
          'data_contract': '2026-10-30', 'descriere': 'Centrala & aragaz'}
    return client, work, company, terms


class ContractIUGNTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.patcher=patch.object(ic,'TEMPLATE',make_template(Path(self.tmp.name)/'synthetic.docx'))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_pf_and_pj_generate_readable_escaped_documents(self):
        for kind in ('PF', 'PJ'):
            with self.subTest(kind=kind):
                data=generate_contract(*fixture(kind))
                text='\n'.join(p.text for p in Document(BytesIO(data)).paragraphs)
                self.assertIn('Ion & Ana <Test>', text)
                self.assertIn('Centrala & aragaz', text)
                self.assertIn('Anexa 4 Formular', text)
                self.assertEqual('Beneficiar persoana juridica:' in text, kind=='PJ')
                self.assertEqual('Act de identitate: CI' in text, kind=='PF')
                self.assertNotIn('Contactul responsabilului cu protectia datelor:', text)
                self.assertNotIn('Banca beneficiar:', text)
                self.assertNotIn('{{', text)

    def test_cnp_is_not_required_or_exported_even_from_legacy_template(self):
        args=list(fixture())
        args[0]['cnp']='0000000000000'
        args[3]['beneficiar_cnp']='0000000000000'
        data=generate_contract(*args)
        text='\n'.join(p.text for p in Document(BytesIO(data)).paragraphs)
        self.assertNotIn('0000000000000',text)
        self.assertNotIn('CNP',text)
        self.assertNotIn('beneficiar_cnp',prepare_context(*args))

    def test_single_deviz_offer_reference_is_used_throughout_contract(self):
        args=list(fixture())
        args[3].update(nr_oferta='OF-42',data_oferta='2026-10-29',nr_deviz='',data_deviz='')
        context=prepare_context(*args)
        self.assertEqual(context['nr_deviz'],'OF-42')
        self.assertEqual(context['data_deviz'],'29.10.2026')
        template=Document(ic.TEMPLATE)
        template.add_paragraph('Devizul tehnico-economic nr. {{ nr_deviz }} / {{ data_deviz }} este anexat.')
        template.add_paragraph('Contractul este insotit de devizul tehnico-economic.')
        template.save(ic.TEMPLATE)
        text='\n'.join(p.text for p in Document(BytesIO(generate_contract(*args))).paragraphs)
        self.assertIn('Devizul-oferta nr. OF-42 / 29.10.2026',text)
        self.assertIn('insotit de devizul-oferta',text)
        args[3].update(nr_deviz='DEV-9',data_deviz='2026-10-30')
        context=prepare_context(*args)
        self.assertEqual(context['nr_deviz'],'OF-42')
        self.assertEqual(context['data_deviz'],'29.10.2026')
        args[3]['data_deviz']=''
        self.assertEqual(prepare_context(*args)['data_deviz'],'29.10.2026')
        args[3].update(nr_deviz='',data_deviz='',data_oferta='')
        with self.assertRaisesRegex(ContractDataError,'data_oferta'):
            prepare_context(*args)

    def test_estimate_only_legacy_draft_recovers_one_complete_pair(self):
        args=list(fixture())
        args[3].update(nr_oferta='',data_oferta='',nr_deviz='LEGACY-1',data_deviz='2026-10-28')
        context=prepare_context(*args)
        self.assertEqual(context['nr_oferta'],context['nr_deviz'])
        self.assertEqual(context['nr_oferta'],'LEGACY-1')
        self.assertEqual(context['data_oferta'],context['data_deviz'])
        args[3]['nr_oferta']='NEW-1'
        with self.assertRaisesRegex(ContractDataError,'data_oferta'):
            prepare_context(*args)

    def test_durations_use_defaults_and_reject_an_impossible_total(self):
        args=list(fixture())
        for field in ic.deadlines.STAGE_DEFAULTS:args[3].pop(field)
        ctx=prepare_context(*args)
        self.assertEqual(ctx['durata_proiectare_zile'],'10')
        args[3]['durata_proiectare_zile']=7
        self.assertEqual(prepare_context(*args)['durata_proiectare_zile'],'7')
        args[3]['durata_contract_zile']=5
        with self.assertRaisesRegex(ValueError,'nu se incadreaza'):prepare_context(*args)
        args[3]['durata_contract_zile']=90
        for invalid in (0,-1,1.5,'NaN'):
            args[3]['durata_verificare_zile']=invalid
            with self.assertRaises(ValueError):prepare_context(*args)

    def test_legacy_stage_texts_accept_new_durations(self):
        template=Document(ic.TEMPLATE)
        template.add_paragraph('- durata receptiei tehnice a instalatiei de utilizare a gazelor naturale este de 1 zi lucratoare;')
        template.save(ic.TEMPLATE)
        args=list(fixture());args[3]['durata_receptie_zile']=3
        text='\n'.join(p.text for p in Document(BytesIO(generate_contract(*args))).paragraphs)
        self.assertIn('este de 3 zile lucratoare',text)

    def test_common_texts_have_defaults(self):
        args=list(fixture())
        for field in ('descriere_lucrare','defalcare_avize','documente_detectoare_beneficiar'):
            args[3][field]=''
        args[1]['tip_lucrare']='Instalatie de utilizare noua'
        context=prepare_context(*args)
        self.assertEqual(context['descriere_lucrare'],args[1]['tip_lucrare'])
        self.assertEqual(context['defalcare_avize'],'Nu sunt incluse avize in pret.')
        self.assertEqual(context['documente_detectoare_beneficiar'],'Nu este cazul.')

    def test_missing_licence_or_gdpr_blocks_generation(self):
        for key in ('autorizatie_executie_numar', 'gdpr_pastrare_acte', 'gdpr_transferuri'):
            args=list(fixture());args[2][key]=''
            with self.subTest(key=key), self.assertRaisesRegex(ContractDataError, key):
                generate_contract(*args)

    def test_other_clients_work_is_rejected(self):
        args=list(fixture());args[1]['client_id']=99
        with self.assertRaisesRegex(ContractDataError, 'nu apartine'):
            generate_contract(*args)

    def test_total_must_match_work(self):
        args=list(fixture());args[1]['valoare_contractata']=3000
        with self.assertRaisesRegex(ContractDataError, 'Defalcarea'):
            generate_contract(*args)

    def test_installments_reconcile_to_cent(self):
        args=list(fixture());args[1]['valoare_contractata']='2800.03'
        args[3].update(valoare_proiectare='500.03', avans_procent='33.33')
        c=prepare_context(*args)
        self.assertEqual(c['avans_suma'], '933,25')
        self.assertEqual(c['executie_suma'], '1.586,78')
        self.assertEqual(c['pif_suma'], '280,00')

    def test_invalid_dates_and_nonfinite_numbers_are_rejected(self):
        for key,value in [('data_oferta','2026-02-30'),('valoare_avize','NaN'),('avans_procent',91)]:
            args=list(fixture());args[3][key]=value
            with self.subTest(key=key), self.assertRaises(ContractDataError):
                generate_contract(*args)


class ContractDeadlines(unittest.TestCase):
    def test_calendar_skips_weekends_fixed_and_movable_holidays(self):
        from datetime import date
        d=ic.deadlines
        self.assertEqual(d.after_workdays('2026-11-27',2),date(2026,12,3))
        self.assertEqual(d.execution_finish('2026-11-27',2),date(2026,12,2))
        self.assertEqual(d.after_workdays('2026-04-09',1),date(2026,4,14))
        self.assertEqual(d.after_workdays('2026-12-24',1),date(2026,12,28))
        self.assertEqual(d.orthodox_easter(2027),date(2027,5,2))

    def test_report_uses_actual_signature_triggers_and_current_schedule(self):
        from datetime import date
        d=ic.deadlines;ctx={'durata_contract_zile':90,**d.STAGE_DEFAULTS}
        state={'facts':{'contract_emis':{'date':'2026-10-01'}},'exceptions':{}}
        self.assertEqual(d.report(ctx,state),[])
        state['facts'].update(contract_semnat={'date':'2026-11-16'},documente_complete={'date':'2026-11-18'},notificare_primita={'date':'2026-11-20'})
        rows=d.report(ctx,state,today=date(2026,12,9))
        self.assertEqual(rows[0]['Termen'],'2027-02-14')
        self.assertEqual(rows[1]['Termen'],'2026-12-08')
        self.assertEqual(rows[1]['Stare'],'Depasit')
        state['facts']['executie_programata']={'date':'2026-11-20','scheduled_for':'2027-02-20'}
        self.assertTrue(d.report(ctx,state,today=date(2026,12,9))[-1]['Depaseste durata contractului'])
        state['facts']['executie_programata']['scheduled_for']='2026-12-10'
        self.assertFalse(d.report(ctx,state,today=date(2026,12,9))[-1]['Depaseste durata contractului'])


if __name__=='__main__':
    unittest.main()
