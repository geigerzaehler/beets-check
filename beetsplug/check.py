# Copyright (c) 2014 Thomas Scholtes

# Permission is hereby granted, free of charge, to any person obtaining a
# copy of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.


import re
import sys
import os.path
import logging
from subprocess import Popen, PIPE
from hashlib import sha256
from optparse import OptionParser

import beets
from beets import importer
from beets.plugins import BeetsPlugin, BeforeWriteError
from beets.ui import Subcommand, decargs, colorize, input_yn


log = logging.getLogger('beets.check')

def set_checksum(item):
    item['checksum'] = compute_checksum(item)
    item.store()

def compute_checksum(item):
    hash = sha256()
    with open(item.path, 'rb') as file:
        hash.update(file.read())
    return hash.hexdigest()

def verify(item):
    verify_checksum(item)
    verify_integrity(item)

def verify_checksum(item):
    if item['checksum'] != compute_checksum(item):
        raise ChecksumError('checksum did not match value in library.')

def verify_integrity(item):
    for checker in IntegrityChecker.allAvailable():
        checker.run(item)


class ChecksumError(BeforeWriteError): pass


class CheckPlugin(BeetsPlugin):

    def __init__(self):
        super(CheckPlugin, self).__init__()
        self.config.add({
            'import': True,
            'write-check': True,
            'write-update': True,
            'integrity': True,
        })
        if self.config['import']:
            self.register_listener('item_imported', self.item_imported)
            self.import_stages = [self.copy_original_checksum]
            self.register_listener('album_imported', self.album_imported)
        if self.config['write-check']:
            self.register_listener('write', self.item_before_write)
        if self.config['write-update']:
            self.register_listener('after_write', self.item_after_write)
        if self.config['integrity']:
            self.register_listener('import_task_choice', self.verify_import_integrity)

    def commands(self):
        return [CheckCommand()]

    def album_imported(self, lib, album):
        for item in album.items():
            if not item.get('checksum', None):
                set_checksum(item)

    def item_imported(self, lib, item):
        if not item.get('checksum', None):
            set_checksum(item)

    def item_before_write(self, item):
        if item.get('checksum', None):
            verify(item)

    def item_after_write(self, item):
        set_checksum(item)

    def copy_original_checksum(self, config, task):
        for item in task.imported_items():
            checksum = None
            for replaced in task.replaced_items[item]:
                checksum = replaced['checksum']
                if checksum:
                    break
            if checksum:
                item['checksum'] = checksum
                item.store()

    def verify_import_integrity(self, session, task):
        integrity_errors = []
        if not task.items:
            return
        for item in task.items:
            for checker in IntegrityChecker.allAvailable():
                try:
                    checker.run(item)
                except IntegrityError as ex:
                    integrity_errors.append(ex)

        if integrity_errors:
            log.warn('Warning: failed to verify integrity')
            for error in integrity_errors:
                log.warn('  {}: {}'.format(item.path, error))
            if beets.config['import']['quiet'] \
               or input_yn('Do you want to skip this album (Y/n)'):
                log.info('Skipping.')
                task.choice_flag = importer.action.SKIP


