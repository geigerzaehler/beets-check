beets-check
===========

*beets-check* is a plugin for [beets][] that lets you to verify the integrity
of your audio files. It computes checksum for files in your library, stores
them in the database and verifies them.

To use the plugin you need the development version of beets. You can
install it via
```
pip install git+git://github.com/sampsyo/beets.git
pip install git+git://github.com/geigerzaehler/beets-check.git
```


To get started compute and store checksums for your files.
```
$ beet check -a
Adding unknown checksums:  1032/8337 [12%]
```
This command adds a checksum for all files in your library that dont’t
have one yet.

To verify the checksums against their file run
```
$ beet check
/music/A Day in the Life.mp3: FAILED
Verifying checksums:  5102/8337 [53%]
```

If you changed one of the files on purpose, its checksum most certainly will
have changed. So go ahead and update the database with the new one.
```
$ beet check -u 'album:Sgt. Pepper'
Updating checksums:  2/13 [2%]
```

Since, it would be tedious to run `check -a` every time you import new music
into beets, *beets-check* will do this for you. The plugin hooks into the
importer and after a tracks has been added to the database and all tracks have
been written it will add a checksum for that file.

The same goes for updating tags. The [`write`][write] and [`modify`][modify]
commands updates the tags of audio files and this invalidates their checksum.
Therefore, *beets-check* will automatically update your checksum after the
write has finished.

```
$ beet check -e 'title:A Day in the Life'
ded5...363f */music/life.mp3

$ beet modify 'title:A Day in the Life' 'artist:The Beatles'

$ beet check -e 'title:A Day in the Life'
d942...5a82 */music/life.mp3
```

To make sure that the file hasn’t changed before beets writes it, we check
every file before updating its tags. If the check failes, beets will not write
the file.


```
$ beet modify 'artist=The Beatles' 'title:A Day in the Life'
could not write /music/life.mp3: checksum did not match value in library
```

*NOTE* This feature is currently not available.

[beets]: http://beets.readthedocs.org/en/latest
[write]: http://beets.readthedocs.org/en/latest/reference/cli.html#write
[modify]: http://beets.readthedocs.org/en/latest/reference/cli.html#modify


CLI Reference
-------------

```
beet check [--quiet] [--add | [--update [--force]] | --export] [QUERY...]
```

If the `QUERY` argument is given the command will restrict all it operations to
files matching the query.  Remember, if a query contains a slash beets will
[interpret it as a path][path query] and match all files that are contained in
a subdirectory of that path.

Without the `-a`, `-u` and `-e` options, the command will verify all checksums
in the database. If the standard output is a terminal it shows a progress
statement like in the example above. If the verification of a file failed the
command prints `/path/to/file: FAILED` to the error output but continues
checking the remaining files. If at least one file could not be verified the
program will exit with exit code `15`.

- **`-a, --add [QUERY...]`** Calculate the checksum for files that don’t have one yet
  and add it to the database.

- **`-u, --update [QUERY...]`** Calculate checksums for all files matching the
  query and write the them to the database. If no query is given this will
  overwrite all checksums already in the database. Since that is almost
  certainly not what you want, beets will ask you for confirmation in that
  case unless the `--force` flag is set.

- **`-e, export [QUERY...]`** Outputs a list of filenames with corresponding
  checksums in the format used by the `sha256sum` command. You can then use
  that command to check your files externally. For example
  `beet check -e | sha256sum -c`.

- **`-q, --quiet`** Suppresses the progress line but still prints verification
  errors. This is the default if stdout is not connected to a terminal

[path query]: http://beets.readthedocs.org/en/latest/reference/query.html#path-queries

Configuration
-------------

By default *beets-check* uses the following configuration.

```yaml
check:
  import: yes
  write-check: yes
  write-update: yes
  integrity: no
```

These option control at which point *beets-check* will be used automatically by
other beets commands. You can disable each option by setting its value to `no`.

* `import: no` Don’t add checksums for new files during the import process
* `write-check: no` Don’t verify checksums before writing files with
  `beet write` or `beet modify`.
* `write-update: no` Don’t update checksums after writing files with
  `beet write` or `beet modify`.
* `integrity: no` Don’t use third party tools to check the integrity of
  a file.


Format-Specific Integretiy Checks
---------------------------------

Checksums alone cannot find errors in the files content. For example,
prior to the import an MP3 file may have been truncated by an incomplete
download. To detect these error the plugin uses third party tools.

Integrity checks are supported for the OGG, MP3, and FLAC formats. They
use the [`oggz-validate`][oggz-validate], [`mp3val`][mp3val] and
[`flac`][flac] (with the `--test` flag) commands. These programs have to
be installed on your system. To show a list of available tools use

```
$ beet check --list-tools
oggz-validate   found
mp3val          found
flac            missing
```

Similar to checksum verification, integrity checks are performed before
writing a file. In addition the integrity of files that are about to be
imported is checked.

```
$ beet import 'Abbey Road'
Tagging:
    The Beatles - Abbey Road
URL:
    http://musicbrainz.org/release/eca8996a-a637-3259-ba07-d2573c601a1b
(Similarity: 100.0%) (Vinyl, 1969, DE, Apple Records)
Warning: failed to verify integrity
  Abbey Road/01 Come Together.mp3: MPEG stream error
Do you want to skip this album? (Y/n)
```

To check files that are already in your library run
```
$ beet check
Abbey Road/01 Come Together.mp3: WARNING MPEG stream error
```

[flac]: https://xiph.org/flac/documentation_tools_flac.html
[mp3val]: http://mp3val.sourceforge.net/
[oggz-validate]: https://www.xiph.org/oggz/

License
-------

Copyright (c) 2014 Thomas Scholtes

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"), to
deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
