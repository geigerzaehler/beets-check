# Changelog

## v0.15.1 2025-10-25

- Add support for beets 2.5
- Drop support for Python 3.9 and beets<2

## v0.15.0 2024-09-20

- Don’t run custom external programs with `-v` (e.g. `ffmpeg -v`) to determine
  whether they are available. (Fixes #43)
- Require Python >=3.9

## v0.14.1 2024-07-11

- Require beets >=1.6.1 and support beets v2.x

## v0.14.0 2024-02-12

- Require Python ^3.8
- Require beets ^1.6

## v0.13.0 2020-06-27

- Drop support for Python2.7
- Require `beets>=1.4.7`
- Fix a crash in `beet check --add` when a music file is not found on disk. (@ssssam)

## v0.12.1 2020-04-19

- Fix crash when running `beet import` with threading enabled ([#22](https://github.com/geigerzaehler/beets-check/issues/22)) ([@alebianco](https://github.com/alebianco))

## v0.12.0 2019-08-12

- Add support for Python 3
- Drop support for `beets<=1.3.10`
