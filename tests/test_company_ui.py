from datetime import date, timedelta
from pathlib import Path
import tempfile
import unittest
from streamlit.testing.v1 import AppTest
from db import company, db, permissions

APP='''
from db import db, permissions
from tabs.tab_date_generale import show, render_authorization_alerts
permissions.bind_actor('admin', permissions.password_marker(db.get_utilizator('admin')))
render_authorization_alerts()
show('admin')
'''


class CompanyUI(unittest.TestCase):
    def setUp(self):
        permissions.clear_actor()
        self.tmp=tempfile.TemporaryDirectory()
        self.old=db.DB_PATH,db.DATABASE_URL
        db.DB_PATH,db.DATABASE_URL=str(Path(self.tmp.name)/'company.db'),''
        db.init_db()
        db.seteaza_must_change_password('admin',0)

    def tearDown(self):
        permissions.clear_actor()
        db.DB_PATH,db.DATABASE_URL=self.old
        self.tmp.cleanup()

    def open(self):
        app=AppTest.from_string(APP,default_timeout=10).run()
        self.assertFalse(app.exception)
        return app

    def test_form_saves_expiry_and_live_alert_is_visible(self):
        app=self.open()
        next(x for x in app.text_input if x.label=='Tip autorizatie proiectare').set_value('PDIB')
        next(x for x in app.text_input if x.label=='Numar autorizatie proiectare').set_value('TEST-2026')
        next(x for x in app.date_input if x.label=='Data expirarii proiectare').set_value(date.today()+timedelta(days=20))
        next(x for x in app.button if x.label=='Salveaza datele generale').click().run()
        self.assertFalse(app.exception)
        self.assertEqual(company.get()['values']['autorizatie_proiectare_numar'],'TEST-2026')
        self.assertTrue(any('expira in 20 zile' in x.value for x in app.warning))
        self.assertTrue(any('salvate' in x.value for x in app.success))

    def test_two_admin_sessions_do_not_silently_overwrite(self):
        a,b=self.open(),self.open()
        next(x for x in a.text_input if x.label=='E-mail firma si cereri GDPR').set_value('first@example.invalid')
        next(x for x in a.button if x.label=='Salveaza datele generale').click().run()
        next(x for x in b.text_input if x.label=='E-mail firma si cereri GDPR').set_value('second@example.invalid')
        next(x for x in b.button if x.label=='Salveaza datele generale').click().run()
        self.assertFalse(b.exception)
        self.assertTrue(any('alta sesiune' in x.value for x in b.error))
        self.assertEqual(company.get()['values']['executant_email'],'first@example.invalid')
