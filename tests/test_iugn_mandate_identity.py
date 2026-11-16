import unittest
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from docx import Document
from utils import iugn_mandate as mandate

class MandateIdentityTests(unittest.TestCase):
    def test_complete_identities_and_legacy_templates(self):
        for kind in ('PF','PJ'):
            with self.subTest(kind=kind), TemporaryDirectory() as tmp:
                source={key:'Exemplu' for key in (
                    'beneficiar_firma','beneficiar_nume','beneficiar_regcom','beneficiar_cui',
                    'beneficiar_ci_serie','beneficiar_ci_nr','beneficiar_ci_emitent','beneficiar_ci_data',
                    'beneficiar_reprezentant_calitate','executant_denumire','executant_regcom',
                    'executant_cui','executant_reprezentant','executant_reprezentant_calitate',
                    'executant_telefon','executant_email','nr_contract','data_contract')}
                source.update(beneficiar_tip=kind,beneficiar_iban='RO00TESTCLIENT',
                    beneficiar_banca='Banca client',beneficiar_localitate='Localitate client',
                    executant_iban='RO00TESTFIRMA',executant_banca='Banca firma',
                    executant_localitate='Localitate firma',beneficiar_cnp='excluded',unrelated='excluded')
                values=mandate.context(source,'MDT-TEST')
                self.assertNotIn('beneficiar_cnp',values)
                self.assertNotIn('unrelated',values)
                d=Document()
                d.add_paragraph("{% if beneficiar_tip == 'PJ' %}{{ beneficiar_firma }} {{ beneficiar_iban }} {{ beneficiar_banca }}{% else %}{{ beneficiar_nume }} CI {{ beneficiar_ci_serie }} {{ beneficiar_ci_nr }}{% endif %}")
                d.add_paragraph('{{ beneficiar_adresa }} {{ executant_adresa }} {{ executant_iban }} {{ executant_banca }} {{ executant_reprezentant }} {{ mandant_identificare }} {{ mandatar_identificare }}')
                template=Path(tmp)/'mandate.docx';d.save(template)
                with patch.object(mandate,'TEMPLATE',template):
                    text='\n'.join(p.text for p in Document(BytesIO(mandate.generate(values))).paragraphs)
                for expected in ('Localitate client','Localitate firma','RO00TESTFIRMA Banca firma'):
                    self.assertIn(expected,text)
                self.assertEqual('RO00TESTCLIENT Banca client' in text,kind=='PJ')
                self.assertIn('mandant_identificare',values)
                self.assertIn('mandatar_identificare',values)
