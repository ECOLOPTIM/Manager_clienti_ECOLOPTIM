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
                 durata_contract_zile=90, avans_procent=50,
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
        for key,value in [('data_deviz','2026-02-30'),('valoare_avize','NaN'),('avans_procent',91)]:
            args=list(fixture());args[3][key]=value
            with self.subTest(key=key), self.assertRaises(ContractDataError):
                generate_contract(*args)


if __name__=='__main__':
    unittest.main()
