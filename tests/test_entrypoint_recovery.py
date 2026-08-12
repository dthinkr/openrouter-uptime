"""The Railway collector must survive whatever the previous container left.

Nothing restarts it (restartPolicyType NEVER) and every cron tick mounts the
same volume, so a container that dies mid-git hands its wreckage to every run
after it. That is not hypothetical: a stale HEAD.lock took the collector down
and it stayed down for hours, invisibly, because the GitHub Actions collector
kept committing and the series only thinned rather than stopping.

These tests plant that wreckage and assert the entrypoint still reaches the
poll guard. They run against a local bare repo standing in for GitHub -- the
script takes a non-https REPO_URL verbatim precisely so this is possible.
"""

import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
ENTRYPOINT = ROOT / "railway" / "entrypoint.sh"

# Locks git takes on the paths this script touches. HEAD.lock is the one
# observed in production; the others are the same failure a different command
# away, and a guard wrapped around a single command would miss them.
LOCK_NAMES = ["HEAD.lock", "index.lock", "config.lock", "packed-refs.lock"]

GUARD_STUB = '#!/usr/bin/env python3\nprint("poll=false  last=0.0 min  test stub")\n'


def git(*args, cwd, **kw):
    return subprocess.run(("git",) + args, cwd=cwd, check=True,
                          capture_output=True, text=True, **kw)


class EntrypointRecoveryTest(unittest.TestCase):
    """Each test gets its own upstream and its own volume copy."""

    def setUp(self):
        self.tmp = pathlib.Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

        self.upstream = self.tmp / "upstream.git"
        git("init", "-q", "--bare", "-b", "main", str(self.upstream), cwd=self.tmp)

        seed = self.tmp / "seed"
        git("clone", "-q", str(self.upstream), str(seed), cwd=self.tmp)
        git("config", "user.email", "t@example.invalid", cwd=seed)
        git("config", "user.name", "t", cwd=seed)
        (seed / "scripts").mkdir()
        (seed / "status").mkdir()
        # Standing the guard down keeps these tests about volume recovery: the
        # run stops right after the worktree is prepared, so no network call
        # and no real poll is involved.
        guard = seed / "scripts" / "should_poll.py"
        guard.write_text(GUARD_STUB)
        guard.chmod(0o755)
        (seed / "status" / "latest.json").write_text("{}")
        git("add", "-A", cwd=seed)
        git("commit", "-qm", "seed", cwd=seed)
        git("push", "-q", "origin", "main", cwd=seed)

        self.workdir = self.tmp / "repo"
        git("clone", "-q", str(self.upstream), str(self.workdir), cwd=self.tmp)

    def run_entrypoint(self, script=None):
        # Resolved here rather than as a default argument: a default binds once
        # at definition time, which silently pins every run to one script and
        # makes the suite pass against a build it never executed.
        script = script or ENTRYPOINT
        env = {
            "PATH": os.environ["PATH"],
            "HOME": str(self.tmp),
            "REPO_URL": str(self.upstream),
            "BRANCH": "main",
            "WORKDIR": str(self.workdir),
        }
        return subprocess.run(["bash", str(script)], env=env,
                              capture_output=True, text=True)

    def assert_recovered(self, result, planted):
        self.assertEqual(
            result.returncode, 0,
            f"{planted} left the collector dead:\n{result.stdout}{result.stderr}")
        self.assertIn(
            "guard:", result.stdout,
            f"{planted} stopped the run before the poll guard:\n{result.stdout}")
        self.assertFalse(
            (self.workdir / ".git" / planted).exists(),
            f"{planted} was still on the volume after the run")

    def test_recovers_from_each_stale_lock(self):
        for name in LOCK_NAMES:
            with self.subTest(lock=name):
                self.setUp()
                (self.workdir / ".git" / name).touch()
                self.assert_recovered(self.run_entrypoint(), name)

    def test_clean_volume_is_untouched(self):
        """The recovery paths must not fire when there is nothing to recover."""
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("guard:", result.stdout)
        self.assertNotIn("removing stale git lock", result.stdout)
        self.assertNotIn("re-cloning", result.stdout)

    def test_recovers_when_the_old_copy_cannot_be_deleted(self):
        """Recovery must not depend on deleting the worktree in place.

        On the Railway volume `rm -rf /data/repo` failed with "Directory not
        empty" and, running under set -e, killed the run at the exact point it
        was meant to recover -- the collector stayed down for the rest of the
        afternoon. Here a root-owned undeletable entry stands in for whatever
        the volume was actually holding: the run has to survive it.
        """
        if os.geteuid() == 0:
            self.skipTest("root deletes everything; the trap cannot be set")
        # A file inside a directory with no write permission cannot be
        # unlinked, so any recovery that deletes before cloning fails here.
        stuck = self.workdir / "stuck"
        stuck.mkdir()
        (stuck / "pinned").write_text("x")
        stuck.chmod(0o500)
        # A successful recovery renames the worktree out from under this path,
        # so the trap may well be gone -- and taking it apart must not be what
        # decides the verdict either way.
        self.addCleanup(lambda: stuck.exists() and stuck.chmod(0o700))

        (self.workdir / ".git" / "HEAD").write_text("this is not a ref\n")
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("guard:", result.stdout)
        self.assertTrue((self.workdir / ".git" / "HEAD").read_text().startswith("ref:"),
                        "the worktree was never actually replaced")

    def test_recovers_from_unusable_repo(self):
        """Corruption the lock sweep cannot name still has to self-heal.

        Locks are the failure mode already seen. This stands in for the ones
        that have not happened yet: the volume is a cache of origin, so the
        entrypoint is expected to discard it rather than stay dead.
        """
        shutil.rmtree(self.workdir / ".git" / "refs")
        (self.workdir / ".git" / "HEAD").write_text("this is not a ref\n")
        result = self.run_entrypoint()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("re-cloning", result.stdout)
        self.assertIn("guard:", result.stdout)


if __name__ == "__main__":
    unittest.main()
