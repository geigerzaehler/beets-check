from unittest import TestCase, skip

import beets.ui
import beets.library
from beets.library import Item
from beets.mediafile import MediaFile

from helper import captureLog, TestHelper
from beetsplug import check

import logging

class ImportTest(TestHelper, TestCase):

    def setUp(self):
        self.setupBeets()
        self.setupImportDir()

    def test_add_album_checksum(self):
        beets.ui._raw_main(['import', '--noautotag', self.import_dir])
        item = self.lib.items().get()
        self.assertIn('checksum', item)
        check.verify(item)

    def test_add_singleton_checksum(self):
        beets.ui._raw_main(['import', '--singletons',
                            '--noautotag', self.import_dir])
        item = self.lib.items().get()
        self.assertIn('checksum', item)
        check.verify(item)

    def test_reimport_does_not_overwrite_checksum(self):
        self.setupFixtureLibrary()

        item = self.lib.items().get()
        orig_checksum = item['checksum']
        check.verify(item)
        self.modifyFile(item.path)

        beets.ui._raw_main(['import', '--noautotag', self.libdir])
        item = self.lib.items().get()
        self.assertEqual(item['checksum'], orig_checksum)


class WriteTest(TestHelper, TestCase):

    def setUp(self):
        self.setupBeets()
        self.setupFixtureLibrary()

    def test_log_error_for_invalid_checksum(self):
        item = self.lib.items().get()
        check.verify(item)
        self.modifyFile(item.path)

        with captureLog() as logs:
            beets.ui._raw_main(['write'])
        self.assertRegexpMatches('\n'.join(logs),
                r'could not write .*: checksum did not match value in library')

    def test_abort_write_when_invalid_checksum(self):
        item = self.lib.items().get()
        check.verify(item)
        self.modifyFile(item.path, title='other title')

        item['title'] = 'newtitle'
        item.store()
        beets.ui._raw_main(['write'])

        mediafile = MediaFile(item.path)
        self.assertNotEqual(mediafile.title, 'newtitle')

    @skip('not yet available in beets')
    def test_update_checksum(self):
        item = self.lib.items().get()
        orig_checksum = item['checksum']
        check.verify(item)

        item['title'] = 'newtitle'
        item.store()
        beets.ui._raw_main(['write'])

        item.load()
        self.assertNotEqual(item['checksum'], orig_checksum)
        check.verify(item)

        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.title, 'newtitle')
