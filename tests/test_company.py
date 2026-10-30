from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest

from db import company, db, permissions


class CompanyCases:
    def test_company_persists_and_migration_keeps_values(self):
        before=company.get()
        values=dict(before['values'], autorizatie_proiectare_tip='PDIB',
                    autorizatie_proiectare_numar='TEST-123',
                    autorizatie_proiectare_expirare='2027-05-31')
        rev=company.save(values,expected_revision=before['revision'])
        db.init_db()
        after=company.get()
        self.assertEqual(after['revision'],rev)
        self.assertEqual(after['values'],values)
        with db._connect() as conn:
            row=db._execute(conn.cursor(),'SELECT payload FROM firma_config_istoric WHERE revision=?',(rev,)).fetchone()
        self.assertIsNotNone(row)

    def test_company_stale_save_does_not_replace_first_save(self):
        a=company.get()
        company.save(dict(a['values'], executant_email='first@example.invalid'),expected_revision=a['revision'])
        with self.assertRaises(company.SettingsConflict):
            company.save(dict(a['values'], executant_email='second@example.invalid'),expected_revision=a['revision'])
        self.assertEqual(company.get()['values']['executant_email'],'first@example.invalid')

    def test_company_live_role_is_required_for_every_save(self):
        permissions.clear_actor()
        if not db.get_utilizator('company_office'):
            db.adauga_utilizator('company_office','Company-password-123','birou',must_change_password=0)
        permissions.bind_actor('company_office',permissions.password_marker(db.get_utilizator('company_office')))
        snapshot=company.get()
        try:
            with self.assertRaises(PermissionError):
                company.save(snapshot['values'],expected_revision=snapshot['revision'])
        finally:
            permissions.clear_actor()

    def test_company_rejects_invalid_expiry_without_writing(self):
        before=company.get()
        with self.assertRaises(ValueError):
            company.save(dict(before['values'],autorizatie_executie_expirare='2027-02-30'),
                         expected_revision=before['revision'])
        self.assertEqual(company.get(),before)


class CompanySQLite(CompanyCases,unittest.TestCase):
    def setUp(self):
        permissions.clear_actor()
        self.tmp=tempfile.TemporaryDirectory()
        self.old=db.DB_PATH,db.DATABASE_URL
        db.DB_PATH,db.DATABASE_URL=str(Path(self.tmp.name)/'settings.db'),''
        db.init_db()
        db.seteaza_must_change_password('admin',0)

    def tearDown(self):
        permissions.clear_actor()
        db.DB_PATH,db.DATABASE_URL=self.old
        self.tmp.cleanup()


class CompanyExpiry(unittest.TestCase):
    def test_calendar_month_boundary_not_ninety_days(self):
        self.assertEqual(company.warning_date(date(2027,5,31)),date(2027,2,28))
        self.assertEqual(company.warning_date(date(2028,5,31)),date(2028,2,29))
        self.assertEqual(company.warning_date(date(2027,1,31)),date(2026,10,31))

    def test_before_threshold_threshold_last_day_and_expired(self):
        values={'autorizatie_executie_tip':'EDIB','autorizatie_executie_numar':'123',
                'autorizatie_executie_expirare':'2027-05-31'}
        for day,status in [(date(2027,2,27),'valabila'),(date(2027,2,28),'expira_curand'),
                           (date(2027,5,31),'expira_curand'),(date(2027,6,1),'expirata')]:
            with self.subTest(day=day):
                result=company.authorizations(values,day)[1]
                self.assertEqual(result['status'],status)
        values['autorizatie_executie_expirare']='2028-10-30'
        self.assertEqual(company.authorizations(values,date(2027,5,31))[1]['status'],'valabila')

    def test_no_expiry_is_not_mistaken_for_expired(self):
        self.assertEqual(company.authorizations({})[0]['status'],'necompletata')
        self.assertFalse(company.authorizations({})[0]['complete'])
