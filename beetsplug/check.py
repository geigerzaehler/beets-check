# Copyright (c) 2014 Thomas Scholtes

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.


import os
import re
import sys
from concurrent import futures
from hashlib import sha256
from optparse import OptionParser
from subprocess import PIPE, STDOUT, Popen, check_call

import beets
from beets import config, importer, logging
from beets.library import ReadError
from beets.plugins import BeetsPlugin
from beets.ui import Subcommand, UserError, colorize, decargs, input_yn
from beets.util import cpu_count, displayable_path, syspath

log = logging.getLogger("beets.check")


def set_checksum(item):
    item["checksum"] = compute_checksum(item)
    item.store()


def compute_checksum(item):
    hash = sha256()
    with open(syspath(item.path), "rb") as file:
        hash.update(file.read())
    return hash.hexdigest()


def verify_checksum(item):
    if item["checksum"] != compute_checksum(item):
        raise ChecksumError(item.path, "checksum did not match value in library.")


def verify_integrity(item):
    for checker in IntegrityChecker.allAvailable():
        checker.check(item)


class ChecksumError(ReadError):
    pass


class CheckPlugin(BeetsPlugin):

    def __init__(self):
        super(CheckPlugin, self).__init__()
        self.config.add(
            {
                "import": True,
                "write-check": True,
                "write-update": True,
                "integrity": True,
                "convert-update": True,
                "threads": cpu_count(),
                "external": {
                    "mp3val": {
                        "cmdline": "mp3val {0}",
                        "formats": "MP3",
                        "error": r"^WARNING: .* \(offset 0x[0-9a-f]+\): (.*)$",
                        "fix": "mp3val -nb -f {0}",
                    },
                    "flac": {
                        "cmdline": "flac --test --silent {0}",
                        "formats": "FLAC",
                        "error": "^.*: ERROR,? (.*)$",
                    },
                    "oggz-validate": {"cmdline": "oggz-validate {0}", "formats": "OGG"},
                },
            }
        )

        if self.config["import"]:
            self.register_listener("item_imported", self.item_imported)
            self.import_stages = [self.copy_original_checksum]
            self.register_listener("album_imported", self.album_imported)
        if self.config["write-check"]:
            self.register_listener("write", self.item_before_write)
        if self.config["write-update"]:
            self.register_listener("after_write", self.item_after_write)
        if self.config["convert-update"]:
            self.register_listener("after_convert", self.after_convert)
        if self.config["integrity"]:
            self.register_listener("import_task_choice", self.verify_import_integrity)

    def commands(self):
        return [CheckCommand(self.config)]

    def album_imported(self, lib, album):
        for item in album.items():
            if not item.get("checksum", None):
                set_checksum(item)

    def item_imported(self, lib, item):
        if not item.get("checksum", None):
            set_checksum(item)

    def item_before_write(self, item, path, **kwargs):
        if path != item.path:
            return
        if item.get("checksum", None):
            verify_checksum(item)

    def item_after_write(self, item, path, **kwargs):
        if path != item.path:
            return
        set_checksum(item)

    def after_convert(self, item, dest, keepnew):
        if keepnew:
            set_checksum(item)

    def copy_original_checksum(self, config, task):
        for item in task.imported_items():
            checksum = None
            for replaced in task.replaced_items[item]:
                try:
                    checksum = replaced["checksum"]
                except KeyError:
                    continue
                if checksum:
                    break
            if checksum:
                item["checksum"] = checksum
                item.store()

    def verify_import_integrity(self, session, task):
        integrity_errors = []
        if not task.items:
            return
        for item in task.items:
            try:
                verify_integrity(item)
            except IntegrityError as ex:
                integrity_errors.append(ex)

        if integrity_errors:
            log.warning("Warning: failed to verify integrity")
            for error in integrity_errors:
                log.warning("  {}: {}".format(displayable_path(item.path), error))
            if beets.config["import"]["quiet"] or input_yn(
                "Do you want to skip this album (Y/n)"
            ):
                log.info("Skipping.")
                task.choice_flag = importer.action.SKIP


