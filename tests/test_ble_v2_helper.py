"""Installed Taby Bluetooth helper integration tests (real board is opt-in)."""

import json
import os
from pathlib import Path
import re
import select
import subprocess
import sys
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_HELPER = Path("/Applications/Taby.app/Contents/Resources/native/taby-bluetooth-probe")


FAKE_HELPER = r'''
import json
import sys
import time

for line in sys.stdin:
    request = json.loads(line)
    op = request["op"]
    if op == "quiet":
        time.sleep(5)
    elif op == "wrong_id":
        print(json.dumps({"id": request["id"] + 1, "ok": True, "result": "wrong"}), flush=True)
    elif op == "refuse" or request.get("command") == "taby_response_ready_in":
        print(json.dumps({"id": request["id"], "ok": False,
                          "error": "rejected_unsupported_animation"}), flush=True)
    else:
        print(json.dumps({"id": request["id"], "ok": True,
                          "result": {"op": op, "command": request.get("command")}}), flush=True)
'''

FAKE_RE_ADVERTISING_HELPER = r'''
import json
import sys

scans = 0
for line in sys.stdin:
    request = json.loads(line)
    if request["op"] == "scan":
        scans += 1
        result = ([{"peripheralId": "peripheral-A", "name": "Taby"}]
                  if sys.argv[1] == "delayed" and scans >= 3 else [])
    elif request["op"] == "connect":
        result = {"protocol": 2, "deviceId": "taby-usb-1", "firmwareVersion": "1.2.3"}
    else:
        raise AssertionError(request)
    print(json.dumps({"id": request["id"], "ok": True, "result": result}), flush=True)
'''


class HelperProtocolError(AssertionError):
    """The helper emitted a malformed or mismatched JSON-lines reply."""


class HelperRejected(AssertionError):
    """The helper or firmware rejected a request with a stable error code."""


class HelperProcess:
    """One live helper session, with bounded request/reply and process cleanup."""

    def __init__(self, command, timeout=20.0):
        self.process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, bufsize=0)
        self.timeout = timeout
        self.next_id = 0
        self.buffer = b""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def request(self, op, *, timeout=None, **fields):
        self.next_id += 1
        request_id = self.next_id
        payload = json.dumps({"id": request_id, "op": op, **fields}, separators=(",", ":"))
        try:
            self.process.stdin.write(payload.encode("utf-8") + b"\n")
            self.process.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            raise HelperProtocolError(f"{op}: helper exited before request {request_id}") from exc

        deadline = time.monotonic() + (self.timeout if timeout is None else timeout)
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"{op}: timed out waiting for request {request_id}")
            if not select.select([self.process.stdout], [], [], remaining)[0]:
                raise TimeoutError(f"{op}: timed out waiting for request {request_id}")
            chunk = os.read(self.process.stdout.fileno(), 4096)
            if not chunk:
                raise HelperProtocolError(f"{op}: helper exited before reply {request_id}")
            self.buffer += chunk
            if len(self.buffer) > 16_384:
                raise HelperProtocolError(f"{op}: oversized reply for request {request_id}")

        line, self.buffer = self.buffer.split(b"\n", 1)
        try:
            reply = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HelperProtocolError(f"{op}: invalid JSON for request {request_id}") from exc
        if not isinstance(reply, dict) or type(reply.get("id")) is not int or reply["id"] != request_id:
            raise HelperProtocolError(f"{op}: wrong request ID (expected {request_id})")
        if reply.get("ok") is True and set(reply) == {"id", "ok", "result"}:
            return reply["result"]
        if reply.get("ok") is False and set(reply) == {"id", "ok", "error"}:
            raise HelperRejected(f"{op}: {reply['error']}")
        raise HelperProtocolError(f"{op}: invalid reply shape for request {request_id}")

    def close(self):
        if self.process.poll() is None:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            try:
                self.process.wait(timeout=2.5)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=1)
        elif not self.process.stdin.closed:
            self.process.stdin.close()
        self.process.stdout.close()


def animation_ids_and_pairs():
    """Derive the current board's complete Bluetooth command sweep at runtime."""
    manifest_path = ROOT / "assets/amoled-1.64/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    catalog_path = manifest_path.parent / manifest["catalog"]["relative_path"]
    catalog = json.loads(catalog_path.read_text())
    ids = [item["id"] for item in manifest["animations"]]
    catalog_ids = [item["id"] for item in catalog["animations"]]
    if (len(ids) != 84 or len(set(ids)) != 84 or len(catalog_ids) != 84
            or set(ids) != set(catalog_ids)):
        raise AssertionError("amoled-1.64 manifest/catalog must agree on 84 unique animation IDs")
    id_set = set(ids)
    pairs = [(animation_id, animation_id[:-3] + "_loop")
             for animation_id in ids if animation_id.endswith("_in")
             and animation_id[:-3] + "_loop" in id_set]
    return ids, pairs


