from unittest import TestCase, skip

import beets.ui
import beets.library
from beets.library import Item, get_query
from beets.mediafile import MediaFile
from beets import plugins

from helper import TestHelper, captureLog, controlStdin
from beetsplug import check

import logging

class MockChecker(check.IntegrityChecker):
    @classmethod
    def install(cls):
        check.IntegrityChecker._all_available = [cls()]

    @classmethod
    def restore(cls):
        if hasattr(check.IntegrityChecker, '_all_available'):
            delattr(check.IntegrityChecker, '_all_available')

    def run(self, item):
        if 'truncated' in item.path:
            raise check.IntegrityError('file is corrupt')


class ImportTest(TestHelper, TestCase):

    def setUp(self):
        super(ImportTest, self).setUp()
        self.setupBeets()
        self.setupImportDir(['ok.mp3'])
        check.IntegrityChecker._all_available = []

    def tearDown(self):
        super(ImportTest, self).tearDown()
        MockChecker.restore()

    def test_add_album_checksum(self):
        with self.mockAutotag():
            beets.ui._raw_main(['import', self.import_dir])
        item = self.lib.items().get()
        self.assertIn('checksum', item)
        self.assertEqual(item.title, 'ok tag')
        check.verify(item)

    def test_add_singleton_checksum(self):
        with self.mockAutotag():
            beets.ui._raw_main(['import', '--singletons', self.import_dir])
        item = self.lib.items().get()
        self.assertIn('checksum', item)
        check.verify(item)

    def test_add_album_checksum_without_autotag(self):
        with self.mockAutotag():
            beets.ui._raw_main(['import', '--noautotag', self.import_dir])
        item = self.lib.items().get()
        self.assertIn('checksum', item)
        self.assertEqual(item.title, 'ok')
        check.verify(item)

    def test_add_singleton_checksum_without_autotag(self):
        with self.mockAutotag():
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
        self.modifyFile(item.path, 'changed')

        with self.mockAutotag():
            beets.ui._raw_main(['import', self.libdir])

        item = self.lib.items([item.path]).get()
        self.assertEqual(item['checksum'], orig_checksum)

    def test_skip_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(['ok.mp3', 'truncated.mp3'])

        with self.mockAutotag(), controlStdin('y'):
            beets.ui._raw_main(['import', self.import_dir])

        self.assertEqual(len(self.lib.items()), 0)

    def test_add_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(['ok.mp3', 'truncated.mp3'])

        with self.mockAutotag(), controlStdin('n'):
            beets.ui._raw_main(['import', self.import_dir])

        self.assertEqual(len(self.lib.items()), 2)


class WriteTest(TestHelper, TestCase):

    def setUp(self):
        super(WriteTest, self).setUp()
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
