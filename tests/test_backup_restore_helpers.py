"""Guards and comparison logic; these checks do not replace a real restore."""
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch
from tools import backup_restore_test as backup


class BackupHelpers(unittest.TestCase):
    def test_restore_refuses_source_and_arbitrary_existing_names(self):
        for name in [backup.DB_NAME, 'postgres', 'ecoloptim_restore_user_test', 'existing_db']:
            with self.subTest(name=name), self.assertRaises(backup.BackupTestError):
                backup.restore_arguments('pg_restore', name, Path('copy.dump'))

    def test_restore_uses_generated_target_and_single_transaction(self):
        target = 'ecoloptim_restore_20261021230000_ab12cd34_test'
        args = backup.restore_arguments('pg_restore', target, Path('copy.dump'))
        self.assertEqual(args[args.index('--dbname') + 1], target)
        self.assertIn('--single-transaction', args)
        self.assertIn('--exit-on-error', args)
        self.assertNotIn(backup.DB_NAME, args)

    def test_same_rows_match_regardless_of_database_row_order(self):
        self.assertEqual(backup.rows_digest(['row B', 'row A']), backup.rows_digest(['row A', 'row B']))

    def test_same_count_with_changed_data_is_detected(self):
        source = {'tables': {'lucrari': {'rows': 1, 'sha256': backup.rows_digest(['A'])}}}
        changed = {'tables': {'lucrari': {'rows': 1, 'sha256': backup.rows_digest(['B'])}}}
        with self.assertRaises(backup.BackupTestError):
            backup.compare_fingerprints(source, changed)
        backup.compare_fingerprints(source, source)

    def test_hash_framing_distinguishes_different_rows(self):
        self.assertNotEqual(backup.rows_digest(['ab', 'c']), backup.rows_digest(['a', 'bc']))
        self.assertNotEqual(backup.rows_digest(['a']), backup.rows_digest(['a', 'a']))

    def test_connection_environment_overrides_ambient_database_options(self):
        with patch.dict(os.environ, {'PGDATABASE': 'other_database', 'PGSERVICE': 'remote',
                                     'PGOPTIONS': '-c search_path=wrong'}):
            env = backup.cli_environment({'host': '127.0.0.1', 'user': 'test_app', 'password': 'secret'})
        self.assertNotIn('PGDATABASE', env)
        self.assertNotIn('PGSERVICE', env)
        self.assertNotIn('PGOPTIONS', env)
        self.assertEqual(env['PGHOST'], '127.0.0.1')
        self.assertEqual(env['PGPASSWORD'], 'secret')

    def test_local_config_cannot_override_host_via_url_query(self):
        with patch.object(backup, 'load_config', return_value={
                'DATABASE_URL': 'postgresql://test:secret@127.0.0.1/ecoloptim_pg_test?host=remote.example'}):
            with self.assertRaises(backup.BackupTestError):
                backup.source_parameters()

    def test_failed_pg_restore_cannot_be_reported_as_success(self):
        failure = subprocess.CompletedProcess(['pg_restore'], 1, stdout='', stderr='error')
        with patch.object(backup.subprocess, 'run', return_value=failure), self.assertRaises(backup.BackupTestError):
            backup.run_tool(['pg_restore'], {}, 'Restaurare')


if __name__ == '__main__':
    unittest.main(verbosity=2)
