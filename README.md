beets-check
===========
[![Build Status](https://travis-ci.org/geigerzaehler/beets-check.svg?branch=master)](https://travis-ci.org/geigerzaehler/beets-check)
[![Coverage Status](https://coveralls.io/repos/geigerzaehler/beets-check/badge.png?branch=master)](https://coveralls.io/r/geigerzaehler/beets-check?branch=master)

*The [beets][] plugin for paranoid obsessive-compulsive music geeks.*

*beets-check* lets you verify the integrity of your audio files. It computes
and validates file checksums and uses third party tools to check the integrity
of audio data.

If you want to use this plugin, make sure your have version 1.3.4 of
beets installed.

```
pip install --upgrade beets>=1.3.4
pip install git+git://github.com/geigerzaehler/beets-check.git
```

If you want to use third-party tools to verify the integrity of your
audio files you have to manually install them on your system. Run `beet
check --list-tools` to see a list of programs that the plugin can use.


Usage
-----

Let’s get started and add some checksums to your library.

```
$ beet check -a
WARNING integrity error: /music/Abbey Road/01 Come Together.mp3
Adding unknown checksums:  1032/8337 [12%]
```

The `check` command looks for all files that don’t have a checksum yet.
It computes the checksum for each of these files and stores it in the
database.  The command also prints a warning if one of the integrity
tools has found an error.

After some time (or maybe a system crash) you’ll probably want to go back to
your library and verify that none of the files has changed. To do this run

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


If you have changed one of the files on purpose, its checksum most certainly
will have changed, too. So go ahead and update the database.
```
$ beet check -u 'album:Sgt. Pepper'
Updating checksums:  2/13 [15%]
```

Oftentimes it is possible to fix integrity errors in MP3 files. Ith the
*mp3val* program is installed *beet-check* can do this for you.
```
$ beet check -x 'album:Abbey Road'
Verifying integrity: 17/17 [100%]
/music/Abbey Road/01 Come Together.mp3
/music/Abbey Road/17 Her Majesty.mp3
Do you want to fix these files? (y/n) y
Fixing files: 1/2 [50%]
```
This will fix the files, keep a backup and update the checksums.

### Usage with `import`

Since it would be tedious to run `check -a` every time you import new music
into beets, *beets-check* will add checksum automatically. Before an album or
track is imported an integrity check is run. If the check fails beets will ask
you to confirm the import.

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

After a track has been added to the database and all modifications to the tags
have been written, beets-check adds the checksums. This is virtually the same as
running ``beets check -a `` after the import.

If you run `import` with the `--quiet` flag the importer will skip corrupted
files automatically and log an error.


### Usage with `write` and `modify`

The [`write`][write] and [`modify`][modify] commands change a file’s
content and this invalidates its checksum. To relieve you from updating the
checksum manually, the plugin will recalculate the checksums of all the files
that were changed.

```
$ beet check -e 'title:A Day in the Life'
ded5...363f */music/life.mp3

$ beet modify 'artist=The Beatles' title:A Day in the Life'

$ beet check -e 'title:A Day in the Life'
d942...5a82 */music/life.mp3
```

This is basically equivalent to running `beets check -u QUERY` after a
`write` or `modify` command

To make sure that a file hasn’t changed before beets changes it, the
plugin will verify the checksum before the file is written.  If the
check fails, beets will not write the file and issue a warning.


```
$ beet modify 'artist=The Beatles' 'title:A Day in the Life'
could not write /music/life.mp3: checksum did not match value in library
```


### Usage with `convert`

The [`convert`][convert] plugin can replace an audio file with a
transcoded version using the `--keep-new` flag. This will invalidate you
checksum, but *beets-check* knows about this and will update the
checksum automatically. You can disable this behaviour in the plugin
configuration. Note that, at the moment we do not verify the checksum
prior to the conversion, so a corrupted file might go undetected. This
feature is also only available with the master branch of beets


[beets]: http://beets.readthedocs.org/en/latest
[write]: http://beets.readthedocs.org/en/latest/reference/cli.html#write
[modify]: http://beets.readthedocs.org/en/latest/reference/cli.html#modify
[convert]: http://beets.readthedocs.org/en/latest/plugins/convert.html



CLI Reference
-------------

```
beet check [--quiet]
                 [ --integrity
                 | --add
                 | --update [--force]
                 | --export
                 | --fix [--force] [--no-backup]
                 ] [QUERY...]
beet check --list-tools
```

The plugin has subcommands for checking files, running integrity checks,
adding, updating and exporting checksums and listing third-party tools. All but
the last accepty a `QUERY` paramter that will restrict the operation to files
matching the query.  Remember, if a query contains a slash beets will
[interpret it as a path][path query] and match all files that are contained in
a subdirectory of that path.

- **`beet check [-q] [QUERY...]`** By default the plugin will verify all known
  checksums and also run integrity tests for all files. Integrity tests can
  be disabled with the `integrity` configuration option.

  If the standard output is a terminal it shows a progress statement like in
  the example above. If the checksum verification of a file failed the command
  prints `FAILED: /path/to/file` to the error output. And if one of the
  third-party tools detects an error it will print `WARNING error description:
  /path/to/file` to *stderr*. If at least one file has an invalid checksum the
  program will exit with status code `15`.

- **`-i, --integrity`** Only run third-party tools to check integrity and don
  not verify checksum. The output is the same is described in the default
  command.

- **`-a, --add`** Look for files in the database that don’t have a
  checksum, compute it from the file and add it to the database. This will also
  print warnings for failed integrity checks.

- **`-u, --update`** Calculate checksums for all files matching the
  query and write the them to the database. If no query is given this will
  overwrite all checksums already in the database. Since that is almost
  certainly not what you want, beets will ask you for confirmation in that
  case unless the `--force` flag is set.

- **`-e, --export`** Outputs a list of filenames with corresponding
  checksums in the format used by the `sha256sum` command. You can then use
  that command to check your files externally. For example
  `beet check -e | sha256sum -c`.

- **`-x, --fix [--force | -f] [--no-backup | -B]`** Fix MP3 files with
  integrity errors. Since this changes files it will ask for you to confirm the
  fixes. This can be disabled with the `--force` flag. For every fixed file the
  command preserves a backup of the original file with the `.bak` extension
  added to it. Backups can be disabled with the `--no-backup` flag or the
  `backup` configuration.

- **`-l, --list-tools`** Outputs a list of third party programs that
  *beets-check* uses to verify file integrity and shows whether they are
  installed. The plugin comes with support for the
  [`oggz-validate`][oggz-validate], [`mp3val`][mp3val] and [`flac`][flac] commands.

All commands accept a quiet flag.

- **`-q, --quiet`** Suppresse the progress line but still print verification
  errors. This is the default if stdout is not connected to a terminal.

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
  convert-update: yes
  integrity: yes
  backup: yes
  threads: num_of_cpus
```

These option control at which point *beets-check* will be used automatically by
other beets commands. You can disable each option by setting its value to `no`.

* `import: no` Don’t add checksums for new files during the import process.
  This also disables integrity checks on import and will not ask you to skip
  the import of corrupted files.
* `write-check: no` Don’t verify checksums before writing files with
  `beet write` or `beet modify`.
* `write-update: no` Don’t update checksums after writing files with
  `beet write` or `beet modify`.
* `convert-update: no` Don’t updated the checksum if a file has been
  converted with the `--keep-new` flag.
* `integrity: no` Don’t use third party tools to check the integrity of
  a file.
* `threads: 4` Use four threads to compute checksums.
* `backup: no` Don’t keep a backup of the original when fixing a file.


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
