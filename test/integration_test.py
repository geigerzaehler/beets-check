import os.path
import re
from unittest import TestCase

import beets
import beets.library
import beets.plugins
import beets.ui
from mediafile import MediaFile

from beetsplug.check import IntegrityChecker, verify_checksum
from test.helper import MockChecker, TestHelper, captureLog, captureStdout, controlStdin


class ImportTest(TestHelper, TestCase):
    def setUp(self):
        super().setUp()
        self.setupBeets()
        self.setupImportDir(["ok.mp3"])
        IntegrityChecker._all_available = []

    def tearDown(self):
        super().tearDown()
        MockChecker.restore()

    def test_add_album_checksum(self):
        with self.mockAutotag():
            beets.ui._raw_main(["import", self.import_dir])
        item = self.lib.items().get()
        assert "checksum" in item
        assert item.title == "ok tag"
        verify_checksum(item)

    def test_add_singleton_checksum(self):
        with self.mockAutotag():
            beets.ui._raw_main(["import", "--singletons", self.import_dir])
        item = self.lib.items().get()
        assert "checksum" in item
        verify_checksum(item)

    def test_add_album_checksum_without_autotag(self):
        with self.mockAutotag():
            beets.ui._raw_main(["import", "--noautotag", self.import_dir])
        item = self.lib.items().get()
        assert "checksum" in item
        assert item.title == "ok"
        verify_checksum(item)

    def test_add_singleton_checksum_without_autotag(self):
        with self.mockAutotag():
            beets.ui._raw_main([
                "import",
                "--singletons",
                "--noautotag",
                self.import_dir,
            ])
        item = self.lib.items().get()
        assert "checksum" in item
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
        assert item["checksum"] == orig_checksum

    def test_skip_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with (
            self.mockAutotag(),
            controlStdin(" "),
            captureStdout() as stdout,
            captureLog() as logs,
        ):
            beets.ui._raw_main(["import", self.import_dir])

        assert "check: Warning: failed to verify integrity" in logs
        assert "truncated.mp3: file is corrupt" in "\n".join(logs)
        assert "Do you want to skip this album" in stdout.getvalue()
        assert len(self.lib.items()) == 0

    def test_quiet_skip_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with self.mockAutotag(), captureLog() as logs:
            beets.ui._raw_main(["import", "-q", self.import_dir])

        assert "check: Warning: failed to verify integrity" in logs
        assert "truncated.mp3: file is corrupt\ncheck: Skipping." in "\n".join(logs)
        assert len(self.lib.items()) == 0

    def test_add_corrupt_files(self):
        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with self.mockAutotag(), controlStdin("n"):
            beets.ui._raw_main(["import", self.import_dir])

        assert len(self.lib.items()) == 2
        item = self.lib.items("truncated").get()
        mediafile = MediaFile(item.path)
        assert mediafile.title == "truncated tag"

    def test_fix_corrupt_files(self):
        self.config["check"]["auto-fix"] = True

        MockChecker.install()
        self.setupImportDir(["ok.mp3", "truncated.mp3"])

        with self.mockAutotag(), captureLog() as logs:
            beets.ui._raw_main(["import", self.import_dir])

        assert len(self.lib.items()) == 2
        assert "Fixing file:" in "\n".join(logs)
        assert "Fixed" in "\n".join(logs)

        item = self.lib.items("truncated").get()
        verify_checksum(item)

        mediafile = MediaFile(item.path)
        assert mediafile.url == "fixed"

    def test_fix_corrupt_files_fail_skip(self):
        self.config["check"]["auto-fix"] = True

        MockChecker.install()
        self.setupImportDir(["ok.mp3", "fail.mp3"])

        with self.mockAutotag(), captureLog() as logs, controlStdin("y"):
            beets.ui._raw_main(["import", self.import_dir])

        assert len(self.lib.items()) == 0
        assert "Fixing file:" in "\n".join(logs)
        assert "Failed to fix" in "\n".join(logs)

    def test_fix_corrupt_files_fail(self):
        self.config["check"]["auto-fix"] = True

        MockChecker.install()
        self.setupImportDir(["ok.mp3", "fail.mp3"])

        with self.mockAutotag(), captureLog() as logs, controlStdin("n"):
            beets.ui._raw_main(["import", self.import_dir])

        assert len(self.lib.items()) == 2
        assert "Fixing file:" in "\n".join(logs)
        assert "Failed to fix" in "\n".join(logs)

    def test_fix_corrupt_files_quiet(self):
        self.config["check"]["auto-fix"] = True
        self.config["import"]["quiet"] = True

        MockChecker.install()
        self.setupImportDir(["ok.mp3", "fail.mp3"])

        with self.mockAutotag(), captureLog() as logs:
            beets.ui._raw_main(["import", self.import_dir])

        assert len(self.lib.items()) == 0
        assert "Fixing file:" in "\n".join(logs)
        assert "Failed to fix" in "\n".join(logs)


class WriteTest(TestHelper, TestCase):
    def setUp(self):
        super().setUp()
        self.setupBeets()
        self.setupFixtureLibrary()

    def test_log_error_for_invalid_checksum(self):
        item = self.lib.items("ok").get()
        verify_checksum(item)
        self.modifyFile(item.path)

        with captureLog() as logs:
            beets.ui._raw_main(["write", item.title])
        assert re.search(
            r"error reading .*: checksum did not match value in library",
            "\n".join(logs),
        )

    def test_abort_write_when_invalid_checksum(self):
        item = self.lib.items("ok").get()
        verify_checksum(item)
        self.modifyFile(item.path, title="other title")

        item["title"] = "newtitle"
        item.store()
        beets.ui._raw_main(["write", item.title])

        mediafile = MediaFile(item.path)
        assert mediafile.title != "newtitle"

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
        assert mediafile.title == "newtitle"

    def test_update_checksum(self):
        item = self.lib.items("ok").get()
        orig_checksum = item["checksum"]
        verify_checksum(item)

        item["title"] = "newtitle"
        item.store()
        beets.ui._raw_main(["write", item.title])

        item["checksum"] = ""
        item.load()
        assert item["checksum"] != orig_checksum
        verify_checksum(item)

        mediafile = MediaFile(item.path)
        assert mediafile.title == "newtitle"


class ConvertTest(TestHelper, TestCase):
    def setUp(self):
        super().setUp()
        self.setupBeets()

        beets.config["convert"] = {
            "dest": os.path.join(self.temp_dir, "convert"),
            # Truncated copy to break checksum
            "command": "dd bs=1024 count=6 if=$source of=$dest",
        }
        self.setupFixtureLibrary()

    def test_convert_command(self):
        with controlStdin("y"):
            beets.ui._raw_main(["convert", "ok.ogg"])

    def test_update_after_keep_new_convert(self):
        item = self.lib.items("ok.ogg").get()
        verify_checksum(item)

        with controlStdin("y"):
            beets.ui._raw_main(["convert", "--keep-new", "ok.ogg"])

        converted = self.lib.items("ok.ogg").get()
        assert converted.path != item.path
        assert converted.checksum != item.checksum
        verify_checksum(converted)
