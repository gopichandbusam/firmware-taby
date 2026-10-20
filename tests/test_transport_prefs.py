"""Host contract for atomic transport preference writes through the real firmware source."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "firmware/main"
STUBS = ROOT / "tests/host/stubs"
DRIVER = ROOT / "tests/host/transport_prefs_driver.c"


class TransportPrefsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("CC") or shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if not compiler:
            raise unittest.SkipTest("A C compiler is needed to test transport preferences off-device")
        cls.build = Path(tempfile.mkdtemp(prefix="taby-transport-prefs-"))
        cls.driver = cls.build / "transport_prefs_driver"
        command = [compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
                   "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                   f"-I{STUBS}", f"-I{MAIN}", str(DRIVER), "-o", str(cls.driver)]
        built = subprocess.run(command, capture_output=True, text=True)
        if built.returncode != 0:
            raise AssertionError(f"host build of transport prefs failed:\n{built.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.build, ignore_errors=True)

    def run_case(self, done=-1, pref=-1, operation="set", candidate_pref=3,
                 candidate_done=1, failure="none"):
        result = subprocess.run([str(self.driver), str(done), str(pref), operation,
                                 str(candidate_pref), str(candidate_done), failure],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        fields = dict(part.split("=", 1) for part in result.stdout.strip().split())
        for key in ("before", "after", "durable", "reboot"):
            fields[key] = tuple(map(int, fields[key].split(",")))
        for key in ("result", "opens", "closes", "commits"):
            fields[key] = int(fields[key])
        return fields

    def assert_balanced_handles(self, actual):
        self.assertEqual(actual["opens"], actual["closes"])

    def test_blank_storage_commits_complete_bluetooth_as_one_pair(self):
        actual = self.run_case()
        self.assertEqual(actual["before"], (0, 0))
        self.assertEqual(actual["result"], 0)
        self.assertEqual(actual["after"], (1, 3))
        self.assertEqual(actual["durable"], (1, 3))
        self.assertEqual(actual["reboot"], (1, 3))
        self.assertEqual(actual["commits"], 1)
        self.assert_balanced_handles(actual)

    def test_complete_usb_and_bluetooth_reload_from_storage(self):
        for pref in (1, 3):
            with self.subTest(pref=pref):
                actual = self.run_case(1, pref, operation="set", candidate_pref=pref)
                self.assertEqual(actual["before"], (1, pref))
                self.assertEqual(actual["reboot"], (1, pref))
                self.assert_balanced_handles(actual)

    def test_incomplete_wifi_remains_pending_until_boot_reset(self):
        actual = self.run_case(0, 2, operation="reset")
        self.assertEqual(actual["before"], (0, 2))
        self.assertEqual(actual["after"], (0, 0))
        self.assertEqual(actual["reboot"], (0, 0))
        self.assert_balanced_handles(actual)

    def test_incomplete_usb_and_bluetooth_reset_to_first_run(self):
        for pref in (1, 3):
            with self.subTest(pref=pref):
                actual = self.run_case(0, pref, operation="reset")
                self.assertEqual(actual["before"], (0, pref))
                self.assertEqual(actual["reboot"], (0, 0))
                self.assert_balanced_handles(actual)

    def test_complete_unknown_and_out_of_range_preference_recover_as_first_run(self):
        for pref in (0, 255):
            with self.subTest(pref=pref):
                actual = self.run_case(1, pref, operation="set", candidate_pref=1)
                self.assertEqual(actual["before"], (0, 0))
                self.assertEqual(actual["after"], (1, 1))
                self.assertEqual(actual["reboot"], (1, 1))
                self.assert_balanced_handles(actual)

    def test_incomplete_out_of_range_preference_remains_first_run(self):
        actual = self.run_case(0, 255, operation="reset")
        self.assertEqual(actual["before"], (0, 0))
        self.assertEqual(actual["after"], (0, 0))
        self.assertEqual(actual["durable"], (0, 255))
        self.assert_balanced_handles(actual)

    def test_each_failed_write_keeps_old_durable_and_live_usb_state(self):
        for failure in ("open", "first_set", "second_set", "commit"):
            with self.subTest(failure=failure):
                actual = self.run_case(1, 1, failure=failure)
                self.assertNotEqual(actual["result"], 0)
                self.assertEqual(actual["before"], (1, 1))
                self.assertEqual(actual["after"], (1, 1))
                self.assertEqual(actual["durable"], (1, 1))
                self.assertEqual(actual["reboot"], (1, 1))
                self.assertEqual(actual["commits"], 0)
                self.assert_balanced_handles(actual)

    def test_failed_blank_write_reboots_to_old_first_run_state(self):
        for failure in ("open", "first_set", "second_set", "commit"):
            with self.subTest(failure=failure):
                actual = self.run_case(failure=failure)
                self.assertNotEqual(actual["result"], 0)
                self.assertEqual(actual["before"], (0, 0))
                self.assertEqual(actual["after"], (0, 0))
                self.assertEqual(actual["durable"], (-1, -1))
                self.assertEqual(actual["reboot"], (0, 0))
                self.assert_balanced_handles(actual)

    def test_failed_clear_does_not_publish_unknown_state(self):
        actual = self.run_case(1, 3, operation="clear", failure="commit")
        self.assertNotEqual(actual["result"], 0)
        self.assertEqual(actual["after"], (1, 3))
        self.assertEqual(actual["reboot"], (1, 3))
        self.assert_balanced_handles(actual)

    def test_failed_boot_reset_keeps_pending_wifi_in_ram_and_storage(self):
        actual = self.run_case(0, 2, operation="reset", failure="commit")
        self.assertNotEqual(actual["result"], 0)
        self.assertEqual(actual["after"], (0, 2))
        self.assertEqual(actual["reboot"], (0, 2))
        self.assert_balanced_handles(actual)


if __name__ == "__main__":
    unittest.main()
