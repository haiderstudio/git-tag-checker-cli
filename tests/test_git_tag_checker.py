#!/usr/bin/env python3
"""Tests for git_tag_checker. Standard library unittest only."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SRC = ROOT / "src" / "git_tag_checker.py"

sys.path.insert(0, str(ROOT / "src"))

import git_tag_checker as gtc  # noqa: E402


def run_cli(*args, input_text=None, cwd=None):
    """Run the CLI as a subprocess. Returns (exit code, stdout, stderr)."""
    proc = subprocess.run(
        [sys.executable, str(SRC), *args],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=cwd or str(ROOT),
    )
    return proc.returncode, proc.stdout, proc.stderr


class TestTagProblem(unittest.TestCase):
    def test_good_tags_pass(self):
        for tag in [
            "v1.2.3",
            "v0.0.0",
            "v10.20.30",
            "v1.0.0-alpha",
            "v1.0.0-alpha.1",
            "v1.0.0-0.3.7",
            "v1.0.0-x-y-z.-",
            "v1.0.0+build.1",
            "v1.0.0-alpha+001",
        ]:
            with self.subTest(tag=tag):
                self.assertIsNone(gtc.tag_problem(tag), tag)

    def test_missing_v_prefix(self):
        self.assertEqual(
            gtc.tag_problem("1.2.3"), "missing 'v' prefix"
        )

    def test_allow_no_v(self):
        self.assertIsNone(gtc.tag_problem("1.2.3", allow_no_v=True))
        self.assertEqual(
            gtc.tag_problem("1.2.3", allow_no_v=False),
            "missing 'v' prefix",
        )
        self.assertIsNone(
            gtc.tag_problem("v1.2.3", allow_no_v=True)
        )

    def test_missing_parts(self):
        self.assertEqual(
            gtc.tag_problem("v1"), "missing minor and patch versions"
        )
        self.assertEqual(
            gtc.tag_problem("v1.2"), "missing patch version"
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.3.4"),
            "too many version parts — expected MAJOR.MINOR.PATCH",
        )

    def test_non_numeric_parts(self):
        self.assertEqual(
            gtc.tag_problem("v1.2.x"), "the patch version is not a number"
        )
        self.assertEqual(
            gtc.tag_problem("vx.2.3"), "the major version is not a number"
        )
        self.assertEqual(
            gtc.tag_problem("v1.y.3"), "the minor version is not a number"
        )

    def test_leading_zeros(self):
        self.assertEqual(
            gtc.tag_problem("v01.2.3"),
            "leading zero in the major version",
        )
        self.assertEqual(
            gtc.tag_problem("v1.02.3"),
            "leading zero in the minor version",
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.03"),
            "leading zero in the patch version",
        )

    def test_stray_tags(self):
        for tag in ["release-2", "latest", "V1.2.3", "v1.2.3 ", ""]:
            with self.subTest(tag=tag):
                reason = gtc.tag_problem(tag)
                self.assertIsNotNone(reason, tag)
        self.assertEqual(
            gtc.tag_problem("release-2"),
            "does not follow vMAJOR.MINOR.PATCH",
        )
        self.assertEqual(gtc.tag_problem(""), "empty tag name")

    def test_prerelease_problems(self):
        self.assertEqual(
            gtc.tag_problem("v1.2.3-"),
            "empty prerelease part",
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.3-alpha..1"),
            "empty identifier in the prerelease part",
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.3-01"),
            "leading zero in prerelease identifier '01'",
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.3-alpha_1"),
            "bad characters in the prerelease part",
        )

    def test_no_prerelease_flag(self):
        self.assertEqual(
            gtc.tag_problem("v1.2.3-alpha.1", no_prerelease=True),
            "prerelease tags are not allowed",
        )
        self.assertIsNone(
            gtc.tag_problem("v1.2.3", no_prerelease=True)
        )
        self.assertIsNone(
            gtc.tag_problem("v1.2.3+build.1", no_prerelease=True)
        )

    def test_build_metadata_problems(self):
        self.assertEqual(
            gtc.tag_problem("v1.2.3+"),
            "empty build metadata",
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.3+build..1"),
            "empty identifier in the build metadata",
        )
        self.assertEqual(
            gtc.tag_problem("v1.2.3+build_1"),
            "bad characters in the build metadata",
        )

    def test_duplicates(self):
        results = gtc.check_tags(["v1.2.3", "v1.2.4", "v1.2.3"])
        self.assertIsNone(results[0][1])
        self.assertIsNone(results[1][1])
        self.assertEqual(results[2][1], "duplicate tag")


class TestInputs(unittest.TestCase):
    def test_read_tag_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.txt"
            path.write_text(
                "# comment\n\nv1.2.3\n  v1.2  \n# another\n",
                encoding="utf-8",
            )
            tags, error = gtc.read_tag_file(str(path))
            self.assertIsNone(error)
            self.assertEqual(tags, ["v1.2.3", "v1.2"])

    def test_read_tag_file_missing(self):
        tags, error = gtc.read_tag_file("/no/such/tags.txt")
        self.assertIsNone(tags)
        self.assertIn("not found", error)

    def test_read_tag_file_not_utf8(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.txt"
            path.write_bytes(b"v1.2.3\n\xff\xfe\n")
            tags, error = gtc.read_tag_file(str(path))
            self.assertIsNone(tags)
            self.assertIn("UTF-8", error)

    def test_read_git_tags_real_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["git", "init", "-q", tmp], check=True
            )
            subprocess.run(
                ["git", "-C", tmp, "config", "user.email", "t@t.t"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", tmp, "config", "user.name", "Test"],
                check=True,
            )
            Path(tmp, "f.txt").write_text("x", encoding="utf-8")
            subprocess.run(
                ["git", "-C", tmp, "add", "."], check=True
            )
            subprocess.run(
                ["git", "-C", tmp, "commit", "-qm", "init"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", tmp, "tag", "v1.2.3"], check=True
            )
            subprocess.run(
                ["git", "-C", tmp, "tag", "v1.2"], check=True
            )
            tags, error = gtc.read_git_tags(tmp)
            self.assertIsNone(error)
            self.assertEqual(sorted(tags), ["v1.2", "v1.2.3"])
            results = gtc.check_tags(sorted(tags))
            self.assertEqual(
                results[0][1], "missing patch version"
            )
            self.assertIsNone(results[1][1])

    def test_read_git_tags_not_a_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            tags, error = gtc.read_git_tags(tmp)
            self.assertIsNone(tags)
            self.assertIsNotNone(error)


class TestCli(unittest.TestCase):
    def test_positional_pass_and_fail(self):
        code, out, err = run_cli("v1.2.3", "v1.2")
        self.assertEqual(code, 1)
        self.assertIn("PASS   v1.2.3", out)
        self.assertIn(
            "FAIL   v1.2: missing patch version", out
        )
        self.assertIn("2 checked, 1 passed, 1 failed", out)

    def test_all_pass_exit_zero(self):
        code, out, err = run_cli("v1.2.3", "v0.1.0")
        self.assertEqual(code, 0)
        self.assertIn("2 checked, 2 passed, 0 failed", out)

    def test_file_input(self):
        code, out, err = run_cli(
            "--file", "examples/tags.txt"
        )
        self.assertEqual(code, 1)
        self.assertIn("8 checked, 3 passed, 5 failed", out)

    def test_good_file_input(self):
        code, out, err = run_cli(
            "--file", "examples/good-tags.txt"
        )
        self.assertEqual(code, 0)
        self.assertIn("5 checked, 5 passed, 0 failed", out)

    def test_stdin_input(self):
        code, out, err = run_cli(
            "--stdin", input_text="v1.2.3\nrelease-2\n"
        )
        self.assertEqual(code, 1)
        self.assertIn("PASS   v1.2.3", out)
        self.assertIn(
            "FAIL   release-2: does not follow vMAJOR.MINOR.PATCH",
            out,
        )

    def test_git_input_in_real_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(
                ["git", "init", "-q", tmp], check=True
            )
            subprocess.run(
                ["git", "-C", tmp, "config", "user.email", "t@t.t"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", tmp, "config", "user.name", "Test"],
                check=True,
            )
            Path(tmp, "f.txt").write_text("x", encoding="utf-8")
            subprocess.run(
                ["git", "-C", tmp, "add", "."], check=True
            )
            subprocess.run(
                ["git", "-C", tmp, "commit", "-qm", "init"],
                check=True,
            )
            subprocess.run(
                ["git", "-C", tmp, "tag", "v1.2.3"], check=True
            )
            code, out, err = run_cli(
                "--git", "--repo", tmp
            )
            self.assertEqual(code, 0)
            self.assertIn("PASS   v1.2.3", out)
            self.assertIn("1 checked, 1 passed, 0 failed", out)

    def test_git_outside_repo_exit_two(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, out, err = run_cli(
                "--git", "--repo", tmp
            )
            self.assertEqual(code, 2)
            self.assertIn("not a git repo", err)

    def test_json_output(self):
        code, out, err = run_cli(
            "--json", "v1.2.3", "v1.2"
        )
        self.assertEqual(code, 1)
        data = json.loads(out)
        self.assertEqual(data["checked"], 2)
        self.assertEqual(data["passed"], 1)
        self.assertEqual(data["failed"], 1)
        self.assertTrue(data["results"][0]["passed"])
        self.assertEqual(
            data["results"][1]["reason"], "missing patch version"
        )

    def test_flags(self):
        code, out, err = run_cli("--allow-no-v", "1.2.3")
        self.assertEqual(code, 0)
        self.assertIn("PASS   1.2.3", out)
        code, out, err = run_cli(
            "--no-prerelease", "v1.2.3-alpha.1"
        )
        self.assertEqual(code, 1)
        self.assertIn("prerelease tags are not allowed", out)

    def test_version_flag(self):
        code, out, err = run_cli("--version")
        self.assertEqual(code, 0)
        self.assertIn("git-tag-checker-cli", out)

    def test_two_input_sources_exit_two(self):
        code, out, err = run_cli(
            "v1.2.3", "--file", "examples/tags.txt"
        )
        self.assertEqual(code, 2)
        self.assertIn("only one way", err)

    def test_missing_file_exit_two(self):
        code, out, err = run_cli("--file", "no-such.txt")
        self.assertEqual(code, 2)
        self.assertIn("not found", err)

    def test_no_tags_exit_two(self):
        code, out, err = run_cli("--stdin", input_text="")
        self.assertEqual(code, 2)
        self.assertIn("no tags to check", err)

    def test_bad_flag_exit_two(self):
        code, out, err = run_cli("--nope")
        self.assertEqual(code, 2)

    def test_input_file_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "tags.txt"
            before = "v1.2.3\nv1.2\n"
            path.write_text(before, encoding="utf-8")
            run_cli("--file", str(path))
            self.assertEqual(path.read_text(encoding="utf-8"), before)


class TestExamples(unittest.TestCase):
    def test_sample_output_matches_fresh_run(self):
        code, out, err = run_cli("--file", "examples/tags.txt")
        self.assertEqual(code, 1)
        saved = (ROOT / "examples" / "sample-output.txt").read_text(
            encoding="utf-8"
        )
        self.assertEqual(out, saved)

    def test_run_example_script(self):
        proc = subprocess.run(
            ["sh", "examples/run-example.sh"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("8 checked, 3 passed, 5 failed", proc.stdout)
        self.assertIn("5 checked, 5 passed, 0 failed", proc.stdout)
        self.assertIn("2 checked, 1 passed, 1 failed", proc.stdout)

    def test_readme_quoted_outputs(self):
        # Every line the README quotes from a real run must match
        # a fresh run of the same command.
        code, out, err = run_cli("v1.2.3")
        self.assertEqual(
            out,
            "PASS   v1.2.3\n1 checked, 1 passed, 0 failed\n",
        )
        code, out, err = run_cli("v1.2.3", "v1.2")
        self.assertEqual(
            out,
            "PASS   v1.2.3\n"
            "FAIL   v1.2: missing patch version\n"
            "2 checked, 1 passed, 1 failed\n",
        )
        code, out, err = run_cli(
            "--file", "examples/good-tags.txt"
        )
        self.assertEqual(
            out,
            "PASS   v1.2.3\n"
            "PASS   v0.1.0\n"
            "PASS   v10.20.30\n"
            "PASS   v2.0.0-alpha.1\n"
            "PASS   v1.0.0+build.1\n"
            "5 checked, 5 passed, 0 failed\n",
        )
        code, out, err = run_cli(
            "--allow-no-v", "--file", "examples/good-tags.txt"
        )
        self.assertEqual(code, 0)


class TestHygiene(unittest.TestCase):
    def test_stdlib_only(self):
        import ast

        allowed = {
            "argparse",
            "ast",
            "contextlib",
            "datetime",
            "json",
            "re",
            "subprocess",
            "sys",
            "pathlib",
            "os",
            "tempfile",
            "unittest",
        }
        for path in [SRC, Path(__file__)]:
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        self.assertIn(
                            alias.name.split(".")[0],
                            allowed | {"git_tag_checker"},
                            "%s imports %s" % (path, alias.name),
                        )
                elif isinstance(node, ast.ImportFrom):
                    self.assertIn(
                        (node.module or "").split(".")[0],
                        allowed | {"git_tag_checker"},
                        "%s imports %s" % (path, node.module),
                    )

    def test_no_placeholders_or_secrets(self):
        banned = ["TODO", "FIXME", "coming soon", "lorem", "API_KEY"]
        bad = []
        # The tests directory is excluded from this scan: the test
        # file itself names the banned words in its own check list.
        # The .git directory is excluded too: GitHub's checkout ships
        # sample hooks under .git/hooks/ that contain "TODO" (Day 21
        # CI failure), and those are git's own files, not this repo's.
        for path in ROOT.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            if "tests" in path.parts:
                continue
            text = path.read_text(
                encoding="utf-8", errors="ignore"
            )
            for word in banned:
                if word in text:
                    bad.append("%s: %s" % (path, word))
        self.assertEqual(bad, [])

    def test_gitignore_lists_env_first(self):
        lines = (ROOT / ".gitignore").read_text(
            encoding="utf-8"
        ).splitlines()
        self.assertEqual(lines[0], ".env")


if __name__ == "__main__":
    unittest.main()
