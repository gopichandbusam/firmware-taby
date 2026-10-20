"""Execute firmware lifecycle bodies with deterministic SDK boundaries.

Only function selection is textual: assertions observe executed C behavior, never
source spelling. Keeping the bodies verbatim avoids a parallel policy model and
avoids dragging display/LVGL and the entire NimBLE SDK into the host compiler.
"""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "firmware/main"


def function(source, name):
    match = re.search(r"^(?:static )?[\w *]+\b" + name + r"\s*\([^;]*?\)\s*\{", source, re.M)
    if not match:
        raise ValueError(f"Missing production function {name}")
    start = source.index("{", match.start())
    depth = 0
    for token in re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]', source[start:], re.S):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[match.start():start + token.end()] + "\n"
    raise ValueError(f"Unclosed production function {name}")


class BluetoothLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler = os.environ.get("CC") or shutil.which("cc")
        if not compiler:
            raise unittest.SkipTest("C compiler required")
        cls.build = Path(tempfile.mkdtemp(prefix="taby-lifecycle-"))
        cls.driver = cls.build / "lifecycle"
        ble = (MAIN / "taby_ble_transport.c").read_text()
        # Include production constants and state, not test copies of policy.
        globals_text = ble[ble.index("#define TABY_BLE_DEVICE_NAME_SIZE"):ble.index('#if __has_include')]
        functions = ["clear_last_error", "set_last_error", "set_last_event_payload", "publish_event_payload",
                     "notify_last_event_payload", "reset_transport_runtime_state", "build_device_name",
                     "gap_event_handler", "start_advertising", "on_sync", "on_reset",
                     "taby_ble_transport_init", "taby_ble_transport_shutdown",
                     "taby_ble_transport_ensure_advertising", "taby_ble_transport_is_ready",
                     "taby_ble_transport_is_advertising", "taby_ble_transport_is_connected",
                     "taby_ble_transport_device_name", "taby_ble_transport_last_error"]
        # Retry helpers are selected when present, including their real bodies.
        functions = re.findall(r"^static (?:void|bool|int) ((?:advertising_(?:retry|state)_\w+|start_advertising_locked|gap_event_handler_locked))\([^;]*?\)\s*\{", ble, re.M) + functions
        bodies = [function(ble, name) for name in functions]
        declarations = [body[:body.index("{")].rstrip() + ";\n" for body in bodies]
        onboarding = (MAIN / "taby_onboarding.c").read_text()
        bodies += [function(onboarding, name) for name in ["taby_onboarding_persist_transport_choice",
                   "taby_onboarding_activate_transport_mode", "taby_onboarding_set_transport_default"]]
        app = (MAIN / "app_main.c").read_text()
        bodies += [function(app, name) for name in ["apply_factory_usb_shipping_default_if_needed", "app_main"]]
        (cls.build / "production_lifecycle.h").write_text(globals_text + "\n".join(declarations + bodies))
        result = subprocess.run([compiler, "-std=gnu11", "-pthread", "-Wall", "-Wextra", "-Werror",
                                 "-Wno-unused-function", "-Wno-unused-variable", "-Wno-unused-parameter",
                                 "-g", "-O1", "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                                 f"-I{ROOT / 'tests/host/stubs'}", f"-I{MAIN}", f"-I{cls.build}",
                                 str(ROOT / "tests/host/bluetooth_lifecycle_driver.c"), "-o", str(cls.driver)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.build, ignore_errors=True)

    def run_case(self, case, pref=1, done=1, failure="none"):
        result = subprocess.run([str(self.driver), case, str(pref), str(done), failure], capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        return dict(field.split("=", 1) for field in result.stdout.strip().split())

    def test_boot_only_complete_persisted_bluetooth(self):
        for pref, done, expected in [(0, 0, "0"), (1, 1, "0"), (2, 1, "0"), (3, 0, "0"), (3, 1, "1"), (255, 1, "0")]:
            with self.subTest(pref=pref, done=done):
                result = self.run_case("boot", pref, done)
                self.assertEqual(result["starts"], expected)
                self.assertEqual(result["usb"], "1")
                self.assertEqual(result["display"], "1")
                self.assertEqual(result["onboarding"], "1")
                if expected == "1":
                    self.assertEqual(result["usb_before_ble"], "1")

    def test_factory_shipping_default_stays_usb(self):
        result = self.run_case("factory", 0, 0)
        self.assertEqual((result["starts"], result["durable"]), ("0", "1"))

    def test_mode_bluetooth_is_temporary(self):
        result = self.run_case("mode_bt")
        self.assertEqual((result["result"], result["starts"], result["commits"], result["durable"]), ("0", "1", "0", "1"))

    def test_default_bluetooth_starts_before_commit_and_success(self):
        result = self.run_case("default_bt")
        self.assertEqual((result["result"], result["durable"], result["live"], result["ready_at_commit"], result["shown"]), ("0", "3", "3", "1", "3"))

    def test_failed_bluetooth_start_never_commits_or_reports_success(self):
        result = self.run_case("default_bt", failure="init")
        self.assertNotEqual(result["result"], "0")
        self.assertEqual((result["commits"], result["live"], result["durable"], result["shown"]), ("0", "1", "1", "0"))
        self.assertIn("nimble_port_init_", result["error"])

    def test_host_launch_failure_never_commits_or_reports_success(self):
        result = self.run_case("default_bt", failure="host")
        self.assertNotEqual(result["result"], "0")
        self.assertEqual((result["ready"], result["durable"], result["commits"], result["shown"]), ("0", "1", "0", "0"))
        self.assertIn("host_task_create_failed", result["error"])

    def test_asynchronous_advertising_failure_keeps_valid_bluetooth_default(self):
        result = self.run_case("default_bt", failure="adv_once")
        self.assertEqual((result["result"], result["durable"], result["ready"], result["pending"]), ("0", "3", "1", "1"))
        self.assertIn("adv_start_rc_", result["error"])

    def test_each_synchronous_setup_failure_leaves_old_default_and_error(self):
        for failure in ("gatt", "name", "queue", "command_task", "retry_timer"):
            with self.subTest(failure=failure):
                result = self.run_case("default_bt", failure=failure)
                self.assertNotEqual(result["result"], "0")
                self.assertEqual((result["ready"], result["durable"], result["commits"], result["shown"]), ("0", "1", "0", "0"))
                self.assertNotEqual(result["error"], "none")

    def test_failed_bluetooth_commit_retains_durable_and_visible_default(self):
        result = self.run_case("default_bt", failure="commit")
        self.assertNotEqual(result["result"], "0")
        self.assertEqual((result["durable"], result["live"], result["ready"], result["shown"]), ("1", "1", "1", "0"))

    def test_mode_usb_stops_ble_without_persisting(self):
        result = self.run_case("mode_usb", 3)
        self.assertEqual((result["result"], result["ready"], result["stops"], result["commits"], result["durable"]), ("0", "0", "1", "0", "3"))

    def test_default_usb_commits_before_stopping(self):
        result = self.run_case("default_usb", 3)
        self.assertEqual((result["result"], result["durable"], result["ready"], result["pref_at_stop"]), ("0", "1", "0", "1"))

    def test_failed_usb_commit_keeps_bluetooth_running(self):
        result = self.run_case("default_usb", 3, failure="commit")
        self.assertNotEqual(result["result"], "0")
        self.assertEqual((result["ready"], result["durable"], result["stops"], result["shown"]), ("1", "3", "0", "0"))

    def test_usb_stop_failure_reports_error_but_default_remains_committed(self):
        result = self.run_case("default_usb", 3, failure="stop")
        self.assertNotEqual(result["result"], "0")
        self.assertEqual((result["durable"], result["shown"]), ("1", "0"))
        self.assertEqual(result["ready"], "0")
        self.assertIn("nimble_port_stop_rc_", result["error"])

    def test_ordinary_disconnect_and_advertising_complete_restart(self):
        for case in ("disconnect", "adv_complete", "connect_fail"):
            with self.subTest(case=case):
                result = self.run_case(case)
                self.assertEqual((result["adv_calls"], result["advertising"]), ("2", "1"))

    def test_intentional_stop_callbacks_never_restart_advertising(self):
        for case in ("shutdown_connected", "shutdown_advertising"):
            with self.subTest(case=case):
                result = self.run_case(case)
                self.assertEqual((result["adv_calls"], result["advertising"], result["ready"]), ("1", "0", "0"))

    def test_transient_failure_retries_asynchronously_and_recovers(self):
        result = self.run_case("retry", failure="adv_once")
        self.assertEqual((result["adv_calls"], result["advertising"], result["pending"], result["error"]), ("2", "1", "0", "none"))
        self.assertEqual(result["backoff"], "1")

    def test_retry_has_bounded_backoff_and_retains_error_on_exhaustion(self):
        result = self.run_case("retry", failure="adv_always")
        self.assertGreater(int(result["adv_calls"]), 1)
        self.assertLessEqual(int(result["adv_calls"]), 8)
        self.assertEqual((result["backoff"], result["pending"], result["advertising"]), ("1", "0", "0"))
        self.assertIn("adv_start_rc_", result["error"])

    def test_shutdown_cancels_pending_retry_and_stale_callback_is_harmless(self):
        result = self.run_case("cancel_retry", failure="adv_always")
        self.assertEqual((result["adv_calls"], result["pending"], result["ready"]), ("1", "0", "0"))

    def test_success_before_retry_deadline_cancels_timer(self):
        result = self.run_case("recover_early", failure="adv_once")
        self.assertEqual((result["adv_calls"], result["pending"], result["advertising"]), ("2", "0", "1"))

    def test_reset_suspends_retry_until_resync(self):
        result = self.run_case("reset_retry", failure="adv_once")
        self.assertEqual((result["before_resync"], result["adv_calls"], result["advertising"]), ("1", "2", "1"))

    def test_init_and_shutdown_are_idempotent_and_restartable(self):
        result = self.run_case("restart")
        self.assertEqual((result["starts"], result["stops"], result["ready"], result["advertising"]), ("2", "1", "1", "1"))

    def test_fatal_boot_ble_failure_preserves_usb_display_and_error(self):
        result = self.run_case("boot", 3, failure="init")
        self.assertEqual((result["usb"], result["display"], result["onboarding"], result["ready"]), ("1", "1", "1", "0"))
        self.assertIn("nimble_port_init_", result["error"])

    def test_shutdown_serializes_with_attempt_already_past_desired_guard(self):
        result = self.run_case("race_shutdown", failure="adv_once")
        self.assertEqual(result["starts_after_stop_intent"], "0")
        self.assertEqual((result["ready"], result["advertising"], result["controller_active"], result["pending"]), ("0", "0", "0", "0"))

    def test_host_retry_and_usb_ensure_do_not_start_advertising_twice(self):
        result = self.run_case("race_retry", failure="adv_once")
        self.assertEqual((result["adv_calls"], result["duplicates"]), ("2", "0"))
        self.assertEqual((result["advertising"], result["controller_active"], result["pending"], result["error"]), ("1", "1", "0", "none"))

    def test_usb_ensure_returns_without_waiting_for_inflight_host_retry(self):
        result = self.run_case("race_ensure", failure="adv_once")
        self.assertEqual(result["ensure_returned_while_paused"], "1")
        self.assertEqual((result["adv_calls"], result["duplicates"], result["advertising"]), ("2", "0", "1"))

    def test_delayed_shutdown_gap_callbacks_cannot_restart_advertising(self):
        result = self.run_case("delayed_shutdown")
        self.assertEqual((result["adv_calls"], result["advertising"], result["controller_active"], result["ready"]), ("1", "0", "0", "0"))

    def test_already_advertising_response_preserves_true_state_without_retry(self):
        result = self.run_case("mode_bt", failure="already")
        self.assertEqual((result["advertising"], result["controller_active"], result["pending"], result["error"]), ("1", "1", "0", "none"))

    def test_subscription_notification_allows_synchronous_notify_tx_reentry(self):
        result = self.run_case("subscribe_notify")
        self.assertEqual((result["notifications"], result["notify_tx_returned"], result["notification_payload"]), ("1", "1", "READY"))
        self.assertEqual((result["ready"], result["advertising"], result["adv_calls"], result["pending"]), ("1", "0", "1", "0"))
