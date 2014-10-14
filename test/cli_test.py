import os
import shutil
from unittest import TestCase

import beets.ui
import beets.library
from beets.library import Item

from helper import TestHelper, captureLog, \
    captureStdout, controlStdin, MockChecker
from beetsplug import check


class TestBase(TestHelper, TestCase):

    def setUp(self):
        super(TestBase, self).setUp()
        self.setupBeets()

    def tearDown(self):
        super(TestBase, self).tearDown()


class CheckAddTest(TestBase, TestCase):
    """beet check --add"""

    def test_add_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        del item['checksum']
        item.store()

        beets.ui._raw_main(['check', '-a'])

        item.load()
        self.assertIn('checksum', item)

    def test_dont_add_existing_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        check.set_checksum(item)
        orig_checksum = item['checksum']

        self.modifyFile(item.path)
        beets.ui._raw_main(['check', '-a'])

        item.load()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_add_shows_integrity_warning(self):
        MockChecker.install()
        item = self.addIntegrityFailFixture(checksum=False)

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-a'])

        self.assertIn('WARNING file is corrupt: {}'.format(item.path),
                      '\n'.join(logs))


class CheckTest(TestBase, TestCase):
    """beet check"""

    def test_check_success(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(['check'])
        self.assertEqual('All checksums successfully verified',
                         stdout.getvalue().split('\n')[-2])

    def test_check_failed_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        try:
            with captureLog('beets.check') as logs:
                beets.ui._raw_main(['check'])
        except SystemExit:
            pass

        self.assertIn('FAILED: {}'.format(item.path), '\n'.join(logs))

    def test_not_found_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        item.path = '/doesnotexist'
        item.store()

        try:
            with captureLog('beets.check') as logs:
                beets.ui._raw_main(['check'])
        except SystemExit:
            pass

        self.assertIn("OK:", '\n'.join(logs))
        self.assertIn("ERROR [Errno 2] No such file or directory: '{}'"
                      .format(item.path), '\n'.join(logs))

    def test_check_failed_exit_code(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        with self.assertRaises(SystemExit) as exit:
            beets.ui._raw_main(['check'])
        self.assertEqual(exit.exception.code, 15)


class CheckIntegrityTest(TestBase, TestCase):
    """beet check"""

    def test_integrity_warning(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])

        self.assertIn('WARNING file is corrupt', '\n'.join(logs))

    def test_check_without_integrity_config(self):
        self.config['check']['integrity'] = False
        MockChecker.install()
        self.addIntegrityFailFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])

        self.assertNotIn('WARNING file is corrupt', '\n'.join(logs))

    def test_only_integrity(self):
        MockChecker.install()
        self.addIntegrityFailFixture(checksum=False)
        self.addIntegrityFailFixture(checksum='not a real checksum')
        self.addCorruptedFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-i'])

        self.assertIn('WARNING file is corrupt', '\n'.join(logs))
        self.assertNotIn('FAILED', '\n'.join(logs))

    def test_no_integrity_checkers_warning(self):
        MockChecker.installNone()
        self.addIntegrityFailFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])

        self.assertIn('No integrity checkers found.', '\n'.join(logs))

    def test_only_integrity_without_checkers_error(self):
        MockChecker.installNone()
        self.addIntegrityFailFixture()

        with self.assertRaises(SystemExit) as exit:
            with captureLog() as logs:
                beets.ui._raw_main(['check', '-i'])

        self.assertIn('No integrity checkers found.', '\n'.join(logs))
        self.assertEqual(exit.exception.code, 2)


class CheckUpdateTest(TestBase, TestCase):
    """beet check --update"""

    def test_force_all_update(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        beets.ui._raw_main(['check', '--force', '--update'])

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

    def test_update_all_confirmation(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        with captureStdout() as stdout, controlStdin(u'y'):
            beets.ui._raw_main(['check', '--update'])

        self.assertIn('Do you want to overwrite all checksums',
                      stdout.getvalue())

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

    def test_update_all_confirmation_no(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        with controlStdin(u'n'):
            beets.ui._raw_main(['check', '--update'])

        item.load()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_update_nonexistent(self):
        item = Item(path='/doesnotexist')
        self.lib.add(item)

        with captureLog() as logs:
            beets.ui._raw_main(['check', '--update', '--force'])

        self.assertIn("ERROR [Errno 2] No such file or directory: '{}'"
                      .format(item.path), '\n'.join(logs))


class CheckExportTest(TestBase, TestCase):
    """beet check --export"""

    def test_export(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--export'])

        item = self.lib.items().get()
        self.assertIn('{} *{}\n'.format(item.checksum, item.path),
                      stdout.getvalue())


class IntegrityCheckTest(TestHelper, TestCase):

    def setUp(self):
        super(IntegrityCheckTest, self).setUp()
        self.setupBeets()
        self.setupFixtureLibrary()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super(IntegrityCheckTest, self).tearDown()

    def test_mp3_integrity(self):
        item = self.lib.items(['path::truncated.mp3']).get()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])
        self.assertIn('WARNING It seems that file is '
                      'truncated or there is garbage at the '
                      'end of the file: {}'.format(item.path), logs)

    def test_flac_integrity(self):
        item = self.lib.items('truncated.flac').get()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])
        self.assertIn(
            'WARNING while decoding data: {}'.format(item.path), logs)

    def test_ogg_vorbis_integrity(self):
        item = self.lib.items('truncated.ogg').get()

        with captureLog() as logs:
            beets.ui._raw_main(['check'])
        self.assertIn('WARNING serialno 1038587646 missing *** eos: {}'
                      .format(item.path), logs)


