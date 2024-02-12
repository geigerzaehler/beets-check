beets-check
===========
[![Build Status](https://travis-ci.org/geigerzaehler/beets-check.svg?branch=master)](https://travis-ci.org/geigerzaehler/beets-check)
[![Coverage Status](https://coveralls.io/repos/geigerzaehler/beets-check/badge.png?branch=master)](https://coveralls.io/r/geigerzaehler/beets-check?branch=master)

*The [beets][] plugin for paranoid obsessive-compulsive music geeks.*

*beets-check* lets you verify the integrity of your audio files. It computes
and validates file checksums and uses third party tools to run custom
tests on files.

This plugin requires at least version 1.6.0 of beets and at least Python 3.8

```
pip install --upgrade beets>=1.6.0
pip install git+git://github.com/geigerzaehler/beets-check.git@master
```

Then add `check` to the list of plugins in your beet configuration.
(Running `beet config --edit` might be the quickest way.)

If you want to use third-party tools to test your audio files you have
to manually install them on your system. Run `beet check --list-tools`
to see a list of programs the plugin can use or [add your
own](#third-party-tests).


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
database.  The command also prints a warning if one of the third-party
tools finds an error. (More on those [later](#third-party-tests).)

After some time (or maybe a system crash) you’ll probably want to go back to
your library and verify that none of the files have changed. To do this run

```
$ beet check
FAILED: /music/Sgt. Pepper/13 A Day in the Life.mp3
Verifying checksums:  5102/8337 [53%]
```

For later inspection you might want to keep a log.  To do that just
redirect the error output with `beet check 2>check.log`. All `WARNING`
and `ERROR` lines are sent to stderr, so you will still see the
progressbar.

When you change your files through beets, using the `modfiy` command
for example, the plugin will [update the checksums
automatically](#automatic-update). However, if you change files
manually, you also need to update the checksums manually.
```
$ beet check -u 'album:Sgt. Pepper'
Updating checksums:  2/13 [15%]
```

### Third-party Tests

The plugin allows you to add custom file checks through external tools.
The plugin supports `flac --test`, `oggz-validate`, and `mp3val` out of
the box, but you can also [configure your own](#third-party-tools).

Custom tests are run when on the following occasions.

* Before importing a file (see below)
* Before adding checksums with the `-a` flag
* When running `beet check --external`

The file checks are not run when updating files. The rationale is that
if the checksum of a file is correct, the file is assumed to be clean
and pass all the custom tests.

If some file fails a test the line 
```
WARNING error description: /path/to/file
```
is printed.


### Usage with `import`

Since it would be tedious to run `check -a` every time you import new music
into beets, *beets-check* will add checksum automatically. Before file
is imported the plugin will also check the file with the provided
third-party tools. If the check fails beets will ask you to confirm the
import.

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

If you run `import` with the `--quiet` flag the importer will skip
files that do not pass third-party tests automatically and log an
error.


### Automatic Update

The [`write`][write] and [`modify`][modify] commands as well as some plugins will
change a file’s content and thus invalidate its checksum. To relieve you from
updating the checksum manually, *beets-check* will recalculate the checksums of
all the files that were changed.

```
$ beet check -e 'title:A Day in the Life'
ded5...363f */music/life.mp3

$ beet modify 'artist=The Beatles' title:A Day in the Life'

$ beet check -e 'title:A Day in the Life'
d942...5a82 */music/life.mp3
```

This is basically equivalent to running `beets check -u QUERY` after a modifying
command.

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
                 [ --external
                 | --add
                 | --update [--force]
                 | --export
                 | --fix [--force]
                 ] [QUERY...]
beet check --list-tools
```

The plugin has subcommands for checking files, running integrity checks,
adding, updating and exporting checksums and listing third-party tools. All but
the last accepty a `QUERY` paramter that will restrict the operation to files
matching the query.  Remember, if a query contains a slash beets will
[interpret it as a path][path query] and match all files that are contained in
a subdirectory of that path.

The default `check` command, as well as the `--add`, `--update`, and
`--external` commands provide structured output to `stderr` to be easily parseable
by other tools. If a file’s checksum cannot be verified the line
`FAILED: /path/to/file` is printed to stdout. If an external test
fails, the line `WARNING error description: /path/to/file` is printed.

In addition, the commands print a progress indicator to `stdout` if
`stdout` is connected to a terminal. This can be disabled with the
**`-q, --quiet`** flag.

- **`beet check [-q] [QUERY...]`** The default command verifies all
  file checksums against the database. The output is described above.
  Exits with status code `15` if at least one file does not pass a
  test.

- **`-e, --external`** Run third-party tools for the given file. The
  output is described above. Exits with status code `15` if at least
  one file does not pass a test.

- **`-a, --add`** Look for files in the database that don’t have a
  checksum, compute it from the file and add it to the database. This will also
  print warnings for failed integrity checks.

- **`-u, --update`** Calculate checksums for all files matching the
  query and write the them to the database. If no query is given this will
  overwrite all checksums already in the database. Since that is almost
  certainly not what you want, beets will ask you for confirmation in that
  case unless the `--force` flag is set.

- **`--export`** Outputs a list of filenames with corresponding
  checksums in the format used by the `sha256sum` command. You can then use
  that command to check your files externally. For example
  `beet check -e | sha256sum -c`.

- **`-x, --fix [--force | -f]`** Since `v0.9.2`. Fix files with
  third-party tools. Since this changes files it will ask for you to
  confirm the fixes. This can be disabled with the `--force` flag.

- **`-l, --list-tools`** Outputs a list of third party programs that
  *beets-check* uses to verify file integrity and shows whether they are
  installed. The plugin comes with support for the
  [`oggz-validate`][oggz-validate], [`mp3val`][mp3val] and [`flac`][flac] commands.


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
* `threads: 4` Use four threads to compute checksums.

### Third-party Tools

*beets-check* allows you to configure custom tests for your files.

Custom tests are shell commands that are run on an audio file and
may produce an error.

```yaml
check:
  tools:
    mp3val:
      cmd: 'mp3val {}'
      formats: MP3
      error: '^WARNING: .* \(offset 0x[0-9a-f]+\): (.*)$'
      fix: 'mp3val -f -nb {}'
```

Each tool is a dictionary entry under `check.tools`, where the key is
the tools name and the value is a configuration dictionary with the
following keys.

- **`cmd`** The shell command that tests the file. The string is
  formatted with python’s [`str.format()`][python-format] to replace
  '{}' with the quoted path of the file to check.

- **`formats`** A space separated list of audio formats the tool can
  check. Valid formats include 'MP'

- **`error`** Python regular expression to match against the tools
  output. If a match is found, an error is assumed to have occured
  and the error description is the first match group.

- **`fix`** Shell command to run when fixing files. The command is
  formtted similar to `cmd`.

A test run with a given tool is assumed to have failed in one of the
following two cases.

- The combined output of `stdout` and `stderr` matches the `error`
  Regular Expression.

- The shell command exits with a non-zero status code.


[python-format]:https://docs.python.org/2/library/string.html#format-string-syntax


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
