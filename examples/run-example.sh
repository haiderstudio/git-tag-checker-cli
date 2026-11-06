#!/bin/sh
# Run the checker on the bundled examples.
# Run from the repo root: sh examples/run-example.sh
# The check runs exit 1 because five example tags fail on purpose —
# that is the expected result here.
set -e
cd "$(dirname "$0")/.."
echo "--- check the sample list ---"
python3 src/git_tag_checker.py --file examples/tags.txt || true
echo "--- check the good list ---"
python3 src/git_tag_checker.py --file examples/good-tags.txt || true
echo "--- one good tag, one bad tag ---"
python3 src/git_tag_checker.py v1.2.3 v1.2 || true
