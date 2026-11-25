import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from catalog.dco import check, valid_signoff


class DCOTests(unittest.TestCase):
    def test_requires_matching_author_in_final_trailer_block(self):
        self.assertTrue(valid_signoff("Change\n\nSigned-off-by: Pat <pat@example.test>\n", "Pat", "pat@example.test"))
        self.assertFalse(valid_signoff("Signed-off-by: Pat <pat@example.test>\n\nUnrelated body", "Pat", "pat@example.test"))
        self.assertFalse(valid_signoff("Change\n\nSigned-off-by: Other <other@example.test>", "Pat", "pat@example.test"))
        self.assertFalse(valid_signoff("Signed-off-by: Pat <pat@example.test>", "Pat", "pat@example.test"))

    def test_checks_all_pr_commits_and_rejects_empty_ranges(self):
        with tempfile.TemporaryDirectory() as tmp:
            previous = Path.cwd()
            try:
                os.chdir(tmp)
                def git(*args):
                    return subprocess.check_output(["git", *args], text=True, stderr=subprocess.DEVNULL).strip()
                git("init", "-b", "main")
                git("config", "user.name", "Pat")
                git("config", "user.email", "pat@example.test")
                git("-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "Base")
                base = git("rev-parse", "HEAD")
                git("-c", "commit.gpgsign=false", "commit", "--allow-empty", "-m", "Unsigned first contribution")
                git("-c", "commit.gpgsign=false", "commit", "--allow-empty", "-s", "-m", "Signed latest contribution")
                head = git("rev-parse", "HEAD")
                with self.assertRaisesRegex(ValueError, "Missing"):
                    check(base, head)
                self.assertEqual(check(git("rev-parse", "HEAD~1"), head), 1)
                with self.assertRaisesRegex(ValueError, "empty"):
                    check(head, head)
            finally:
                os.chdir(previous)

    def test_rejects_option_injection(self):
        with self.assertRaises(ValueError):
            check("--all", "a" * 40)