class FixIntegrityTest(TestHelper, TestCase):

    def setUp(self):
        super(FixIntegrityTest, self).setUp()
        self.setupBeets()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super(FixIntegrityTest, self).tearDown()

    def test_fix_integrity(self):
        item = self.addIntegrityFailFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-i'])
        self.assertIn('WARNING It seems that file is truncated',
                      '\n'.join(logs))

        with controlStdin(u'y'), captureLog() as logs:
            beets.ui._raw_main(['check', '--fix'])
        self.assertIn(item.path, '\n'.join(logs))
        self.assertIn('FIXED: {}'.format(item.path), '\n'.join(logs))

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-i'])
        self.assertNotIn('WARNING It seems that file is truncated',
                         '\n'.join(logs))

    def test_fix_without_confirmation(self):
        item = self.addIntegrityFailFixture()

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-i'])
        self.assertIn('WARNING It seems that file is truncated',
                      '\n'.join(logs))

        with captureLog() as logs:
            beets.ui._raw_main(['check', '--fix', '--force'])
        self.assertIn(item.path, '\n'.join(logs))

        with captureLog() as logs:
            beets.ui._raw_main(['check', '-i'])
        self.assertNotIn('WARNING It seems that file is truncated',
                         '\n'.join(logs))

    def test_update_checksum(self):
        item = self.addIntegrityFailFixture()
        old_checksum = item['checksum']
        beets.ui._raw_main(['check', '--fix', '--force'])

        item.load()
        check.verify_checksum(item)
        self.assertNotEqual(old_checksum, item['checksum'])

    def test_dont_fix_with_wrong_checksum(self):
        item = self.addIntegrityFailFixture()
        item['checksum'] = 'this is wrong'
        item.store()

        with captureLog() as logs:
            beets.ui._raw_main(['check', '--fix', '--force'])
        self.assertIn('FAILED checksum', '\n'.join(logs))

        item.load()
        self.assertEqual(item['checksum'], 'this is wrong')

    def test_nothing_to_fix(self):
        self.addItemFixture('ok.ogg')
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--fix', '--force'])
        self.assertIn('No MP3 files to fix', stdout.getvalue())

    def test_do_not_fix(self):
        item = self.addIntegrityFailFixture()
        with controlStdin(u'n'):
            beets.ui._raw_main(['check', '--fix'])
        check.verify_checksum(item)

    def test_keep_backup(self):
        item = self.addIntegrityFailFixture()
        old_checksum = item['checksum']

        with controlStdin(u'y'), captureStdout() as stdout:
            beets.ui._raw_main(['check', '--fix'])
        self.assertIn('Backup files will be created', stdout.getvalue())

        backup = Item(path=item.path + '.bak', checksum=old_checksum)
        self.assertTrue(os.path.isfile(backup.path))
        check.verify_checksum(backup)

    def test_dont_keep_backup_flag(self):
        item = self.addIntegrityFailFixture()

        with controlStdin(u'y'), captureStdout() as stdout:
            beets.ui._raw_main(['check', '--fix', '--no-backup'])
        self.assertIn('No backup files will be created', stdout.getvalue())

        backup_path = item.path + '.bak'
        self.assertFalse(os.path.isfile(backup_path))

    def test_dont_keep_backup_config(self):
        item = self.addIntegrityFailFixture()
        self.config['check']['backup'] = False

        beets.ui._raw_main(['check', '--fix', '--force'])
        backup_path = item.path + '.bak'
        self.assertFalse(os.path.isfile(backup_path))


class ToolListTest(TestHelper, TestCase):

    def setUp(self):
        super(ToolListTest, self).setUp()
        self.enableIntegrityCheckers()
        self.setupBeets()
        self.orig_path = os.environ['PATH']
        os.environ['PATH'] = self.temp_dir

    def tearDown(self):
        super(ToolListTest, self).tearDown()
        os.environ['PATH'] = self.orig_path

    def test_list(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--list-tools'])
        self.assertIn('mp3val', stdout.getvalue())
        self.assertIn('flac', stdout.getvalue())
        self.assertIn('oggz-validate', stdout.getvalue())

    def test_found_mp3val(self):
        shutil.copy('/bin/echo', os.path.join(self.temp_dir, 'mp3val'))
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--list-tools'])
        self.assertRegexpMatches(stdout.getvalue(), r'mp3val *found')

    def test_oggz_validate_not_found(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--list-tools'])
        self.assertRegexpMatches(stdout.getvalue(),
                                 r'oggz-validate *not found')