class CheckCommand(Subcommand):

    def __init__(self, config):
        self.threads = config["threads"].get(int)
        self.check_integrity = config["integrity"].get(bool)

        parser = OptionParser(usage="%prog [options] [QUERY...]")
        parser.add_option(
            "-e",
            "--external",
            action="store_true",
            dest="external",
            default=False,
            help="run external tools",
        )
        parser.add_option(
            "-a",
            "--add",
            action="store_true",
            dest="add",
            default=False,
            help="add checksum for all files that do not already have one",
        )
        parser.add_option(
            "-u",
            "--update",
            action="store_true",
            dest="update",
            default=False,
            help="compute new checksums and add the to the database",
        )
        parser.add_option(
            "-f",
            "--force",
            action="store_true",
            dest="force",
            default=False,
            help="force updating the whole library or fixing all files",
        )
        parser.add_option(
            "--export",
            action="store_true",
            dest="export",
            default=False,
            help="print paths and corresponding checksum",
        )
        parser.add_option(
            "-x",
            "--fix",
            action="store_true",
            dest="fix",
            default=False,
            help="fix errors with external tools",
        )
        parser.add_option(
            "-l",
            "--list-tools",
            action="store_true",
            dest="list_tools",
            default=False,
            help="list available third-party used to check integrity",
        )
        parser.add_option(
            "-q",
            "--quiet",
            action="store_true",
            dest="quiet",
            default=False,
            help="only show errors",
        )
        super(CheckCommand, self).__init__(
            parser=parser, name="check", help="compute and verify checksums"
        )

    def func(self, lib, options, arguments):
        self.quiet = options.quiet
        self.lib = lib
        arguments = decargs(arguments)
        self.query = arguments
        self.force_update = options.force
        if options.add:
            self.add()
        elif options.update:
            self.update()
        elif options.export:
            self.export()
        elif options.fix:
            self.fix(ask=not options.force)
        elif options.list_tools:
            self.list_tools()
        else:
            self.check(options.external)

    def add(self):
        self.log("Looking for files without checksums...")
        items = [i for i in self.lib.items(self.query) if not i.get("checksum", None)]

        def add(item):
            log.debug("adding checksum for {0}".format(displayable_path(item.path)))
            try:
                set_checksum(item)
            except FileNotFoundError:
                log.warning(
                    "{} {}: {}".format(
                        colorize("text_warning", "WARNING"),
                        "No such file",
                        displayable_path(item.path),
                    )
                )
                return
            if self.check_integrity:
                try:
                    verify_integrity(item)
                except IntegrityError as ex:
                    log.warning(
                        "{} {}: {}".format(
                            colorize("text_warning", "WARNING"),
                            ex.reason,
                            displayable_path(item.path),
                        )
                    )

        self.execute_with_progress(add, items, msg="Adding missing checksums")

    def check(self, external):
        if external and not IntegrityChecker.allAvailable():
            no_checkers_warning = (
                "No integrity checkers found. " "Run 'beet check --list-tools'"
            )
            raise UserError(no_checkers_warning)

        if external:
            progs = list(map(lambda c: c.name, IntegrityChecker.allAvailable()))
            plural = "s" if len(progs) > 1 else ""
            self.log("Using integrity checker{} {}".format(plural, ", ".join(progs)))

        items = list(self.lib.items(self.query))
        failures = [0]

        def check(item):
            try:
                if external:
                    verify_integrity(item)
                elif item.get("checksum", None):
                    verify_checksum(item)
                log.debug(
                    "{}: {}".format(
                        colorize("text_success", "OK"), displayable_path(item.path)
                    )
                )
            except ChecksumError:
                log.error(
                    "{}: {}".format(
                        colorize("text_error", "FAILED"), displayable_path(item.path)
                    )
                )
                failures[0] += 1
            except IntegrityError as ex:
                log.warning(
                    "{} {}: {}".format(
                        colorize("text_warning", "WARNING"),
                        ex.reason,
                        displayable_path(item.path),
                    )
                )
                failures[0] += 1
            except IOError as exc:
                log.error("{} {}".format(colorize("text_error", "ERROR"), exc))
                failures[0] += 1

        if external:
            msg = "Running external tests"
        else:
            msg = "Verifying checksums"
        self.execute_with_progress(check, items, msg)

        failures = failures[0]
        if external:
            if failures:
                self.log("Found {} integrity error(s)".format(failures))
                sys.exit(15)
            else:
                self.log("Integrity successfully verified")
        else:
            if failures:
                self.log("Failed to verify checksum of {} file(s)".format(failures))
                sys.exit(15)
            else:
                self.log("All checksums successfully verified")

    def update(self):
        if not self.query and not self.force_update:
            if not input_yn(
                "Do you want to overwrite all " "checksums in your database? (y/n)",
                require=True,
            ):
                return

        items = self.lib.items(self.query)

        def update(item):
            log.debug("updating checksum: {}".format(displayable_path(item.path)))
            try:
                set_checksum(item)
            except IOError as exc:
                log.error("{} {}".format(colorize("text_error", "ERROR"), exc))

        self.execute_with_progress(update, items, msg="Updating checksums")

    def export(self):
        for item in self.lib.items(self.query):
            if item.get("checksum", None):
                print("{} *{}".format(item.checksum, displayable_path(item.path)))

    def fix(self, ask=True):
        items = list(self.lib.items(self.query))
        failed = []

        def check(item):
            try:
                if "checksum" in item:
                    verify_checksum(item)
                fixer = IntegrityChecker.fixer(item)
                if fixer:
                    fixer.check(item)
                    log.debug(
                        "{}: {}".format(
                            colorize("text_success", "OK"), displayable_path(item.path)
                        )
                    )
            except IntegrityError:
                failed.append(item)
            except ChecksumError:
                log.error(
                    "{}: {}".format(
                        colorize("text_error", "FAILED checksum"),
                        displayable_path(item.path),
                    )
                )
            except IOError as exc:
                log.error("{} {}".format(colorize("text_error", "ERROR"), exc))

        self.execute_with_progress(check, items, msg="Verifying integrity")

        if not failed:
            self.log("No MP3 files to fix")
            return

        for item in failed:
            log.info(displayable_path(item.path))

        if ask and not input_yn(
            "Do you want to fix these files? {} (y/n)", require=True
        ):
            return

        def fix(item):
            fixer = IntegrityChecker.fixer(item)
            if fixer:
                fixer.fix(item)
                log.debug(
                    "{}: {}".format(
                        colorize("text_success", "FIXED"), displayable_path(item.path)
                    )
                )
                set_checksum(item)

        self.execute_with_progress(fix, failed, msg="Fixing files")

    def list_tools(self):
        checkers = [
            (checker.name, checker.available()) for checker in IntegrityChecker.all()
        ]
        prog_length = max(map(lambda c: len(c[0]), checkers)) + 3
        for name, available in checkers:
            msg = name + (prog_length - len(name)) * " "
            if available:
                msg += colorize("text_success", "found")
            else:
                msg += colorize("text_error", "not found")
            print(msg)

    def log(self, msg):
        if not self.quiet:
            print(msg)

    def log_progress(self, msg, index, total):
        if self.quiet or not sys.stdout.isatty():
            return
        msg = "{}: {}/{} [{}%]".format(msg, index, total, index * 100 / total)
        sys.stdout.write(msg + "\r")
        sys.stdout.flush()
        if index == total:
            sys.stdout.write("\n")
        else:
            sys.stdout.write(len(msg) * " " + "\r")

    def execute_with_progress(self, func, args, msg=None):
        """Run `func` for each value in the iterator `args` in a thread pool.

        When the function has finished it logs the progress and the `msg`.
        """
        total = len(args)
        finished = 0
        with futures.ThreadPoolExecutor(max_workers=self.threads) as e:
            for _ in e.map(func, args):
                finished += 1
                self.log_progress(msg, finished, total)


