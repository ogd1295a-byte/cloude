"""Exercise the actual Git commands against a temporary local remote."""

from pathlib import Path
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "state_branch.sh"


class StateBranchTests(unittest.TestCase):
    def test_first_run_and_next_run_preserve_history(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def run(*args, cwd=root):
                return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

            run("git", "init", "--bare", "remote.git")
            run("git", "clone", str(root / "remote.git"), "first")
            first = root / "first"
            run("git", "checkout", "-b", "main", cwd=first)
            run("git", "config", "user.name", "Test", cwd=first)
            run("git", "config", "user.email", "test@example.com", cwd=first)
            (first / "program.txt").write_text("program stays on main\n")
            run("git", "add", ".", cwd=first)
            run("git", "commit", "-m", "Initial program", cwd=first)
            run("git", "push", "origin", "main", cwd=first)
            main_head = run("git", "rev-parse", "HEAD", cwd=first)

            for index in (1, 2):
                checkout = first
                if index == 2:
                    run("git", "clone", "--branch", "main", str(root / "remote.git"), "second")
                    checkout = root / "second"
                run("bash", str(SCRIPT), "prepare", cwd=checkout)
                state = checkout / ".state"
                self.assertFalse((state / "program.txt").exists())
                history = state / "history.jsonl"
                if index == 2:
                    self.assertEqual(history.read_text(), '{"run": 1}\n')
                (state / "status.json").write_text('{"notified": false}\n')
                with history.open("a") as stream:
                    stream.write(f'{{"run": {index}}}\n')
                run("bash", str(SCRIPT), "save", cwd=checkout)

            self.assertEqual(run("git", "--git-dir=remote.git", "rev-list", "--count", "state"), "2")
            self.assertEqual(run("git", "--git-dir=remote.git", "rev-parse", "main"), main_head)
            self.assertEqual(run("git", "--git-dir=remote.git", "ls-tree", "--name-only", "state"), "history.jsonl\nstatus.json")
