#!/usr/bin/env python3
"""Check git tags follow vMAJOR.MINOR.PATCH, fail CI on a bad tag.

Run: python3 src/git_tag_checker.py v1.2.3
     python3 src/git_tag_checker.py --file examples/tags.txt
     python3 src/git_tag_checker.py --git
     cat tags.txt | python3 src/git_tag_checker.py --stdin

The tool checks each tag against the shape vMAJOR.MINOR.PATCH
(semantic versioning with a leading "v"). It prints PASS or FAIL
per tag and a one-line summary. It exits 1 when any tag fails, so
it can fail a CI run.

It never creates, moves, or deletes a tag, and it never changes a
file. It is report-only and runs fully offline: it sends nothing
anywhere and needs no API key.

Exit codes: 0 when every tag passes, 1 when any tag fails, 2 for
a usage or input problem (missing file, not a git repo, no tags
to check).

Python standard library only.
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

VERSION = "1.0.0"

# The shape a tag must follow: vMAJOR.MINOR.PATCH, with an optional
# prerelease part (-alpha.1) and optional build metadata (+build.1).
# Numbers are non-negative integers with no leading zeros, as
# semantic versioning requires.
_FULL_SHAPE = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_BARE_SHAPE = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)"
    r"(?:-((?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*)"
    r"(?:\.(?:0|[1-9][0-9]*|[0-9]*[a-zA-Z-][0-9a-zA-Z-]*))*))?"
    r"(?:\+([0-9a-zA-Z-]+(?:\.[0-9a-zA-Z-]+)*))?$"
)
_PRERELEASE_IDENT = re.compile(r"^[0-9a-zA-Z-]+$")
_BUILD_IDENT = re.compile(r"^[0-9a-zA-Z-]+$")
_NUMBER = re.compile(r"^[0-9]+$")
_PART_NAMES = ("major", "minor", "patch")


def _split_core(core):
    """Split a tag body into (version, prerelease, build).

    Build metadata (+...) is split off first, then the prerelease
    part (-...). Returns (version, prerelease or None, build or
    None)."""
    build = None
    if "+" in core:
        core, build = core.split("+", 1)
    prerelease = None
    if "-" in core:
        core, prerelease = core.split("-", 1)
    return core, prerelease, build


def tag_problem(tag, *, allow_no_v=False, no_prerelease=False, seen=None):
    """Return a plain-language reason the tag fails, or None when
    it follows vMAJOR.MINOR.PATCH."""
    if tag == "":
        return "empty tag name"
    if seen is not None:
        if tag in seen:
            return "duplicate tag"
        seen.add(tag)
    if _FULL_SHAPE.match(tag):
        if no_prerelease and "-" in tag.split("+", 1)[0]:
            return "prerelease tags are not allowed"
        return None
    # Work out the most specific reason instead of a generic one.
    if tag.startswith("v"):
        core = tag[1:]
    elif allow_no_v and _BARE_SHAPE.match(tag):
        if no_prerelease and "-" in tag.split("+", 1)[0]:
            return "prerelease tags are not allowed"
        return None
    elif tag and tag[0].isdigit():
        return "missing 'v' prefix"
    else:
        return "does not follow vMAJOR.MINOR.PATCH"
    version, prerelease, build = _split_core(core)
    parts = version.split(".")
    if len(parts) == 1:
        return "missing minor and patch versions"
    if len(parts) == 2:
        return "missing patch version"
    if len(parts) > 3:
        return "too many version parts — expected MAJOR.MINOR.PATCH"
    for part, name in zip(parts, _PART_NAMES):
        if not _NUMBER.match(part):
            return "the %s version is not a number" % name
        if len(part) > 1 and part.startswith("0"):
            return "leading zero in the %s version" % name
    if prerelease is not None:
        if no_prerelease:
            return "prerelease tags are not allowed"
        if prerelease == "":
            return "empty prerelease part"
        for ident in prerelease.split("."):
            if ident == "":
                return "empty identifier in the prerelease part"
            if not _PRERELEASE_IDENT.match(ident):
                return "bad characters in the prerelease part"
            if ident.isdigit() and len(ident) > 1 and ident.startswith("0"):
                return (
                    "leading zero in prerelease identifier '%s'" % ident
                )
    if build is not None:
        if build == "":
            return "empty build metadata"
        for ident in build.split("."):
            if ident == "":
                return "empty identifier in the build metadata"
            if not _BUILD_IDENT.match(ident):
                return "bad characters in the build metadata"
    return "does not follow vMAJOR.MINOR.PATCH"


def check_tags(tags, *, allow_no_v=False, no_prerelease=False):
    """Check a list of tag names. Returns a list of (tag, reason)
    pairs, where reason is None for a pass."""
    seen = set()
    results = []
    for tag in tags:
        reason = tag_problem(
            tag,
            allow_no_v=allow_no_v,
            no_prerelease=no_prerelease,
            seen=seen,
        )
        results.append((tag, reason))
    return results


def read_tag_file(path):
    """Read one tag per line from a file. Blank lines and lines
    starting with '#' are ignored. Returns (tags, error), where
    error is None on success."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None, "file not found: %s" % path
    except OSError as exc:
        return None, "cannot read %s: %s" % (path, exc)
    except UnicodeDecodeError:
        return None, "file is not UTF-8 text: %s" % path
    tags = []
    for line in text.splitlines():
        line = line.strip()
        if line == "" or line.startswith("#"):
            continue
        tags.append(line)
    return tags, None