class CheckCommand(Subcommand):

    def __init__(self):
        parser = OptionParser(usage='%prog [options] [QUERY...]')
        parser.add_option(
            '-a', '--add',
            action='store_true', dest='add', default=False,
            help='add checksum for all files that do not already have one')
        parser.add_option(
            '-u', '--update',
            action='store_true', dest='update', default=False,
            help='compute new checksums and add the to the database')
        parser.add_option(
            '-f', '--force',
            action='store_true', dest='force', default=False,
            help='force updating the whole library')
        parser.add_option(
            '-e', '--export',
            action='store_true', dest='export', default=False,
            help='print paths and corresponding checksum')
        parser.add_option(
            '-l', '--list-tools',
            action='store_true', dest='list_tools', default=False,
            help='list available third-party used to check integrity')
        parser.add_option(
            '-q', '--quiet',
            action='store_true', dest='quiet', default=False,
            help='only show errors')
        super(CheckCommand, self).__init__(
                parser=parser,
                name='check',
                help='compute and verify checksums')

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
        elif options.list_tools:
            self.list_tools()
        else:
            self.check()

    def add(self):
        self.log('Looking for files without checksums...')
        items = [i for i in self.lib.items(self.query)
                            if not i.get('checksum', None)]
        total = len(items)
        for index, item in enumerate(items):
            log.debug('adding checksum for {0}'.format(item.path))
            set_checksum(item)
            try:
                verify_integrity(item)
            except IntegrityError as ex:
                log.warn('{} {}: {}'.format(colorize('yellow', 'WARNING'), ex,
                                            item.path))

            self.log_progress('Adding missing checksums', index+1, total)

    def check(self):
        self.log('Looking up files with checksums...')
        items = [i for i in self.lib.items(self.query)
                            if i.get('checksum', None)]
        total = len(items)
        failures = 0
        integrity = 0
        for index, item in enumerate(items):
            try:
                verify(item)
                log.debug('{}: {}'.format(colorize('green', 'OK'), item.path))
            except ChecksumError:
                log.error('{}: {}'.format(colorize('red', 'FAILED'), item.path))
                failures += 1
            except IntegrityError as ex:
                log.warn('{} {}: {}'.format(colorize('yellow', 'WARNING'), ex,
                                            item.path))
                integrity += 1
            self.log_progress('Verifying checksums', index+1, total)
        if integrity:
            self.log('Found {} integrity error(s)'.format(integrity))
        if failures:
            self.log('Failed to verify checksum of {} file(s)'.format(failures))
            sys.exit(15)
        else:
            self.log('All checksums successfully verified')

    def update(self):
        if not self.query and not self.force_update:
            if not input_yn('Do you want to overwrite all '
                            'checksums in your database? (y/n)', require=True):
                return
        items = self.lib.items(self.query)
        total = len(items)
        for index, item in enumerate(items):
            log.debug('updating checksum: {}'.format(item.path))
            set_checksum(item)
            self.log_progress('Updating checksums', index+1, total)

    def export(self):
        for item in self.lib.items(self.query):
            if item.get('checksum', None):
                print('{} *{}'.format(item.checksum, item.path))

    def list_tools(self):
        checkers = [(checker.program, checker.available())
                     for checker in IntegrityChecker.all()]
        prog_length = max(map(lambda c: len(c[0]), checkers)) + 3
        for program, available in checkers:
            msg = program + (prog_length-len(program))*u' '
            if available:
                msg += colorize('green', 'found')
            else:
                msg += colorize('red', 'not found')
            print(msg)

    def log(self, msg):
        if not self.quiet:
            print(msg)

    def log_progress(self, msg, index, total):
        if self.quiet or not sys.stdout.isatty():
            return
        msg = '{}: {}/{} [{}%]'.format(msg, index, total, index*100/total)
        sys.stdout.write(msg + '\r')
        sys.stdout.flush()
        if index == total:
            sys.stdout.write('\n')
        else:
            sys.stdout.write(len(msg)*' ' + '\r')


class IntegrityError(BeforeWriteError): pass


class IntegrityChecker(object):

    program = None
    arguments = []
    formats = []

    @classmethod
    def all(cls):
        if not hasattr(cls, '_all'):
            cls._all = [c() for c in cls.__subclasses__()]
        return cls._all

    @classmethod
    def allAvailable(cls):
        if not hasattr(cls, '_all_available'):
            cls._all_available = [c for c in cls.all() if c.available()]
        return cls._all_available

    def available(self):
        for path in os.environ.get('PATH').split(os.pathsep):
            if os.path.isfile(os.path.join(path, self.program)):
                return True
        return False

    def run(self, item):
        if item.format not in self.formats:
            return
        process = Popen([self.program] + self.arguments + [item.path],
                        stdin=PIPE, stdout=PIPE, stderr=PIPE)
        stdout, stderr = process.communicate()
        self.parse(stdout, stderr, process.returncode)

    def parse(self, stdout, stderr, returncode):
        raise NotImplementedError


class MP3Val(IntegrityChecker):

    program = 'mp3val'
    formats = ['MP3']

    log_matcher = re.compile( r'^WARNING: .* \(offset 0x[0-9a-f]+\): (.*)$')

    def parse(self, stdout, stderr, returncode):
        for line in stdout.split('\n'):
            match = self.log_matcher.match(line)
            if match:
                raise IntegrityError(match.group(1))

class FlacTest(IntegrityChecker):

    program = 'flac'
    arguments = ['--test', '--silent']
    formats = ['FLAC']

    error_matcher = re.compile( r'^.*: ERROR,? (.*)$')

    def parse(self, stdout, stderr, returncode):
        if returncode == 0:
            return
        for line in stderr.split('\n'):
            match = self.error_matcher.match(line)
            if match:
                raise IntegrityError('error {}'.format(match.group(1)))

class OggzValidate(IntegrityChecker):

    program = 'oggz-validate'

    def parse(self, stdout, stderr, returncode):
        pass
