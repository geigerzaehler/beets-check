from unittest import TestCase

import beets.ui
import beets.library
from beets.library import Item
from beets.mediafile import MediaFile

from helper import TestHelper, captureLog, captureStdout, controlStdin
from beetsplug import check


class CheckTest(TestHelper, TestCase):

    def setUp(self):
        super(CheckTest, self).setUp()
        self.setupBeets()
        self.setupFixtureLibrary()

    def test_add_checksums(self):
        item = self.lib.items().get()
        del item['checksum']
        item.store()

        beets.ui._raw_main(['check', '-a'])

        item.load()
        self.assertIn('checksum', item)

    def test_dont_add_existing_checksums(self):
        item = self.lib.items().get()
        check.set_checksum(item)
        orig_checksum = item['checksum']

        self.modifyFile(item.path)
        beets.ui._raw_main(['check', '-a'])

        item.load()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_check_success(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(['check'])
        self.assertEqual('All checksums successfully verified',
                         stdout.getvalue().split('\n')[-2])

    def test_check_failed_error_log(self):
        item = self.lib.items().get()
        self.modifyFile(item.path)

        try:
            with captureLog('beets.check') as logs:
                beets.ui._raw_main(['check'])
        except SystemExit:
            pass

        self.assertIn('{}: FAILED'.format(item.path), '\n'.join(logs))

    def test_check_failed_exit_code(self):
        item = self.lib.items().get()
        self.modifyFile(item.path)

        with self.assertRaises(SystemExit) as exit:
            beets.ui._raw_main(['check'])
        self.assertEqual(exit.exception.code, 15)

    def test_force_all_update(self):
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        beets.ui._raw_main(['check', '--force', '--update'])

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

    def test_update_all_confirmation(self):
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        with captureStdout() as stdout, controlStdin(u'y') as stdin:
            beets.ui._raw_main(['check', '--update'])

        self.assertIn('Do you want to overwrite all checksums', stdout.getvalue())

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

    def test_update_all_confirmation_no(self):
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        self.modifyFile(item.path)

        with controlStdin(u'n') as stdin:
            beets.ui._raw_main(['check', '--update'])

        item.load()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_export(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(['check', '--export'])

        item = self.lib.items().get()
        self.assertIn('{} *{}\n'.format(item.checksum, item.path),
                      stdout.getvalue())
