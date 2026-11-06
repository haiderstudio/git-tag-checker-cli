# git-tag-checker-cli

Check git tags follow vMAJOR.MINOR.PATCH, fail CI on a bad tag.

[![CI](https://github.com/haiderstudio/git-tag-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/git-tag-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`git_tag_checker` checks git tags against the shape
`vMAJOR.MINOR.PATCH` (semantic versioning with a leading `v`).
It prints `PASS` or `FAIL` per tag, plus a one-line summary, and
exits 1 when any tag fails — so it can fail a CI run.

- A tag must look like `v1.2.3`: three non-negative numbers
  with no leading zeros, separated by dots, with a leading `v`.
  `v1.2.3`, `v0.1.0`, and `v10.20.30` pass; `v1.2`, `v1`,
  `1.2.3`, `v01.2.3`, and `release-2` fail.
- A prerelease part is allowed, as in `v2.0.0-alpha.1`, and
  build metadata is allowed, as in `v1.0.0+build.1`. Both follow
  the semantic versioning rules: no empty parts, no leading
  zeros in numeric prerelease identifiers. `--no-prerelease`
  fails any tag with a prerelease part.
- A bare `1.2.3` fails by default, because the leading `v` is
  part of the shape. `--allow-no-v` accepts it.
- A tag that appears twice fails as a duplicate.
- Every failure names the reason, not just the tag: missing
  patch version, missing `v` prefix, leading zero in the major
  version, duplicate tag, and so on — so you know what to fix.
- It reads tags four ways: as arguments, from a file
  (`--file`, one tag per line, `#` comments and blank lines
  ignored), from standard input (`--stdin`), or every tag in
  the local repo (`--git`, which runs `git tag`). With no tags
  and no flag, it checks the tags in the current repo.
- It is report-only and runs fully offline: it never creates,
  moves, or deletes a tag, sends nothing anywhere, and needs
  no API key.

## What it does NOT do

- It does not create, move, or delete tags. A bad tag is
  reported; fixing it is your job.
- It does not check whether a tag points at the right commit,
  whether a release exists for a tag, or whether a tag is
  signed — the shape of the name only.
- It does not check versions in code, in a changelog, or in a
  package file — tags only. (Checking that a version in code
  matches the tag is a different job.)
- It does not talk to GitHub or any remote. `--git` reads
  only the local tags in the folder you run it in.

## Who it is for

Any project that tags releases and wants the tags to stay
clean: a developer adding a CI step that fails the build on a
badly named tag, a maintainer who keeps finding tags like `v1`
or `release-2` next to real releases, or anyone who wants one
small check instead of a tag rule buried inside a big CI setup.
If every tag passes, you get a clean report; if one fails, the
report says which tag and why.

## How this differs from similar tools

Tag tools today mostly create or bump tags instead of checking
them. The quoted GitHub search for `"git-tag-checker"`
returns 1 result, a 1-star Python script that checks whether a
GitHub release tag exists — existence, not format, a different
job. The closest format tools work on one tag at a time or
inside a bigger job: `semantic-tag-increment` increments tags
(its `--validate` flag checks one tag you hand it),
`tag-validate-action` is a GitHub Action that validates one tag
push and can check signatures, `verscan` checks that a manifest
version, a changelog entry, and the latest git tag agree with
each other, and `actions-semver-checker` validates the tag and
release layout of a GitHub Action's own repo — and can fix
things itself. The tag-creation tools (`go-git-semver`,
`release-tag`, and the like) generate the next tag; they do
not check the tags you already have.

This tool does a narrower job: a Python standard-library-only
CLI that checks every tag in a local repo, or any list of tags,
against one fixed shape, reports the exact reason per failure,
and exits 1 for CI — no install beyond Python, no Action, no
remote, and it never touches a tag.

## Install

Python standard library only — no packages to download. Clone
the repo and run it in place:

```sh
git clone https://github.com/haiderstudio/git-tag-checker-cli.git
cd git-tag-checker-cli
```

Python 3.10 or newer. Git is only needed for `--git`; checking
tags from arguments, a file, or standard input works without git.

## Usage

Check one tag:

```sh
python3 src/git_tag_checker.py v1.2.3
```

Real output:

```text
PASS   v1.2.3
1 checked, 1 passed, 0 failed
```

The command exits 0.

Check a good tag and a bad tag together:

```sh
python3 src/git_tag_checker.py v1.2.3 v1.2
```

Real output:

```text
PASS   v1.2.3
FAIL   v1.2: missing patch version
2 checked, 1 passed, 1 failed
```

The command exits 1, because one tag failed.

Check a list from a file:

```sh
python3 src/git_tag_checker.py --file examples/tags.txt
```

Real output:

```text
PASS   v1.2.3
PASS   v0.1.0
PASS   v2.0.0-alpha.1
FAIL   v1.2: missing patch version
FAIL   1.2.3: missing 'v' prefix
FAIL   v01.2.3: leading zero in the major version
FAIL   release-2: does not follow vMAJOR.MINOR.PATCH
FAIL   v1.2.3: duplicate tag
8 checked, 3 passed, 5 failed
```

The command exits 1, because five tags failed. The same output
is saved in `examples/sample-output.txt`.

Check a file of good tags only:

```sh
python3 src/git_tag_checker.py --file examples/good-tags.txt
```

Real output:

```text
PASS   v1.2.3
PASS   v0.1.0
PASS   v10.20.30
PASS   v2.0.0-alpha.1
PASS   v1.0.0+build.1
5 checked, 5 passed, 0 failed
```

The command exits 0.

Check every tag in the current repo:

```sh
python3 src/git_tag_checker.py --git
```

Check tags from a pipe:

```sh
printf 'v1.2.3\nrelease-2\n' | python3 src/git_tag_checker.py --stdin
```

Real output:

```text
PASS   v1.2.3
FAIL   release-2: does not follow vMAJOR.MINOR.PATCH
2 checked, 1 passed, 1 failed
```

Get the report as JSON, for another tool to read:

```sh
python3 src/git_tag_checker.py --json v1.2.3 v1.2
```

Real output:

```json
{
  "results": [
    {
      "tag": "v1.2.3",
      "passed": true,
      "reason": null
    },
    {
      "tag": "v1.2",
      "passed": false,
      "reason": "missing patch version"
    }
  ],
  "checked": 2,
  "passed": 1,
  "failed": 1
}
```

The command exits 1, because one tag failed.

## Examples

### 1. Fail CI on a bad tag

```sh
python3 src/git_tag_checker.py --git
echo $?
```

```text
1
```

The exit code is 1 when any tag in the repo fails. Put the
same command in CI and the build fails until the tag is fixed
or removed. With only good tags the same command prints `PASS`
lines and exits 0.

### 2. A stray tag next to real releases

```sh
python3 src/git_tag_checker.py v1.2.3 release-2
```

```text
PASS   v1.2.3
FAIL   release-2: does not follow vMAJOR.MINOR.PATCH
2 checked, 1 passed, 1 failed
```

The reason names the problem — the tag is not a version at
all — so you know it is a stray name, not a version with a
typo in one part.

### 3. A duplicate tag

```sh
python3 src/git_tag_checker.py v1.2.3 v1.2.3
```

```text
PASS   v1.2.3
FAIL   v1.2.3: duplicate tag
2 checked, 1 passed, 1 failed
```

The first copy passes; the second is reported as a duplicate.

## How it is tested

```sh
python3 tests/test_git_tag_checker.py
```

37 tests, standard library `unittest` only — no third-party
packages. They cover: the tag shape (good tags, missing `v`,
missing parts, too many parts, non-numeric parts, leading
zeros, stray tags, prerelease and build-metadata rules,
`--allow-no-v`, `--no-prerelease`, duplicates), the inputs
(file, stdin, `--git` in a real temporary git repo, `--git`
outside a repo, two input sources, empty input, bad flags, a
missing file, a non-UTF-8 file, `--json` output, `--version`,
and the input file left unchanged), the bundled examples (the
committed `examples/sample-output.txt` is compared against a
fresh run, the example script, and every line the README quotes
is checked against the real output), and a check that the code
and the tests import standard library only.

The bundled example is a real run, not made-up output:

```sh
sh examples/run-example.sh
```

It checks the sample list, the good list, and one good and one
bad tag. The check runs exit 1 on purpose, because five
example tags fail — that is the expected result here.

## Contributing

Small, focused improvements are welcome — see
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

Built from scratch for this repo. The shape follows semantic
versioning as documented at semver.org; no code was copied from
any existing tag checker.
