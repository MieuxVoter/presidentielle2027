# coding: utf-8

import pathlib
import re
import subprocess
import sys

"""
Script run example :

pytest . | python3 src/repair/end_date.py
"""

SCRIPT_DIR = pathlib.Path(__file__).parent.resolve()
PROJECT_DIR = SCRIPT_DIR.parent.parent
POLLS_PATH = PROJECT_DIR / "polls.csv"
POLLS_DIR = PROJECT_DIR / "polls"

REGEX = re.compile(
    r"^SKIPPED.+tests/test_poll_consistency\.py.+(([0-9]{8}_)([0-9]{2})([0-9]{2})(_[a-z]+_2?[A-Z])) spells its end date DDMM$"
)


def git_mv(source, dest):
    subprocess.check_output(["git", "mv", source, dest])


with POLLS_PATH.open("r+") as polls_file:
    polls_content = polls_file.read()
    for line in sys.stdin:
        # If line matches targeted error
        match_res = REGEX.match(line)
        if match_res:
            # Replace content in polls.csv
            new_name = f"{match_res.group(2)}{match_res.group(4)}{match_res.group(3)}{match_res.group(5)}"
            polls_content = polls_content.replace(match_res.group(1), new_name)

            old_name = (POLLS_DIR / match_res.group(1)).with_suffix(".csv")
            new_path = (POLLS_DIR / new_name).with_suffix(".csv")

            # git mv in polls/
            git_mv(old_name, new_path)

    # Update polls.csv
    polls_file.seek(0)
    polls_file.write(polls_content)