class IntegrityError(ReadError):
    pass


class IntegrityChecker(object):

    @classmethod
    def all(cls):
        if hasattr(cls, "_all"):
            return cls._all

        cls._all = []
        for name, tool in config["check"]["external"].items():
            cls._all.append(cls(name, tool))
        return cls._all

    @classmethod
    def allAvailable(cls):
        if not hasattr(cls, "_all_available"):
            cls._all_available = [c for c in cls.all() if c.available()]
        return cls._all_available

    def __init__(self, name, config):
        self.name = name
        self.cmdline = config["cmdline"].get(str)

        if config["formats"].exists():
            self.formats = config["formats"].as_str_seq()
        else:
            self.formats = True

        if config["error"].exists():
            self.error_match = re.compile(config["error"].get(str), re.M)
        else:
            self.error_match = False

        if config["fix"].exists():
            self.fixcmd = config["fix"].get(str)
        else:
            self.fixcmd = False

    def available(self):
        try:
            with open(os.devnull, "wb") as devnull:
                check_call(
                    [self.cmdline.split(" ")[0], "-v"], stdout=devnull, stderr=devnull
                )
        except OSError:
            return False
        else:
            return True

    @classmethod
    def fixer(cls, item):
        """Return an `IntegrityChecker` instance that can fix this item."""
        for checker in cls.allAvailable():
            if checker.can_fix(item):
                return checker

    def can_check(self, item):
        return self.formats is True or item.format in self.formats

    def check(self, item):
        if not self.can_check(item):
            return
        process = Popen(
            self.cmdline.format(self.shellquote(syspath(item.path).decode("utf-8"))),
            shell=True,
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
        )
        stdout = process.communicate()[0]
        if self.error_match:
            match = self.error_match.search(stdout.decode("utf-8"))
        else:
            match = False
        if match:
            raise IntegrityError(item.path, match.group(1))
        elif process.returncode:
            raise IntegrityError(
                item.path, "non-zero exit code for {}".format(self.name)
            )

    def can_fix(self, item):
        return self.can_check(item) and self.fixcmd

    def fix(self, item):
        check_call(
            self.fixcmd.format(self.shellquote(syspath(item.path).decode("utf-8"))),
            shell=True,
            stdin=PIPE,
            stdout=PIPE,
            stderr=STDOUT,
        )

    def shellquote(self, s):
        return "'" + s.replace("'", r"'\''") + "'"
