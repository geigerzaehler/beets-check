beets-check
===========

*The [beets][] plugin for paranoid obsessive-compulsive music geeks.*

*beets-check* lets you verify the integrity of your audio files. It
computes and verifies checksums for files in your library and uses third
party tools to [check the integrity] of audio data.

If you want to use this plugin you need a development version of beets.

```
pip install git+git://github.com/sampsyo/beets.git@4a6e3f12
pip install git+git://github.com/geigerzaehler/beets-check.git
```

If you want to use third-party tools to verify the integrity of your
audio files you have to install them on your system manually. Run `beet
check --list-tools` to see the list of programs that the plugin can use.


Usage
-----

Let’s get started and add checksums for your library.

```
$ beet check -a
WARNING integrity error: /music/Abbey Road/01 Come Together.mp3
Adding unknown checksums:  1032/8337 [12%]
```

This command adds a checksum for all files in your library that dont’t
have one yet. It also looks for integrity errors in the file’s audio
content and prints a warning.

If you want to make sure that your files have stayed the same, run

```
$ beet check
WARNING integrity error: /music/Abbey Road/01 Come Together.mp3
FAILED: /music/Sgt. Pepper/13 A Day in the Life.mp3
Verifying checksums:  5102/8337 [53%]
```

For later inspection you might want to keep a log.  To do that just
redirect the error output with `beet check 2>check.log`. All `WARNING`
and `ERROR` lines are sent to stderr, so you will still see the
progressbar.


If you changed one of the files on purpose, its checksum most certainly will
have changed, too. So go ahead and update the database.
```
$ beet check -u 'album:Sgt. Pepper'
Updating checksums:  2/13 [15%]
```

### Usage with `import`

Since, it would be tedious to run `check -a` every time you import new music
into beets, *beets-check* will do this for you automatically. The plugin
hooks into the importer and after a tracks has been added to the
database and all tracks have been written it will add a checksum for
that file. It will also check the file integrity and ask you to confirm
importing corrupt files.

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

If you run `import` with the `--quiet` flag will skip corrupted files
automatically and log an error.

### Usage with `write` and `modify`

*beets-check* hooks into the [`write`][write] and [`modify`][modify]
commands similar to `import`. These commands update the tags of audio
files and this invalidates their checksum, so beets recalculates it
after the file has been modified.

```
$ beet check -e 'title:A Day in the Life'
ded5...363f */music/life.mp3

$ beet modify 'artist=The Beatles' title:A Day in the Life'

$ beet check -e 'title:A Day in the Life'
d942...5a82 */music/life.mp3
```

To make sure that a file hasn’t changed before beets changes it, the
plugin will verify the checksum before the file is written.  If the
check fails, beets will not write the file and issue a warning.


```
$ beet modify 'artist=The Beatles' 'title:A Day in the Life'
could not write /music/life.mp3: checksum did not match value in library
```

TODO update to new plugin api.


[beets]: http://beets.readthedocs.org/en/latest
[write]: http://beets.readthedocs.org/en/latest/reference/cli.html#write
[modify]: http://beets.readthedocs.org/en/latest/reference/cli.html#modify



CLI Reference
-------------

```
beet check [--quiet] [--add | [--update [--force]] | --export] [QUERY...]
beet check --list-tools
```

The `QUERY` argument will restrict all operations to files matching the
query.  Remember, if a query contains a slash beets will [interpret it
as a path][path query] and match all files that are contained in a
subdirectory of that path.

Without any of the `-a`, `-u`, `-e`, and `-l` flags, the command will verify all
items that are matched by the query. If the standard output is a
terminal it shows a progress statement like in the example above. If the
verification of a file failed the command prints `/path/to/file: FAILED`
to the error output but continues checking the remaining files. If at
least one file could not be verified the program will exit with exit
code `15`.

- **`-a, --add [QUERY...]`** Calculate the checksum for files that don’t have one yet
  and add it to the database.

- **`-u, --update [QUERY...]`** Calculate checksums for all files matching the
  query and write the them to the database. If no query is given this will
  overwrite all checksums already in the database. Since that is almost
  certainly not what you want, beets will ask you for confirmation in that
  case unless the `--force` flag is set.

- **`-e, --export [QUERY...]`** Outputs a list of filenames with corresponding
  checksums in the format used by the `sha256sum` command. You can then use
  that command to check your files externally. For example
  `beet check -e | sha256sum -c`.

- **`-l, --list-tools`** Outputs a list of third party programs that
  *beets-check* uses to verify file integrity and shows whether they are
  installed. The plugin comes with support for the
  [`oggz-validate`][oggz-validate], [`mp3val`][mp3val] and [`flac`][flac] commands.

- **`-q, --quiet`** Suppresses the progress line but still prints verification
  errors. This is the default if stdout is not connected to a terminal

[path query]: http://beets.readthedocs.org/en/latest/reference/query.html#path-queries
[flac]: https://xiph.org/flac/documentation_tools_flac.html
[mp3val]: http://mp3val.sourceforge.net/
[oggz-validate]: https://www.xiph.org/oggz/



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
