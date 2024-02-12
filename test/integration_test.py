import os.path
from test.helper import MockChecker, TestHelper, captureLog, captureStdout, controlStdin
from unittest import TestCase

import beets
import beets.library
import beets.plugins
import beets.ui
from beets.mediafile import MediaFile

from beetsplug.check import IntegrityChecker, verify_checksum


class ImportTest(TestHelper, TestCase):

    def setUp(self):
        super(ImportTest, self).setUp()
        self.setupBeets()
        self.setupImportDir(["ok.mp3"])
        IntegrityChecker._all_available = []

    def tearDown(self):
        super(ImportTest, self).tearDown()
        MockChecker.restore()

    def test_add_album_checksum(self):
        with self.mockAutotag():
            beets.ui._raw_main(["import", self.import_dir])
        item = self.lib.items().get()
        self.assertIn("checksum", item)
        self.assertEqual(item.title, "ok tag")
        verify_checksum(item)

    def test_add_singleton_checksum(self):
        with self.mockAutotag():
            beets.ui._raw_main(["import", "--singletons", self.import_dir])
        item = self.lib.items().get()
        self.assertIn("checksum", item)
        verify_checksum(item)

    def test_add_album_checksum_without_autotag(self):
        with self.mockAutotag():
            beets.ui._raw_main(["import", "--noautotag", self.import_dir])
        item = self.lib.items().get()
        self.assertIn("checksum", item)
        self.assertEqual(item.title, "ok")
        verify_checksum(item)

    def test_add_singleton_checksum_without_autotag(self):
        with self.mockAutotag():
            beets.ui._raw_main(
                ["import", "--singletons", "--noautotag", self.import_dir]
            )
        item = self.lib.items().get()
        self.assertIn("checksum", item)
        verify_checksum(item)

    def test_reimport_does_not_overwrite_checksum(self):
        self.setupFixtureLibrary()

        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        verify_checksum(item)
        self.modifyFile(item.path, "changed")

        with self.mockAutotag():
            beets.ui._raw_main(["import", self.libdir])

        item = self.lib.items([item.path.decode("utf-8")]).get()
        self.assertEqual(item["checksum"], orig_checksum)

    def test_skip_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with self.mockAutotag(), controlStdin(
            " "
        ), captureStdout() as stdout, captureLog() as logs:
            beets.ui._raw_main(["import", self.import_dir])

        self.assertIn("check: Warning: failed to verify integrity", logs)
        self.assertIn("truncated.mp3: file is corrupt", "\n".join(logs))
        self.assertIn("Do you want to skip this album", stdout.getvalue())
        self.assertEqual(len(self.lib.items()), 0)

    def test_quiet_skip_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with self.mockAutotag(), captureLog() as logs:
            beets.ui._raw_main(["import", "-q", self.import_dir])

        self.assertIn("check: Warning: failed to verify integrity", logs)
        self.assertIn(
            "truncated.mp3: file is corrupt\ncheck: Skipping.", "\n".join(logs)
        )
        self.assertEqual(len(self.lib.items()), 0)

    def test_add_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with self.mockAutotag(), controlStdin("n"):
            beets.ui._raw_main(["import", self.import_dir])

        self.assertEqual(len(self.lib.items()), 2)
        item = self.lib.items("truncated").get()
        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.title, "truncated tag")


class WriteTest(TestHelper, TestCase):

    def setUp(self):
        super(WriteTest, self).setUp()
        self.setupBeets()
        self.setupFixtureLibrary()

    def test_log_error_for_invalid_checksum(self):
        item = self.lib.items("ok").get()
        verify_checksum(item)
        self.modifyFile(item.path)

        with captureLog() as logs:
            beets.ui._raw_main(["write", item.title])
        self.assertRegexpMatches(
            "\n".join(logs),
            r"error reading .*: checksum did not match value in library",
        )

    def test_abort_write_when_invalid_checksum(self):
        item = self.lib.items("ok").get()
        verify_checksum(item)
        self.modifyFile(item.path, title="other title")

        item["title"] = "newtitle"
        item.store()
        beets.ui._raw_main(["write", item.title])

        mediafile = MediaFile(item.path)
        self.assertNotEqual(mediafile.title, "newtitle")

    def test_write_on_integrity_error(self):
        MockChecker.install()

        item = self.lib.items("truncated").get()

        item["title"] = "newtitle"
        item.store()
        beets.ui._raw_main(["write", item.title])

        item["checksum"] = ""
        item.load()
        verify_checksum(item)
        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.title, "newtitle")

    def test_update_checksum(self):
        item = self.lib.items("ok").get()
        orig_checksum = item["checksum"]
        verify_checksum(item)

        item["title"] = "newtitle"
        item.store()
        beets.ui._raw_main(["write", item.title])

        item["checksum"] = ""
        item.load()
        self.assertNotEqual(item["checksum"], orig_checksum)
        verify_checksum(item)

        mediafile = MediaFile(item.path)
        self.assertEqual(mediafile.title, "newtitle")


class ConvertTest(TestHelper, TestCase):

    def setUp(self):
        super(ConvertTest, self).setUp()
        self.setupBeets()
        beets.config["plugins"] = ["convert"]
        beets.plugins._instances.clear()
        beets.plugins.load_plugins(("convert", "check"))

        beets.config["convert"] = {
            "dest": os.path.join(self.temp_dir, "convert"),
            # Truncated copy to break checksum
            "command": "dd bs=1024 count=6 if=$source of=$dest",
        }
        self.setupFixtureLibrary()

    def test_convert_command(self):
        with controlStdin("y"):
            print("GO")
            beets.ui._raw_main(["convert", "ok.ogg"])

    def test_update_after_keep_new_convert(self):
        item = self.lib.items("ok.ogg").get()
        verify_checksum(item)

        with controlStdin("y"):
            beets.ui._raw_main(["convert", "--keep-new", "ok.ogg"])

        converted = self.lib.items("ok.ogg").get()
        self.assertNotEqual(converted.path, item.path)
        self.assertNotEqual(converted.checksum, item.checksum)
        verify_checksum(converted)
