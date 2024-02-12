import sys
import os
import tempfile
import logging
import shutil
from contextlib import contextmanager

try:
        from StringIO import StringIO
except ImportError:
        from io import StringIO

import beets
from beets import autotag
from beets import plugins
from beets.autotag import AlbumInfo, TrackInfo, \
    AlbumMatch, TrackMatch, Recommendation, Proposal
from beets.autotag.hooks import Distance
from beets.library import Item
from mediafile import MediaFile

from beetsplug import check

logging.getLogger('beets').propagate = True


class LogCapture(logging.Handler):

    def __init__(self):
        super(LogCapture, self).__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(str(record.msg))


@contextmanager
def captureLog(logger='beets'):
    capture = LogCapture()
    log = logging.getLogger(logger)
    log.addHandler(capture)
    try:
        yield capture.messages
    finally:
        log.removeHandler(capture)


@contextmanager
def captureStdout():
    org = sys.stdout
    sys.stdout = StringIO()
    try:
        yield sys.stdout
    finally:
        sys.stdout = org


@contextmanager
def controlStdin(input=None):
    org = sys.stdin
    sys.stdin = StringIO(input)
    try:
        yield sys.stdin
    finally:
        sys.stdin = org


class TestHelper(object):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        plugins._classes = set([check.CheckPlugin])
        self.disableIntegrityCheckers()

    def tearDown(self):
        self.unloadPlugins()
        if hasattr(self, 'temp_dir'):
            shutil.rmtree(self.temp_dir)
        MockChecker.restore()

    def setupBeets(self):
        os.environ['BEETSDIR'] = self.temp_dir

        self.config = beets.config
        self.config.clear()
        self.config.read()

        self.config['plugins'] = []
        self.config['verbose'] = True
        self.config['ui']['color'] = False
        self.config['threaded'] = False
        self.config['import']['copy'] = False

        self.libdir = os.path.join(self.temp_dir, 'libdir')
        os.mkdir(self.libdir)
        self.config['directory'] = self.libdir

        self.lib = beets.library.Library(
            self.config['library'].as_filename(),
            self.libdir
        )

        self.fixture_dir = os.path.join(os.path.dirname(__file__), 'fixtures')

    def setupImportDir(self, files):
        self.import_dir = os.path.join(self.temp_dir, 'import')
        if not os.path.isdir(self.import_dir):
            os.mkdir(self.import_dir)
        for file in files:
            src = os.path.join(self.fixture_dir, file)
            shutil.copy(src, self.import_dir)

    def setupFixtureLibrary(self):
        for basename in os.listdir(self.fixture_dir):
            item = self.addItemFixture(basename)
            check.set_checksum(item)

    def addIntegrityFailFixture(self, checksum=True):
        """Add item with integrity errors to the library and return it.

        The `MockChecker` will raise an integrity error when run on this item.
        """
        item = self.addItemFixture('truncated.mp3')
        if checksum:
            check.set_checksum(item)
        return item

    def addCorruptedFixture(self):
        """Add item with a wrong checksum to the library and return it.
        """
        item = self.addItemFixture('ok.ogg')
        item['checksum'] = 'this is a wrong checksum'
        item.store()
        return item

    def addItemFixture(self, basename):
        src = os.path.join(self.fixture_dir, basename)
        dst = os.path.join(self.libdir, basename)
        shutil.copy(src, dst)
        item = Item.from_path(dst)
        item.add(self.lib)
        return item

    def disableIntegrityCheckers(self):
        check.IntegrityChecker._all = []
        check.IntegrityChecker._all_available = []

    def enableIntegrityCheckers(self):
        if hasattr(check.IntegrityChecker, '_all'):
            delattr(check.IntegrityChecker, '_all')
        if hasattr(check.IntegrityChecker, '_all_available'):
            delattr(check.IntegrityChecker, '_all_available')

    def modifyFile(self, path, title='a different title'):
        mediafile = MediaFile(path)
        mediafile.title = title
        mediafile.save()

    @contextmanager
    def mockAutotag(self):
        mock = AutotagMock()
        mock.install()
        try:
            yield
        finally:
            mock.restore()

    def unloadPlugins(self):
        for plugin in plugins._classes:
            plugin.listeners = None
        plugins._classes = set()
        plugins._instances = {}


class AutotagMock(object):

    def __init__(self):
        self.id = 0

    def nextid(self):
        self.id += 1
        return self.id

    def install(self):
        self._orig_tag_album = autotag.tag_album
        self._orig_tag_item = autotag.tag_item
        autotag.tag_album = self.tag_album
        autotag.tag_item = self.tag_item

    def restore(self):
        autotag.tag_album = self._orig_tag_album
        autotag.tag_item = self._orig_tag_item

    def tag_album(self, items, **kwargs):
        artist = (items[0].artist or '') + ' tag'
        album = (items[0].album or '') + ' tag'
        mapping = {}
        dist = Distance()
        dist.tracks = {}
        for item in items:
            title = (item.title or '') + ' tag'
            track_info = TrackInfo(title=title, track_id=self.nextid(), index=1)
            mapping[item] = track_info
            dist.tracks[track_info] = Distance()

        album_info = AlbumInfo(album='album', album_id=self.nextid(),
                               artist='artist', artist_id=self.nextid(),
                               tracks=mapping.values())
        match = AlbumMatch(distance=dist, info=album_info, mapping=mapping,
                           extra_items=[], extra_tracks=[])
        return artist, album, Proposal([match], Recommendation.strong)

    def tag_item(self, item, **kwargs):
        title = (item.title or '') + ' tag'
        track_info = TrackInfo(title=title, track_id=self.nextid())
        match = TrackMatch(distance=Distance(), info=track_info)
        return Proposal([match], Recommendation.strong)


class MockChecker(object):
    name = 'mock'

    @classmethod
    def install(cls):
        check.IntegrityChecker._all_available = [cls()]

    @classmethod
    def restore(cls):
        if hasattr(check.IntegrityChecker, '_all_available'):
            delattr(check.IntegrityChecker, '_all_available')

    @classmethod
    def installNone(cls):
        check.IntegrityChecker._all_available = []

    def check(self, item):
        if b'truncated' in item.path:
            raise check.IntegrityError(item.path, 'file is corrupt')
