"""Report filter regressions using the real Streamlit rendering code."""
import unittest
from streamlit.testing.v1 import AppTest

APP = '''
import pandas as pd
import streamlit as st
from unittest.mock import patch
from tabs import tab_lucrari
amounts = st.session_state['amounts']
clients = pd.DataFrame([{'id': 1, 'nume': 'Test A'}, {'id': 2, 'nume': 'Test B'}])
works = pd.DataFrame([{'id': i + 1, 'client_id': i % 2 + 1,
                      'tip_lucrare': 'Instalatie termica noua',
                      'valoare_contractata': amount, 'status': 'OFERTAT',
                      'echipa': '', 'descriere': 'Test'} for i, amount in enumerate(amounts)])
with patch.object(tab_lucrari.db, 'lista_clienti', return_value=clients), \\
     patch.object(tab_lucrari.db, 'lista_lucrari', return_value=works):
    tab_lucrari.show('admin')
'''


class LucrariReportUI(unittest.TestCase):
    def render(self, amounts):
        app = AppTest.from_string(APP, default_timeout=10)
        app.session_state['amounts'] = amounts
        app.run()
        self.assertFalse(app.exception)
        return app

    def assert_count(self, app, count):
        self.assertTrue(any(f'{count} lucrări găsite' in x.value for x in app.markdown))

    def test_single_work_has_no_invalid_slider(self):
        app = self.render([1000])
        self.assert_count(app, 1)
        self.assertEqual(len(app.slider), 0)
        self.assertIn('1,000.00', app.success[0].value)

    def test_equal_values_keep_client_filter_and_reset(self):
        app = self.render([1000, 1000])
        self.assert_count(app, 2)
        self.assertEqual(len(app.slider), 0)
        app.selectbox[0].select('Test A').run()
        self.assertFalse(app.exception)
        self.assert_count(app, 1)
        next(b for b in app.button if b.label == 'Reset').click().run()
        self.assertFalse(app.exception)
        self.assert_count(app, 2)

    def test_different_values_can_be_filtered(self):
        app = self.render([1000, 2000, 3000])
        self.assert_count(app, 3)
        app.slider[0].set_range(1000.0, 2000.0).run()
        self.assertFalse(app.exception)
        self.assert_count(app, 2)
        self.assertIn('3,000.00', app.success[0].value)

    def test_decimal_amounts_are_not_truncated(self):
        app = self.render([1000.25, 1000.50, 1000.75])
        self.assert_count(app, 3)
        app.slider[0].set_range(1000.50, 1000.75).run()
        self.assertFalse(app.exception)
        self.assert_count(app, 2)
        self.assertIn('2,001.25', app.success[0].value)

    def test_zero_and_missing_values_do_not_crash(self):
        for amounts in [[0], [0, 0], [None], [float('nan'), None]]:
            with self.subTest(amounts=amounts):
                app = self.render(amounts)
                self.assert_count(app, len(amounts))

    def test_empty_report(self):
        app = self.render([])
        self.assertTrue(any('Nu există lucrări.' in x.value for x in app.info))


if __name__ == '__main__':
    unittest.main(verbosity=2)
