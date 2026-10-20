"""Host tests for the exact BLE protocol-v2 identity and choice JSON contract."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "firmware/main"
SOURCES = [ROOT / "tests/host/ble_v2_driver.c", MAIN / "taby_ble_protocol_v2.c"]
FLAGS = ["-std=gnu11", "-Wall", "-Wextra", "-Werror", "-g", "-O1",
         "-fno-omit-frame-pointer", f"-I{MAIN}"]
SANITIZERS = ["-fsanitize=address,undefined", "-fno-sanitize-recover=all"]


class BleV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("CC") or shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if not compiler:
            raise unittest.SkipTest("A C compiler is needed to test BLE payloads off-device")
        cls.build = Path(tempfile.mkdtemp(prefix="taby-ble-v2-"))
        cls.driver = cls.build / "ble_v2_driver"
        base = [compiler, *FLAGS, "-o", str(cls.driver), *map(str, SOURCES)]
        built = subprocess.run(base[:1] + SANITIZERS + base[1:], capture_output=True, text=True)
        cls.sanitized = built.returncode == 0
        if not cls.sanitized:
            built = subprocess.run(base, capture_output=True, text=True)
        if built.returncode != 0:
            raise AssertionError(f"host build of BLE v2 payloads failed:\n{built.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.build, ignore_errors=True)

    def run_driver(self, *args):
        result = subprocess.run([str(self.driver), *map(str, args)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.rstrip("\n")

    def identity(self, device_id="taby-01", version="1.2.3", size=512,
                 null_id=False, null_version=False, null_out=False):
        reply = self.run_driver("identity", device_id, version, size,
                                "null" if null_id else "value",
                                "null" if null_version else "value",
                                "null" if null_out else "value")
        ok, payload = reply.split("\t", 1)
        return ok == "1", payload

    def choice(self, signal, selection, size=512, null_out=False):
        reply = self.run_driver("choice", signal, selection, size,
                                "null" if null_out else "value")
        ok, payload = reply.split("\t", 1)
        return ok == "1", payload

    def test_identity_has_only_the_three_contract_fields_and_integer_protocol_two(self):
        ok, payload = self.identity("taby-01", "1.2.3")
        self.assertTrue(ok)
        decoded = json.loads(payload)
        self.assertEqual(decoded, {"protocol": 2, "deviceId": "taby-01", "firmwareVersion": "1.2.3"})
        self.assertIs(type(decoded["protocol"]), int)

    def test_device_id_accepts_exact_ascii_alphabet_and_length_bounds(self):
        for device_id in ("A", "aZ09._:-", "x" * 120):
            with self.subTest(device_id=device_id[:16]):
                self.assertEqual(self.run_driver("available", device_id, "v", "value", "value"), "1")
                ok, payload = self.identity(device_id, "v")
                self.assertTrue(ok)
                self.assertEqual(json.loads(payload)["deviceId"], device_id)
        for device_id in ("", "x" * 121, "bad id", "a/b", 'a"b', "a\\b", "é", "\n"):
            with self.subTest(device_id=device_id[:16]):
                self.assertEqual(self.run_driver("available", device_id, "v", "value", "value"), "0")
                self.assertEqual(self.identity(device_id, "v"), (False, ""))

    def test_firmware_version_must_be_nonempty_and_at_most_eighty_bytes(self):
        ok, payload = self.identity(version="x" * 80)
        self.assertTrue(ok)
        self.assertEqual(json.loads(payload)["firmwareVersion"], "x" * 80)
        for version in ("", "x" * 81, "é" * 41):
            with self.subTest(version=version[:16]):
                self.assertEqual(self.run_driver("available", "id", version, "value", "value"), "0")
                self.assertEqual(self.identity("id", version), (False, ""))

    def test_firmware_version_json_escapes_special_characters(self):
        version = 'v"\\\n\t'
        ok, payload = self.identity(version=version)
        self.assertTrue(ok)
        self.assertEqual(json.loads(payload)["firmwareVersion"], version)

    def test_null_inputs_and_output_cannot_return_identity_payload(self):
        for options in ({"null_id": True}, {"null_version": True}, {"null_out": True}):
            with self.subTest(options=options):
                self.assertEqual(self.identity(**options), (False, ""))
        self.assertEqual(self.run_driver("available", "id", "v", "null", "value"), "0")
        self.assertEqual(self.run_driver("available", "id", "v", "value", "null"), "0")

    def test_undersized_identity_buffer_fails_without_partial_json(self):
        ok, payload = self.identity("id", "v")
        self.assertTrue(ok)
        for size in (0, 1, len(payload)):
            with self.subTest(size=size):
                self.assertEqual(self.identity("id", "v", size=size), (False, ""))
        self.assertEqual(self.identity("id", "v", size=len(payload) + 1), (True, payload))

    def test_choice_has_only_signal_and_choice_with_expected_selection_mapping(self):
        for selection, expected in ((0, "none"), (1, "left"), (2, "right"), (3, "left")):
            with self.subTest(selection=selection):
                ok, payload = self.choice(7, selection)
                self.assertTrue(ok)
                decoded = json.loads(payload)
                self.assertEqual(decoded, {"signal": 7, "choice": expected})
                self.assertIs(type(decoded["signal"]), int)

    def test_choice_counter_round_trips_zero_and_uint32_max(self):
        for signal in (0, 4294967295):
            with self.subTest(signal=signal):
                ok, payload = self.choice(signal, 1)
                self.assertTrue(ok)
                self.assertEqual(json.loads(payload), {"signal": signal, "choice": "left"})

    def test_choice_rejects_invalid_selection_and_undersized_output(self):
        self.assertEqual(self.choice(3, 99), (False, ""))
        self.assertEqual(self.choice(3, 1, null_out=True), (False, ""))
        ok, payload = self.choice(3, 1)
        self.assertTrue(ok)
        for size in (0, 1, len(payload)):
            with self.subTest(size=size):
                self.assertEqual(self.choice(3, 1, size=size), (False, ""))
        self.assertEqual(self.choice(3, 1, size=len(payload) + 1), (True, payload))


if __name__ == "__main__":
    unittest.main()
