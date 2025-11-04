import os
import re
import shutil
from unittest import TestCase

import beets.library
import beets.ui
import pytest
from beets.library import Item
from beets.ui import UserError

from beetsplug.check import set_checksum, verify_checksum
from test.helper import MockChecker, TestHelper, captureLog, captureStdout, controlStdin


class TestBase(TestHelper, TestCase):
    def setUp(self):
        super().setUp()
        self.setupBeets()

    def tearDown(self):
        super().tearDown()


class CheckAddTest(TestBase, TestCase):
    """beet check --add"""

    def test_add_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        del item["checksum"]
        item.store()

        beets.ui._raw_main(["check", "-a"])

        item = self.lib.items().get()
        assert "checksum" in item

    def test_dont_add_existing_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        set_checksum(item)
        orig_checksum = item["checksum"]

        self.modifyFile(item.path)
        beets.ui._raw_main(["check", "-a"])

        item["checksum"] = ""
        item.load()
        assert item["checksum"] == orig_checksum

    def test_dont_fail_missing_file(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        del item["checksum"]
        item.path = "/doesnotexist"
        item.store()

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-a"])

        assert "WARNING No such file: /doesnotexist" in "\n".join(logs)

    def test_add_shows_integrity_warning(self):
        MockChecker.install()
        item = self.addIntegrityFailFixture(checksum=False)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-a"])

        assert "WARNING file is corrupt: {}".format(
            item.path.decode("utf-8")
        ) in "\n".join(logs)


class CheckTest(TestBase, TestCase):
    """beet check"""

    def test_check_success(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(["check"])
        assert (
            stdout.getvalue().split("\n")[-2] == "All checksums successfully verified"
        )

    def test_check_failed_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        try:
            with captureLog("beets.check") as logs:
                beets.ui._raw_main(["check"])
            assert "FAILED: {}".format(item.path.decode("utf-8")) in "\n".join(logs)
        except SystemExit:
            pass

    def test_not_found_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        item.path = "/doesnotexist"
        item.store()

        try:
            with captureLog("beets.check") as logs:
                beets.ui._raw_main(["check"])
            assert "OK:" in "\n".join(logs)
            assert "ERROR [Errno 2] No such file or directory" in "\n".join(logs)
        except SystemExit:
            pass

    def test_check_failed_exit_code(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        with pytest.raises(SystemExit) as exc_info:
            beets.ui._raw_main(["check"])
        assert exc_info.value.code == 15


class CheckIntegrityTest(TestBase, TestCase):
    # TODO beet check --external=mp3val,other
    """beet check --external"""

    def test_integrity_warning(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with pytest.raises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "--external"])

        assert "WARNING file is corrupt" in "\n".join(logs)

    def test_check_failed_exit_code(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with pytest.raises(SystemExit) as exc_info:
            beets.ui._raw_main(["check", "--external"])
        assert exc_info.value.code == 15

    def test_no_integrity_checkers_warning(self):
        MockChecker.installNone()
        self.addIntegrityFailFixture()

        with pytest.raises(UserError) as exc_info:
            beets.ui._raw_main(["check", "--external"])

        assert "No integrity checkers found." in exc_info.value.args[0]

    def test_print_integrity_checkers(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with pytest.raises(SystemExit), captureStdout() as stdout:
            beets.ui._raw_main(["check", "--external"])

        assert "Using integrity checker mock" in stdout.getvalue()


class CheckUpdateTest(TestBase, TestCase):
    """beet check --update"""

    def test_force_all_update(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        self.modifyFile(item.path)

        beets.ui._raw_main(["check", "--force", "--update"])

        item = self.lib.items().get()
        assert item["checksum"] != orig_checksum
        verify_checksum(item)

    def test_update_all_confirmation(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        self.modifyFile(item.path)

        with captureStdout() as stdout, controlStdin("y"):
            beets.ui._raw_main(["check", "--update"])

        assert "Do you want to overwrite all checksums" in stdout.getvalue()

        item = self.lib.items().get()
        assert item["checksum"] != orig_checksum
        verify_checksum(item)

    def test_update_all_confirmation_no(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        self.modifyFile(item.path)

        with controlStdin("n"):
            beets.ui._raw_main(["check", "--update"])

        item = self.lib.items().get()
        assert item["checksum"] == orig_checksum

    def test_update_nonexistent(self):
        item = Item(path="/doesnotexist")
        self.lib.add(item)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--update", "--force"])

        assert "ERROR [Errno 2] No such file or directory" in "\n".join(logs)


class CheckExportTest(TestBase, TestCase):
    """beet check --export"""

    def test_export(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--export"])

        item = self.lib.items().get()
        assert (
            "{} *{}\n".format(item.checksum, item.path.decode("utf-8"))
            in stdout.getvalue()
        )


class IntegrityCheckTest(TestHelper, TestCase):
    """beet check --external

    For integrated third-party tools"""

    def setUp(self):
        super().setUp()
        self.setupBeets()
        self.setupFixtureLibrary()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super().tearDown()

    def test_mp3_integrity(self):
        item = self.lib.items(["path::truncated.mp3"]).get()

        with pytest.raises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "--external"])
        assert (
            "check: WARNING It seems that file is "
            "truncated or there is garbage at the "
            "end of the file: {}".format(item.path.decode("utf-8"))
            in logs
        )

    def test_flac_integrity(self):
        item = self.lib.items("truncated.flac").get()

        with pytest.raises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "--external"])
        logs = "\n".join(logs)
        assert re.search(
            f"check: WARNING (while|during) decoding( data)?: {item.path.decode('utf-8')}",
            logs,
        )

    def test_ogg_vorbis_integrity(self):
        item = self.lib.items("truncated.ogg").get()

        with captureLog() as logs, pytest.raises(SystemExit):
            beets.ui._raw_main(["check", "--external"])
        assert (
            f"check: WARNING non-zero exit code for oggz-validate: {str(item.path, 'utf-8')}"
            in logs
        )

    def test_shellquote(self):
        item = self.lib.items(["ok.flac"]).get()
        item["title"] = "ok's"
        item.move()

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--external", item.title])
        assert "WARNING" not in "\n".join(logs)


class FixIntegrityTest(TestHelper, TestCase):
    """beet check -x"""

    def setUp(self):
        super().setUp()
        self.setupBeets()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super().tearDown()

    def test_fix_integrity(self):
        item = self.addIntegrityFailFixture()

        with pytest.raises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        assert "WARNING It seems that file is truncated" in "\n".join(logs)

        with controlStdin("y"), captureLog() as logs:
            beets.ui._raw_main(["check", "--fix"])
        assert item.path.decode("utf-8") in "\n".join(logs)
        assert "FIXED: {}".format(item.path.decode("utf-8")) in "\n".join(logs)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        assert "WARNING It seems that file is truncated" not in "\n".join(logs)

    def test_fix_flac_integrity(self):
        item = self.addItemFixture("truncated.flac")

        with pytest.raises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        assert "WARNING" in "\n".join(logs)

        with controlStdin("y"), captureLog() as logs:
            beets.ui._raw_main(["check", "--fix"])
        assert item.path.decode("utf-8") in "\n".join(logs)
        assert "FIXED: {}".format(item.path.decode("utf-8")) in "\n".join(logs)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        assert "WARNING" not in "\n".join(logs)

    def test_fix_without_confirmation(self):
        item = self.addIntegrityFailFixture()

        with pytest.raises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        assert "WARNING It seems that file is truncated" in "\n".join(logs)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--fix", "--force"])
        assert item.path.decode("utf-8") in "\n".join(logs)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        assert "WARNING It seems that file is truncated" not in "\n".join(logs)

    def test_update_checksum(self):
        item = self.addIntegrityFailFixture()
        old_checksum = item["checksum"]
        beets.ui._raw_main(["check", "--fix", "--force"])

        item["checksum"] = ""
        item.load()
        verify_checksum(item)
        assert old_checksum != item["checksum"]

    def test_dont_fix_with_wrong_checksum(self):
        item = self.addIntegrityFailFixture()
        item["checksum"] = "this is wrong"
        item.store()

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--fix", "--force"])
        assert "FAILED checksum" in "\n".join(logs)

        item["checksum"] = ""
        item.load()
        assert item["checksum"] == "this is wrong"

    def test_nothing_to_fix(self):
        self.addItemFixture("ok.ogg")
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--fix", "--force"])
        assert "No MP3 files to fix" in stdout.getvalue()

    def test_do_not_fix(self):
        item = self.addIntegrityFailFixture()
        with controlStdin("n"):
            beets.ui._raw_main(["check", "--fix"])
        verify_checksum(item)


class ToolListTest(TestHelper, TestCase):
    def setUp(self):
        super().setUp()
        self.enableIntegrityCheckers()
        self.setupBeets()
        self.orig_path = os.environ["PATH"]
        os.environ["PATH"] = self.temp_dir

    def tearDown(self):
        super().tearDown()
        os.environ["PATH"] = self.orig_path

    def test_list(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--list-tools"])
        assert "mp3val" in stdout.getvalue()
        assert "flac" in stdout.getvalue()
        assert "oggz-validate" in stdout.getvalue()

    def test_found_mp3val(self):
        shutil.copy("/bin/echo", os.path.join(self.temp_dir, "mp3val"))
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--list-tools"])
        assert re.search(r"mp3val *found", stdout.getvalue())

    def test_oggz_validate_not_found(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--list-tools"])
        assert re.search(r"oggz-validate *not found", stdout.getvalue())
