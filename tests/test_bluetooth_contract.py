"""Host behavior check for Bluetooth v2 capability emission."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "firmware/main"
CAPABILITY_SOURCE = MAIN / "taby_usb_ble_v2_capability.c"


class UsbBleCapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("CC") or shutil.which("cc") or shutil.which("clang") or shutil.which("gcc")
        if not compiler:
            raise unittest.SkipTest("A C compiler is needed to test USB capability output")
        cls.build = Path(tempfile.mkdtemp(prefix="taby-usb-ble-capability-"))
        cls.driver = cls.build / "usb_ble_capability_driver"
        sources = [ROOT / "tests/host/usb_ble_capability_driver.c", MAIN / "taby_ble_protocol_v2.c"]
        if CAPABILITY_SOURCE.exists():
            sources.append(CAPABILITY_SOURCE)
        result = subprocess.run(
            [compiler, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
             f"-I{ROOT / 'tests/host/stubs'}", f"-I{MAIN}", "-o", str(cls.driver),
             *map(str, sources)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(f"host build failed:\n{result.stderr}")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.build, ignore_errors=True)

    def capability_count(self, device_id, firmware_version):
        result = subprocess.run([str(self.driver), device_id, firmware_version],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return int(result.stdout.strip())

    def test_valid_identity_adds_bluetooth_v2_once(self):
        self.assertEqual(self.capability_count("taby-01", "1.2.3"), 1)

    def test_invalid_identity_cannot_claim_bluetooth_v2(self):
        for device_id, version in (("", "1.2.3"), ("bad id", "1.2.3"),
                                   ("taby-01", ""), ("taby-01", "x" * 81),
                                   ("__NONTERMINATED__", "1.2.3")):
            with self.subTest(device_id=device_id, version=version[:16]):
                self.assertEqual(self.capability_count(device_id, version), 0)


if __name__ == "__main__":
    unittest.main()