def send_animation(helper, animation_id):
    """Keep the exact animation command in a failed sweep's diagnostic."""
    try:
        result = helper.request("send", command=animation_id)
    except (HelperRejected, HelperProtocolError, TimeoutError) as exc:
        raise AssertionError(f"animation {animation_id}: {exc}") from exc
    if isinstance(result, str) and "unsupported_animation" in result:
        raise AssertionError(f"animation {animation_id}: {result}")
    return result


def wait_for_re_advertising(helper, peripheral_id, timeout=35.0, poll_interval=0.25):
    """Observe the remembered peripheral in a fresh helper's scan results."""
    deadline = time.monotonic() + timeout
    scans = 0
    last_seen = []
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            seen = ", ".join(last_seen) if last_seen else "none"
            raise TimeoutError(f"{peripheral_id} did not re-advertise after {scans} scans; "
                               f"last seen: {seen}")
        try:
            candidates = helper.request("scan", timeout=remaining)
        except TimeoutError as exc:
            raise TimeoutError(f"{peripheral_id} did not re-advertise after {scans} scans; "
                               "final scan timed out") from exc
        scans += 1
        if not isinstance(candidates, list):
            raise HelperProtocolError(f"scan returned non-list while waiting for {peripheral_id}")
        last_seen = []
        for candidate in candidates:
            if not isinstance(candidate, dict) or set(candidate) != {"peripheralId", "name"}:
                raise HelperProtocolError(f"scan returned invalid candidate while waiting for {peripheral_id}")
            last_seen.append(candidate["peripheralId"])
            if candidate == {"peripheralId": peripheral_id, "name": "Taby"}:
                return candidate
        time.sleep(min(poll_interval, max(0.0, deadline - time.monotonic())))


class HelperHarnessTests(unittest.TestCase):
    def test_requests_have_unique_ids_and_receive_their_own_replies(self):
        with HelperProcess([sys.executable, "-u", "-c", FAKE_HELPER]) as helper:
            self.assertEqual(helper.request("scan"), {"op": "scan", "command": None})
            self.assertEqual(helper.request("send", command="confirmation"),
                             {"op": "send", "command": "confirmation"})

    def test_wrong_reply_id_fails(self):
        with HelperProcess([sys.executable, "-u", "-c", FAKE_HELPER]) as helper:
            with self.assertRaisesRegex(HelperProtocolError, "request ID"):
                helper.request("wrong_id")

    def test_helper_refusal_is_not_success(self):
        with HelperProcess([sys.executable, "-u", "-c", FAKE_HELPER]) as helper:
            with self.assertRaisesRegex(HelperRejected, "unsupported_animation"):
                helper.request("refuse")

    def test_timeout_is_bounded_and_child_is_closed(self):
        helper = HelperProcess([sys.executable, "-u", "-c", FAKE_HELPER], timeout=0.2)
        try:
            with self.assertRaisesRegex(TimeoutError, "quiet"):
                helper.request("quiet")
        finally:
            helper.close()
        self.assertIsNotNone(helper.process.poll())

    def test_manifest_and_catalog_supply_all_ids_and_intro_loop_pairs(self):
        ids, pairs = animation_ids_and_pairs()
        self.assertEqual(len(ids), 84)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("confirmation", ids)
        self.assertIn(("taby_response_ready_in", "taby_response_ready_loop"), pairs)
        self.assertIn(("calendar_in", "calendar_loop"), pairs)

    def test_animation_rejection_names_the_exact_id(self):
        with HelperProcess([sys.executable, "-u", "-c", FAKE_HELPER]) as helper:
            with self.assertRaisesRegex(AssertionError, "taby_response_ready_in"):
                send_animation(helper, "taby_response_ready_in")

    def test_wait_for_readvertising_scans_until_same_peripheral_returns(self):
        with HelperProcess([sys.executable, "-u", "-c", FAKE_RE_ADVERTISING_HELPER,
                            "delayed"]) as helper:
            candidate = wait_for_re_advertising(helper, "peripheral-A", timeout=1,
                                                poll_interval=0.01)
            self.assertEqual(candidate, {"peripheralId": "peripheral-A", "name": "Taby"})
            self.assertEqual(helper.request("connect", peripheralId=candidate["peripheralId"]),
                             {"protocol": 2, "deviceId": "taby-usb-1",
                              "firmwareVersion": "1.2.3"})

    def test_wait_for_readvertising_times_out_with_peripheral_and_scan_count(self):
        with HelperProcess([sys.executable, "-u", "-c", FAKE_RE_ADVERTISING_HELPER,
                            "never"]) as helper:
            with self.assertRaisesRegex(TimeoutError, r"peripheral-A.*scans"):
                wait_for_re_advertising(helper, "peripheral-A", timeout=0.15,
                                        poll_interval=0.01)


@unittest.skipUnless(os.environ.get("TABY_BLE_HARDWARE") == "1",
                     "set TABY_BLE_HARDWARE=1 for the flashed-board helper sweep")
class InstalledHelperHardwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.expected_device_id = os.environ.get("TABY_USB_DEVICE_ID", "")
        if not re.fullmatch(r"[A-Za-z0-9._:-]{1,120}", cls.expected_device_id):
            raise AssertionError("Capture USB INFO.device_id and set TABY_USB_DEVICE_ID")
        cls.executable = Path(os.environ.get("TABY_BLE_HELPER", str(DEFAULT_HELPER)))
        if not cls.executable.is_file() or not os.access(cls.executable, os.X_OK):
            raise AssertionError(f"Installed Bluetooth helper is not executable: {cls.executable}")

    def setUp(self):
        self.helper = self.start_helper()

    def start_helper(self):
        helper = HelperProcess([str(self.executable)])
        self.addCleanup(helper.close)
        return helper

    def assert_identity(self, value):
        self.assertIs(type(value), dict, value)
        self.assertEqual(set(value), {"protocol", "deviceId", "firmwareVersion"}, value)
        self.assertIs(type(value["protocol"]), int, value)
        self.assertEqual(value["protocol"], 2, value)
        self.assertEqual(value["deviceId"], self.expected_device_id, value)
        self.assertIs(type(value["firmwareVersion"]), str, value)
        self.assertTrue(value["firmwareVersion"], value)
        self.assertLessEqual(len(value["firmwareVersion"].encode("utf-8")), 80, value)
        return value

    def assert_link(self, helper=None):
        return self.assert_identity((helper or self.helper).request("state"))

    def connect(self):
        candidates = self.helper.request("scan")
        self.assertIs(type(candidates), list, candidates)
        self.assertTrue(candidates, "scan found no Taby peripheral; confirm board is advertising")
        for candidate in candidates:
            self.assertEqual(set(candidate), {"peripheralId", "name"}, candidate)
            self.assertEqual(candidate["name"], "Taby", candidate)
            self.assertTrue(candidate["peripheralId"], candidate)
        selected = os.environ.get("TABY_BLE_PERIPHERAL_ID")
        if selected:
            matches = [candidate for candidate in candidates if candidate["peripheralId"] == selected]
            self.assertEqual(len(matches), 1, f"peripheral {selected} not found in scan")
        else:
            self.assertEqual(len(candidates), 1,
                             "Multiple Taby peripherals found; set TABY_BLE_PERIPHERAL_ID")
            matches = candidates
        peripheral_id = matches[0]["peripheralId"]
        self.assert_identity(self.helper.request("connect", peripheralId=peripheral_id))
        return peripheral_id

    def test_discovery_identity_state_and_choice(self):
        self.connect()
        self.assert_link()
        choice = self.helper.request("choice")
        self.assertIs(type(choice), dict, choice)
        self.assertEqual(set(choice), {"signal", "choice"}, choice)
        self.assertIs(type(choice["signal"]), int, choice)
        self.assertGreaterEqual(choice["signal"], 0, choice)
        self.assertIn(choice["choice"], {"none", "left", "right"}, choice)

    def test_commands_keep_one_connection_alive_after_a_refusal(self):
        self.connect()
        for command in ("confirmation", "UI/title_subtitle?hardware:HELLO|BLE TEST",
                        "UI/timer?hardware:FOCUS|60|60||run|0"):
            with self.subTest(command=command):
                self.helper.request("send", command=command)
                self.assert_link()
        orientation = self.helper.request("orientation", command="DISPLAY_ORIENTATION?")
        self.assertIs(type(orientation), str, orientation)
        self.assertRegex(orientation,
                         r"^OK DISPLAY_ORIENTATION (?:0|90|180|270) (?:auto|left|right|90|270) "
                         r"(?:left|right|90|270) [01] (?:round|rectangle)$")
        self.assert_link()
        with self.assertRaisesRegex(HelperRejected, "rejected_unsupported_animation"):
            self.helper.request("send", command="dizzy_loop")
        self.assert_link()
        self.helper.request("send", command="confirmation")
        self.assert_link()

    def test_fresh_helper_reconnects_to_remembered_peripheral(self):
        peripheral_id = self.connect()
        self.helper.close()
        fresh = self.start_helper()
        wait_for_re_advertising(fresh, peripheral_id)
        self.assert_identity(fresh.request("connect", peripheralId=peripheral_id))
        self.assert_link(fresh)
        fresh.request("send", command="confirmation")
        self.assert_link(fresh)

    def test_all_manifest_animations_and_intro_loop_pairs(self):
        self.connect()
        ids, pairs = animation_ids_and_pairs()
        for index, animation_id in enumerate(ids, 1):
            with self.subTest(animation_id=animation_id):
                send_animation(self.helper, animation_id)
                if index % 8 == 0 or index == len(ids):
                    try:
                        self.assert_link()
                    except (AssertionError, HelperRejected, HelperProtocolError, TimeoutError) as exc:
                        raise AssertionError(f"animation {animation_id}: link lost: {exc}") from exc
        for intro_id, loop_id in pairs:
            command = f"{intro_id}>{loop_id}"
            with self.subTest(animation_pair=command):
                send_animation(self.helper, command)
                try:
                    self.assert_link()
                except (AssertionError, HelperRejected, HelperProtocolError, TimeoutError) as exc:
                    raise AssertionError(f"animation {command}: link lost: {exc}") from exc


if __name__ == "__main__":
    unittest.main()