def read_git_tags(repo):
    """Read tags with `git tag` in the given folder. Returns
    (tags, error), where error is None on success."""
    try:
        proc = subprocess.run(
            ["git", "tag"],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        return None, "git is not installed"
    except subprocess.TimeoutExpired:
        return None, "git tag timed out in %s" % repo
    if proc.returncode != 0:
        return None, "%s is not a git repo, or has no tags" % repo
    return proc.stdout.splitlines(), None


def format_text(results):
    """Format the per-tag report plus the one-line summary."""
    lines = []
    passed = 0
    for tag, reason in results:
        if reason is None:
            lines.append("PASS   %s" % tag)
            passed += 1
        else:
            lines.append("FAIL   %s: %s" % (tag, reason))
    failed = len(results) - passed
    lines.append(
        "%d checked, %d passed, %d failed"
        % (len(results), passed, failed)
    )
    return "\n".join(lines)


def format_json(results):
    """Format the report as JSON: one entry per tag, plus counts."""
    entries = [
        {
            "tag": tag,
            "passed": reason is None,
            "reason": reason,
        }
        for tag, reason in results
    ]
    passed = sum(1 for _, reason in results if reason is None)
    return json.dumps(
        {
            "results": entries,
            "checked": len(results),
            "passed": passed,
            "failed": len(results) - passed,
        },
        indent=2,
    )


def build_parser():
    parser = argparse.ArgumentParser(
        prog="git_tag_checker",
        description=(
            "Check git tags follow vMAJOR.MINOR.PATCH. "
            "Report-only; it never creates, moves, or deletes a tag."
        ),
    )
    parser.add_argument("tags", nargs="*", help="tag names to check")
    parser.add_argument(
        "--file",
        metavar="PATH",
        help="read one tag per line from a file",
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="read one tag per line from standard input",
    )
    parser.add_argument(
        "--git",
        action="store_true",
        help="check every tag in the local repo (git tag)",
    )
    parser.add_argument(
        "--repo",
        metavar="PATH",
        default=".",
        help="repo folder for --git (default: current folder)",
    )
    parser.add_argument(
        "--allow-no-v",
        action="store_true",
        help="also accept bare 1.2.3 without the 'v' prefix",
    )
    parser.add_argument(
        "--no-prerelease",
        action="store_true",
        help="fail tags with a prerelease part, for example v1.2.3-alpha.1",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="print the report as JSON instead of text",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="git-tag-checker-cli %s" % VERSION,
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    sources = sum(
        [
            bool(args.tags),
            bool(args.file),
            args.stdin,
            args.git,
        ]
    )
    if sources > 1:
        print(
            "error: give tags only one way — as names, --file, "
            "--stdin, or --git",
            file=sys.stderr,
        )
        return 2
    if args.file:
        tags, error = read_tag_file(args.file)
        if error is not None:
            print("error: %s" % error, file=sys.stderr)
            return 2
    elif args.stdin:
        tags = [
            line.strip()
            for line in sys.stdin.read().splitlines()
            if line.strip() != "" and not line.strip().startswith("#")
        ]
    elif args.git or sources == 0:
        tags, error = read_git_tags(args.repo)
        if error is not None:
            print("error: %s" % error, file=sys.stderr)
            return 2
    else:
        tags = list(args.tags)
    if not tags:
        print("error: no tags to check", file=sys.stderr)
        return 2
    results = check_tags(
        tags,
        allow_no_v=args.allow_no_v,
        no_prerelease=args.no_prerelease,
    )
    if args.json:
        print(format_json(results))
    else:
        print(format_text(results))
    failed = sum(1 for _, reason in results if reason is not None)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
