"""Local test configurations must retain isolated database selection."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from tools import local_pg_config as config

class LocalPGConfig(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'config.json'
        p=patch.object(config,'CONFIG',self.path)
        p.start()
        self.addCleanup(p.stop)

    def value(self,database='ecoloptim_iugn_test',host='127.0.0.1'):
        return {'DATABASE_URL':f'postgresql://test:demo@{host}:5432/{database}',
                'TEST_DATABASE':database,'UPLOAD_DIR':'uploads_test'}

    def test_dedicated_database_survives_reload(self):
        value=self.value()
        config.write_config(value)
        self.assertEqual(config.load_config(),value)

    def test_legacy_configuration_still_loads(self):
        value=self.value('ecoloptim_pg_test')
        del value['TEST_DATABASE']
        config.write_config(value)
        self.assertEqual(config.load_config(),value)

    def test_database_mismatch_and_remote_host_are_rejected(self):
        for value in [dict(self.value(),TEST_DATABASE='ecoloptim_other_test'),
                      self.value(host='remote.example.invalid')]:
            self.path.write_text(json.dumps(value))
            with self.assertRaises(ValueError):config.load_config()

    def test_production_names_and_sql_identifiers_are_rejected(self):
        for name in ['ecoloptim_prod','postgres','ecoloptim_bad_test;DROP','ecoloptim_'+'a'*60+'_test']:
            with self.subTest(name=name),self.assertRaises(ValueError):
                config.validate_test_database(name)

    def test_existing_config_is_not_overwritten(self):
        first=self.value()
        config.write_config(first)
        with self.assertRaises(FileExistsError):config.write_config(self.value('ecoloptim_other_test'))
        self.assertEqual(config.load_config(),first)
