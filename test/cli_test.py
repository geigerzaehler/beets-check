import os
import shutil
from test.helper import MockChecker, TestHelper, captureLog, captureStdout, controlStdin
from unittest import TestCase

import beets.library
import beets.ui
from beets.library import Item
from beets.ui import UserError

from beetsplug.check import set_checksum, verify_checksum


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
        del item["checksum"]
        item.store()

        beets.ui._raw_main(["check", "-a"])

        item = self.lib.items().get()
        self.assertIn("checksum", item)

    def test_dont_add_existing_checksums(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        set_checksum(item)
        orig_checksum = item["checksum"]

        self.modifyFile(item.path)
        beets.ui._raw_main(["check", "-a"])

        item["checksum"] = ""
        item.load()
        self.assertEqual(item["checksum"], orig_checksum)

    def test_dont_fail_missing_file(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        del item["checksum"]
        item.path = "/doesnotexist"
        item.store()

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-a"])

        self.assertIn("WARNING No such file: /doesnotexist", "\n".join(logs))

    def test_add_shows_integrity_warning(self):
        MockChecker.install()
        item = self.addIntegrityFailFixture(checksum=False)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-a"])

        self.assertIn(
            "WARNING file is corrupt: {}".format(item.path.decode("utf-8")),
            "\n".join(logs),
        )


class CheckTest(TestBase, TestCase):
    """beet check"""

    def test_check_success(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(["check"])
        self.assertEqual(
            "All checksums successfully verified", stdout.getvalue().split("\n")[-2]
        )

    def test_check_failed_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        try:
            with captureLog("beets.check") as logs:
                beets.ui._raw_main(["check"])
        except SystemExit:
            pass

        self.assertIn("FAILED: {}".format(item.path.decode("utf-8")), "\n".join(logs))

    def test_not_found_error_log(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        item.path = "/doesnotexist"
        item.store()

        try:
            with captureLog("beets.check") as logs:
                beets.ui._raw_main(["check"])
        except SystemExit:
            pass

        self.assertIn("OK:", "\n".join(logs))
        self.assertIn("ERROR [Errno 2] No such file or directory", "\n".join(logs))

    def test_check_failed_exit_code(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        self.modifyFile(item.path)

        with self.assertRaises(SystemExit) as exit:
            beets.ui._raw_main(["check"])
        self.assertEqual(exit.exception.code, 15)


class CheckIntegrityTest(TestBase, TestCase):
    # TODO beet check --external=mp3val,other
    """beet check --external"""

    def test_integrity_warning(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with self.assertRaises(SystemExit):
            with captureLog() as logs:
                beets.ui._raw_main(["check", "--external"])

        self.assertIn("WARNING file is corrupt", "\n".join(logs))

    def test_check_failed_exit_code(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with self.assertRaises(SystemExit) as exit:
            beets.ui._raw_main(["check", "--external"])
        self.assertEqual(exit.exception.code, 15)

    def test_no_integrity_checkers_warning(self):
        MockChecker.installNone()
        self.addIntegrityFailFixture()

        with self.assertRaises(UserError) as error:
            beets.ui._raw_main(["check", "--external"])

        self.assertIn("No integrity checkers found.", error.exception.args[0])

    def test_print_integrity_checkers(self):
        MockChecker.install()
        self.addIntegrityFailFixture()

        with self.assertRaises(SystemExit):
            with captureStdout() as stdout:
                beets.ui._raw_main(["check", "--external"])

        self.assertIn("Using integrity checker mock", stdout.getvalue())


class CheckUpdateTest(TestBase, TestCase):
    """beet check --update"""

    def test_force_all_update(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        self.modifyFile(item.path)

        beets.ui._raw_main(["check", "--force", "--update"])

        item = self.lib.items().get()
        self.assertNotEqual(item["checksum"], orig_checksum)
        verify_checksum(item)

    def test_update_all_confirmation(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        self.modifyFile(item.path)

        with captureStdout() as stdout, controlStdin("y"):
            beets.ui._raw_main(["check", "--update"])

        self.assertIn("Do you want to overwrite all checksums", stdout.getvalue())

        item = self.lib.items().get()
        self.assertNotEqual(item["checksum"], orig_checksum)
        verify_checksum(item)

    def test_update_all_confirmation_no(self):
        self.setupFixtureLibrary()
        item = self.lib.items().get()
        orig_checksum = item["checksum"]
        self.modifyFile(item.path)

        with controlStdin("n"):
            beets.ui._raw_main(["check", "--update"])

        item = self.lib.items().get()
        self.assertEqual(item["checksum"], orig_checksum)

    def test_update_nonexistent(self):
        item = Item(path="/doesnotexist")
        self.lib.add(item)

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--update", "--force"])

        self.assertIn("ERROR [Errno 2] No such file or directory", "\n".join(logs))


class CheckExportTest(TestBase, TestCase):
    """beet check --export"""

    def test_export(self):
        self.setupFixtureLibrary()
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--export"])

        item = self.lib.items().get()
        self.assertIn(
            "{} *{}\n".format(item.checksum, item.path.decode("utf-8")),
            stdout.getvalue(),
        )


class IntegrityCheckTest(TestHelper, TestCase):
    """beet check --external

    For integrated third-party tools"""

    def setUp(self):
        super(IntegrityCheckTest, self).setUp()
        self.setupBeets()
        self.setupFixtureLibrary()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super(IntegrityCheckTest, self).tearDown()

    def test_mp3_integrity(self):
        item = self.lib.items(["path::truncated.mp3"]).get()

        with self.assertRaises(SystemExit):
            with captureLog() as logs:
                beets.ui._raw_main(["check", "--external"])
        print("\n".join(logs))
        self.assertIn(
            "check: WARNING It seems that file is "
            "truncated or there is garbage at the "
            "end of the file: {}".format(item.path.decode("utf-8")),
            logs,
        )

    def test_flac_integrity(self):
        item = self.lib.items("truncated.flac").get()

        with self.assertRaises(SystemExit):
            with captureLog() as logs:
                beets.ui._raw_main(["check", "--external"])
        logs = "\n".join(logs)
        self.assertRegex(
            logs,
            f"check: WARNING (while|during) decoding( data)?: {item.path.decode('utf-8')}",
        )

    def test_ogg_vorbis_integrity(self):
        item = self.lib.items("truncated.ogg").get()

        with self.assertRaises(SystemExit):
            with captureLog() as logs:
                beets.ui._raw_main(["check", "--external"])
                self.assertIn(
                    "check: WARNING non-zero exit code for oggz-validate: {}".format(
                        item.path
                    ),
                    logs,
                )

    def test_shellquote(self):
        item = self.lib.items(["ok.flac"]).get()
        item["title"] = "ok's"
        item.move()

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--external", item.title])
        self.assertNotIn("WARNING", "\n".join(logs))


class FixIntegrityTest(TestHelper, TestCase):
    """beet check -x"""

    def setUp(self):
        super(FixIntegrityTest, self).setUp()
        self.setupBeets()
        self.enableIntegrityCheckers()

    def tearDown(self):
        super(FixIntegrityTest, self).tearDown()

    def test_fix_integrity(self):
        item = self.addIntegrityFailFixture()

        with self.assertRaises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        self.assertIn("WARNING It seems that file is truncated", "\n".join(logs))

        with controlStdin("y"), captureLog() as logs:
            beets.ui._raw_main(["check", "--fix"])
        self.assertIn(item.path.decode("utf-8"), "\n".join(logs))
        self.assertIn("FIXED: {}".format(item.path.decode("utf-8")), "\n".join(logs))

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        self.assertNotIn("WARNING It seems that file is truncated", "\n".join(logs))

    def test_fix_without_confirmation(self):
        item = self.addIntegrityFailFixture()

        with self.assertRaises(SystemExit), captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        self.assertIn("WARNING It seems that file is truncated", "\n".join(logs))

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--fix", "--force"])
        self.assertIn(item.path.decode("utf-8"), "\n".join(logs))

        with captureLog() as logs:
            beets.ui._raw_main(["check", "-e"])
        self.assertNotIn("WARNING It seems that file is truncated", "\n".join(logs))

    def test_update_checksum(self):
        item = self.addIntegrityFailFixture()
        old_checksum = item["checksum"]
        beets.ui._raw_main(["check", "--fix", "--force"])

        item["checksum"] = ""
        item.load()
        verify_checksum(item)
        self.assertNotEqual(old_checksum, item["checksum"])

    def test_dont_fix_with_wrong_checksum(self):
        item = self.addIntegrityFailFixture()
        item["checksum"] = "this is wrong"
        item.store()

        with captureLog() as logs:
            beets.ui._raw_main(["check", "--fix", "--force"])
        self.assertIn("FAILED checksum", "\n".join(logs))

        item["checksum"] = ""
        item.load()
        self.assertEqual(item["checksum"], "this is wrong")

    def test_nothing_to_fix(self):
        self.addItemFixture("ok.ogg")
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--fix", "--force"])
        self.assertIn("No MP3 files to fix", stdout.getvalue())

    def test_do_not_fix(self):
        item = self.addIntegrityFailFixture()
        with controlStdin("n"):
            beets.ui._raw_main(["check", "--fix"])
        verify_checksum(item)


class ToolListTest(TestHelper, TestCase):

    def setUp(self):
        super(ToolListTest, self).setUp()
        self.enableIntegrityCheckers()
        self.setupBeets()
        self.orig_path = os.environ["PATH"]
        os.environ["PATH"] = self.temp_dir

    def tearDown(self):
        super(ToolListTest, self).tearDown()
        os.environ["PATH"] = self.orig_path

    def test_list(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--list-tools"])
        self.assertIn("mp3val", stdout.getvalue())
        self.assertIn("flac", stdout.getvalue())
        self.assertIn("oggz-validate", stdout.getvalue())

    def test_found_mp3val(self):
        shutil.copy("/bin/echo", os.path.join(self.temp_dir, "mp3val"))
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--list-tools"])
        self.assertRegexpMatches(stdout.getvalue(), r"mp3val *found")

    def test_oggz_validate_not_found(self):
        with captureStdout() as stdout:
            beets.ui._raw_main(["check", "--list-tools"])
        self.assertRegexpMatches(stdout.getvalue(), r"oggz-validate *not found")
