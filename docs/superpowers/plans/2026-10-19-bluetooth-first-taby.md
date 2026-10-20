# Bluetooth-first Taby Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the firmware's existing Bluetooth Low Energy protocol so Taby for macOS 1.0.13 can switch this Waveshare ESP32-S3 board from USB to Bluetooth, run every shipped animation and supported card interaction, remember the device, and recover after disconnects, restarts, and power loss without repeating setup.

**Architecture:** Keep USB as the one-time trusted setup, flashing, diagnostic, and recovery channel. Add the two missing protocol-2 GATT reads to the existing NimBLE service, continue routing every display command through the shared transport parser/runtime, and make the persisted transport preference transactional. The installed app remains responsible for remembering its CoreBluetooth peripheral and restoring persistent presentation state after reconnect; the firmware remains responsible for stable identity, durable Bluetooth preference, advertising, and safe recovery.

**Tech Stack:** ESP-IDF 5.4.2, ESP32-S3 NimBLE GATT, FreeRTOS, NVS, C11, Python 3 `unittest`, AddressSanitizer/UndefinedBehaviorSanitizer host drivers, installed Taby.app 1.0.13 native Bluetooth helper, esptool/pyserial, Waveshare ESP32-S3-Touch-AMOLED-1.64 V1.1/V2.

**Spec:** `docs/superpowers/specs/2026-10-19-bluetooth-first-taby-design.md`

## Global Constraints

- Deliver this candidate through the short-lived `feature/bluetooth-first` draft
  pull request requested by the owner on 2026-10-20. Do not add a GitHub Actions
  workflow; local verification remains authoritative.
- Preserve the existing UUIDs `0001`-`0005`, USB commands, reply shapes, board pins, partitions, and asset packs.
- Add choice on UUID suffix `0006` and identity on `0007`; do not reverse them.
- Map `choice_1` to `left`, `choice_2` to `right`, `none` to `none`, and legacy one-button `action` to `left`.
- "Paired" means the installed app remembers the CoreBluetooth peripheral ID plus the stable Taby device ID. This release does not add OS-level BLE bonding, a passkey, or encrypted GATT.
- Do not add or migrate NVS keys. The existing `taby_setup/done` and `taby_setup/pref` values remain the durable transport model.
- Never expose the device secret, Wi-Fi credentials, claim owner, logs, or factory data through BLE.
- The board cannot work while it has no power. After power is restored, it must boot the persisted Bluetooth preference and reconnect without USB setup.
- Removing USB while battery/alternate power is present must not stop BLE. Removing the only power source is expected to turn the board off; reconnection is tested after repower.
- Keep USB initialized even in Bluetooth mode so diagnosis, switching back to USB, and reflashing remain available.
- The app/API contract is verified against the owner's installed app for a personal compatibility build. A public/upstream release remains blocked on senior security/API-contract review.
- Never record full device IDs, credentials, private app data, or personal logs in committed files.

## Review Focus

- Exact protocol-2 UUID mapping and strict JSON shapes expected by Taby.app 1.0.13.
- NVS transaction ordering across power loss between `TRANSPORT_MODE bluetooth` and `TRANSPORT_DEFAULT bluetooth`.
- No false success when NVS commit, BLE initialization, GATT registration, or advertising fails.
- Disconnect versus intentional shutdown races: ordinary disconnect re-advertises; switching to USB does not.
- Full animation coverage from the checked-in manifest, including inferred `*_in>*_loop` pairs, with no BLE-only allowlist.
- Protocol success is not treated as proof of visible pixels; physical display observation remains a separate gate.
- One active Mac at a time and no claim of secure bonding.

---

## Task 1: Lock the protocol-2 payload contract in a pure host-tested module

**Files:**

- Create: `firmware/main/taby_ble_protocol_v2.h`
- Create: `firmware/main/taby_ble_protocol_v2.c`
- Create: `tests/host/ble_v2_driver.c`
- Create: `tests/test_ble_v2.py`
- Modify: `firmware/main/CMakeLists.txt`

- [x] **Step 1: Write the failing host tests**

  Add a sanitizer-built driver following `tests/host/protocol_driver.c`. Assert:

  - identity JSON decodes to exactly `protocol`, `deviceId`, and `firmwareVersion`;
  - `protocol` is integer `2`;
  - the device ID accepts only ASCII `[A-Za-z0-9._:-]`, length 1-120;
  - the firmware version is non-empty and at most 80 bytes;
  - null or undersized output buffers fail without returning a partial valid payload;
  - choice JSON decodes to exactly `signal` and `choice`;
  - `NONE -> none`, `CHOICE_1 -> left`, `CHOICE_2 -> right`, and `ACTION -> left`;
  - counter values `0` and `UINT32_MAX` round-trip exactly.

  Run:

  ```sh
  .venv/bin/python -m unittest tests.test_ble_v2 -v
  ```

  Expected: FAIL because the module does not exist.

- [x] **Step 2: Add the smallest pure interface**

  Declare:

  ```c
  #define TABY_BLE_PROTOCOL_VERSION 2U

  bool taby_ble_v2_identity_available(
      const char *device_id,
      const char *firmware_version);
  bool taby_ble_v2_format_identity_json(
      const char *device_id,
      const char *firmware_version,
      char *out,
      size_t out_size);
  bool taby_ble_v2_format_choice_json(
      uint32_t signal,
      taby_reusable_choice_selection_t selection,
      char *out,
      size_t out_size);
  ```

  Keep this module independent of NimBLE, FreeRTOS, NVS, and `cJSON`. Use bounded formatting and explicit length/result checks. Add the source to `firmware/main/CMakeLists.txt`.

- [x] **Step 3: Make the focused tests pass**

  Run:

  ```sh
  .venv/bin/python -m unittest tests.test_ble_v2 -v
  ```

  Expected: PASS, including sanitizer execution when the host compiler supports it.

- [x] **Step 4: Self-review and commit**

  Check that invalid input cannot produce an app-valid identity, no secret-bearing type enters the module, and `ACTION` maps to `left`.

  ```sh
  git diff --check
  git add firmware/main/taby_ble_protocol_v2.h firmware/main/taby_ble_protocol_v2.c firmware/main/CMakeLists.txt tests/host/ble_v2_driver.c tests/test_ble_v2.py
  git commit -m "test: lock bluetooth protocol v2 payloads"
  ```

## Task 2: Add the missing GATT characteristics and gate `bluetooth_v2`

**Files:**

- Modify: `firmware/main/taby_ble_transport.c`
- Modify: `firmware/main/taby_ble_transport.h`
- Modify: `firmware/main/taby_usb_serial.c`
- Modify: `tests/test_bluetooth_contract.py` (create if Task 1 used only `test_ble_v2.py`)

- [x] **Step 1: Add failing structural contract tests**

  Test that the firmware source/build contract contains:

  - read-only characteristic `54414259-0000-4000-a000-000000000006` for choice;
  - read-only characteristic `54414259-0000-4000-a000-000000000007` for identity;
  - existing `0002` command write, `0003` event notify, `0004` state read, and `0005` power read unchanged;
  - `bluetooth_v2` inserted exactly once into USB capabilities and only through `taby_ble_v2_identity_available()`.

  Run the new focused test and confirm it fails before editing production code.

- [x] **Step 2: Implement the identity read**

  Add an identity value handle and read callback. On `taby_ble_transport_init(identity)`, build a private bounded identity payload from `identity->device_id` and `taby_firmware_version()`. Refuse protocol-2 availability and set a clear internal error if it cannot be formatted. The callback must accept only `BLE_GATT_ACCESS_OP_READ_CHR` and append the full prepared payload once.

- [x] **Step 3: Implement the choice read**

  Add a choice value handle and read callback. Each read takes a fresh atomic snapshot through `taby_reusable_ui_read_choice_signal()`, formats it through the pure v2 module, does not consume/reset the signal, and appends one complete JSON payload.

- [x] **Step 4: Register `0006` and `0007` without changing older characteristics**

  Put choice then identity after power in `k_gatt_services`, both with `BLE_GATT_CHR_F_READ`. Reset their handles and cached payload state on shutdown. Preserve the existing advertised name unless the installed helper black-box test proves it incompatible.

- [x] **Step 5: Advertise the USB capability only for a usable identity**

  In `add_usb_capabilities()`, call `taby_identity_get()` and add `bluetooth_v2` only when `taby_ble_v2_identity_available(identity->device_id, taby_firmware_version())` returns true. Do not require BLE to be currently initialized; a USB-default device must announce that it can switch.

- [x] **Step 6: Run focused and existing protocol tests**

  ```sh
  .venv/bin/python -m unittest tests.test_ble_v2 tests.test_bluetooth_contract tests.test_protocol tests.test_device -v
  ```

  Expected: PASS.

- [x] **Step 7: Self-review and commit**

  Confirm the identity payload has no secret/claim/Wi-Fi fields and the capability cannot be reported for an invalid identity.

  ```sh
  git diff --check
  git add firmware/main/taby_ble_transport.c firmware/main/taby_ble_transport.h firmware/main/taby_usb_serial.c tests/test_bluetooth_contract.py
  git commit -m "feat: complete Taby bluetooth protocol v2"
  ```

## Task 3: Prove all manifest animations use the same BLE command path

**Files:**

- Modify: `tests/test_protocol.py`

- [x] **Step 1: Add a manifest-driven BLE reply test**

  For every animation in each board catalog, run the real shared handler with `prefix=""` and `echo=False`. Require `result == "applied"`, `animation_id == input`, and reply `OK ANIMATION`. Explicitly reject any response containing `unsupported_animation`.

- [x] **Step 2: Add inferred intro-to-loop coverage**

  Generate pairs at test time where a catalog ID ending in `_in` has a matching `_loop`. Send `intro>loop` through the BLE handler seam and require both IDs in the resolved command. Do not hard-code a second animation inventory.

- [x] **Step 3: Keep rejection nonfatal**

  Send an absent ID such as `dizzy_loop`, assert the existing successful `OK ... unsupported_animation` compatibility response, then send `confirmation` on the same driver session and require it to apply.

- [x] **Step 4: Run and commit**

  ```sh
  .venv/bin/python -m unittest tests.test_protocol -v
  git diff --check
  git add tests/test_protocol.py
  git commit -m "test: cover every animation through bluetooth commands"
  ```

## Task 4: Make transport preference writes atomic across power loss

**Files:**

- Modify: `firmware/main/taby_transport_prefs.c`
- Create: `tests/host/stubs/esp_check.h`
- Create: `tests/host/stubs/nvs.h`
- Create: `tests/host/transport_prefs_driver.c`
- Create: `tests/test_transport_prefs.py`

- [x] **Step 1: Write a fake-NVS failure matrix against the real prefs source**

  Compile `taby_transport_prefs.c` off-device with fake NVS functions. Cover blank storage, complete USB, complete Bluetooth, incomplete/pending values, out-of-range preference, and failures at open, first set, second set, and commit. Simulate reboot by discarding RAM state and loading the fake persisted bytes again.

- [x] **Step 2: State the required invariant in tests**

  Require:

  - before a successful commit, reboot loads the old durable default;
  - after successful commit, both `done=1` and `pref=bluetooth` reload together;
  - a failed commit returns an error and does not publish the candidate into the in-memory state reported by `INFO`;
  - all opened NVS handles close on success and error;
  - `done=1,pref=unknown` normalizes to safe first-run/USB recovery rather than hiding onboarding.

  Run and confirm RED:

  ```sh
  .venv/bin/python -m unittest tests.test_transport_prefs -v
  ```

- [x] **Step 3: Persist candidates before publishing RAM state**

  Replace `persist_state()` with a helper that accepts candidate values. Open NVS, set both candidate bytes, commit, close on every path, and only then assign `s_state.preferred_mode` and `s_state.onboarding_complete`. Keep the existing namespace and keys unchanged.

- [x] **Step 4: Normalize inconsistent loaded pairs**

  Validate the loaded complete/preference combination without adding a migration. Let the existing factory USB-default path handle a normalized unknown first-run state. Preserve the current pending-Wi-Fi semantics.

- [x] **Step 5: Run and commit**

  ```sh
  .venv/bin/python -m unittest tests.test_transport_prefs -v
  git diff --check
  git add firmware/main/taby_transport_prefs.c tests/host/stubs/esp_check.h tests/host/stubs/nvs.h tests/host/transport_prefs_driver.c tests/test_transport_prefs.py
  git commit -m "fix: make transport preference persistence atomic"
  ```

## Task 5: Harden boot, handoff, intentional shutdown, and re-advertising

**Files:**

- Modify: `firmware/main/app_main.c`
- Modify: `firmware/main/taby_onboarding.c`
- Modify: `firmware/main/taby_ble_transport.c`
- Modify: `tests/test_bluetooth_lifecycle.py`
- Create: `tests/host/bluetooth_lifecycle_driver.c` only if a pure transition seam is needed

- [x] **Step 1: Add failing policy/order tests**

  Cover these cases with the smallest host seam or source/build test that exercises behavior rather than duplicated constants:

  - boot starts BLE only for complete persisted Bluetooth, not `unknown` first-run;
  - `MODE bluetooth` starts BLE but writes no preference;
  - `DEFAULT bluetooth` starts/verifies BLE, commits Bluetooth, then reports success;
  - BLE-start failure does not commit;
  - commit failure reports error and leaves the prior durable/default state visible;
  - `MODE usb` intentionally shuts BLE down without changing the durable default;
  - `DEFAULT usb` commits USB first, then shuts BLE down, so interruption boots USB.

- [x] **Step 2: Tighten the boot condition**

  In `app_main.c`, start BLE only when `preferred_transport == TABY_TRANSPORT_PREF_BLUETOOTH` after validated preference loading. Keep USB initialization before BLE and preserve the factory USB shipping default.

- [x] **Step 3: Enforce handoff ordering**

  In `taby_onboarding_activate_transport_mode()` and `taby_onboarding_set_transport_default()`, implement the tested order. Never send a success reply until the relevant operation has completed. On Bluetooth preference commit failure, the current temporary BLE session may remain recoverable, but the durable/INFO state must remain the old value.

- [x] **Step 4: Guard intentional BLE shutdown**

  Add a desired-active/shutting-down guard. Ordinary disconnect and advertising-complete events re-advertise while desired-active. A disconnect triggered by `taby_ble_transport_shutdown()` must not restart advertising. Keep init/shutdown idempotent.

- [x] **Step 5: Retry transient advertising failures without blocking USB/display**

  Add a bounded one-shot retry/backoff for `ble_gap_adv_start()` failures while BLE remains desired-active and NimBLE is synced. Cancel it on successful advertising or intentional shutdown. A fatal NimBLE initialization failure remains visible through `bluetooth_error` and must leave USB/display usable.

- [x] **Step 6: Run and commit**

  ```sh
  .venv/bin/python -m unittest tests.test_bluetooth_lifecycle tests.test_transport_prefs tests.test_device -v
  git diff --check
  git add firmware/main/app_main.c firmware/main/taby_onboarding.c firmware/main/taby_ble_transport.c tests/test_bluetooth_lifecycle.py tests/host/bluetooth_lifecycle_driver.c
  git commit -m "fix: recover bluetooth across lifecycle changes"
  ```

  If no lifecycle driver is needed, omit its path from `git add`.

## Task 6: Black-box the flashed board with the installed native helper

**Files:**

- Create: `tests/test_ble_v2_helper.py`
- Create: `tests/hardware/README.md` if no hardware-test instructions file exists

- [x] **Step 1: Add an opt-in JSON-lines helper harness**

  Skip unless `TABY_BLE_HARDWARE=1`. Default to `/Applications/Taby.app/Contents/Resources/native/taby-bluetooth-probe`, spawn it as a subprocess, match replies by request ID, enforce timeouts, and terminate it cleanly in teardown.

- [x] **Step 2: Test discovery and identity**

  Exercise `scan`, `connect`, `state`, and `choice`. Require protocol 2, firmware version, and the same stable device ID captured from USB. Require choice to contain exactly `signal` and `choice` with an allowed choice value.

- [x] **Step 3: Test commands and connection retention**

  Send `confirmation`, a card, a timer, `DISPLAY_ORIENTATION?`, an unsupported animation, and another valid animation without reconnecting. Require expected acknowledgements and no helper crash/timeout.

- [x] **Step 4: Test a fresh-helper reconnect**

  Connect and capture the peripheral/device identity, close the helper, wait for re-advertising, launch a new helper, reconnect to the remembered peripheral, and send another command. Require the same device ID.

- [x] **Step 5: Add the real-board animation sweep**

  Load all 84 IDs from `assets/amoled-1.64/manifest.json`/catalog at runtime. Send each over the native helper, fail with the exact ID on timeout/rejection/`unsupported_animation`, and periodically read state to detect a silently lost link. Also send every inferred `*_in>*_loop` pair.

- [x] **Step 6: Validate skip behavior off-hardware and commit**

  ```sh
  .venv/bin/python -m unittest tests.test_ble_v2_helper -v
  git diff --check
  git add tests/test_ble_v2_helper.py tests/hardware/README.md
  git commit -m "test: add installed-app bluetooth hardware coverage"
  ```

  Omit `tests/hardware/README.md` from `git add` if the instructions belong in an existing file instead.

## Task 7: Run the complete local verification and build all boards

**Files:**

- Modify only if a failing check reveals a real implementation defect.

- [x] **Step 1: Run repository checks and all host tests**

  ```sh
  .venv/bin/python tools/check.py
  .venv/bin/python -m unittest discover -s tests -v
  ```

  Expected: all required checks pass; hardware tests skip without the opt-in environment variable.

- [x] **Step 2: Build all shared-code targets cleanly**

  ```sh
  source work/esp-idf-v5.4.2/export.sh
  python tools/build.py amoled-1.64
  python tools/build.py amoled-1.64-v2
  python tools/build.py round-1.32
  ```

  Expected: all three ESP-IDF builds succeed. Do not weaken warnings or remove older board support to make a build pass.

- [x] **Step 3: Review the complete diff**

  ```sh
  git status --short
  git diff --check
  git log --oneline --decorate -8
  ```

  Review UUIDs, JSON schemas, NVS ordering, shutdown guards, test coverage, and the absence of secrets or generated build artifacts.

## Task 8: Package, flash, and prove the one-time USB-to-BLE handoff

**Files:**

- Generated/ignored: `work/dist-bluetooth-v2/taby-amoled-1.64-v2/`
- Modify after results: `log.md`

- [ ] **Step 1: Package and inspect the V2 bundle**

  Use a fresh ignored output directory and inspect the bundle before flashing. Confirm it does not write NVS or factory identity partitions.

  ```sh
  python tools/package_release.py amoled-1.64-v2 --output work/dist-bluetooth-v2
  .venv/bin/python tools/install.py inspect \
    --board amoled-1.64-v2 \
    --bundle work/dist-bluetooth-v2/taby-amoled-1.64-v2
  ```

- [ ] **Step 2: Release the serial port and flash**

  Quit Taby.app only for the flash/serial phase. Resolve the current `/dev/cu.usbmodem*` port again because it may change. Flash the complete matching `amoled-1.64-v2` bundle and verify every image/hash with the existing installer. Never erase the full chip or alter eFuses.

- [ ] **Step 3: Verify USB identity and capability**

  Query `INFO`; require target `amoled-1.64-v2`, stable device ID, and exactly one `bluetooth_v2` capability. Record only a redacted ID suffix in logs.

- [ ] **Step 4: Exercise the app's atomic handoff**

  Open Taby.app, select Bluetooth once, and observe USB `TRANSPORT_MODE bluetooth` followed by `TRANSPORT_DEFAULT bluetooth`. Require the final success only after NVS commit and `INFO.preferred_transport == bluetooth`.

- [ ] **Step 5: Run the native-helper compatibility suite**

  Close the app so it does not own the single BLE slot, then run:

  ```sh
  TABY_BLE_HARDWARE=1 TABY_USB_DEVICE_ID="$TABY_DEVICE_ID" \
    .venv/bin/python -m unittest tests.test_ble_v2_helper -v
  ```

  Expected: discovery, protocol-2 handshake, choice/state, reconnect, all 84 IDs, and inferred sequences pass.

## Task 9: Validate visible animations and resilience on the physical board

**Files:**

- Modify after results: `log.md`
- Modify after results: `memory.md`

- [ ] **Step 1: Visually validate all animations**

  Run the manifest-derived 84-animation BLE sweep while watching or recording the AMOLED. For each ID, verify a visible first frame, motion, correct orientation, and loop/completion behavior. A protocol `OK` alone does not pass this step. After the sweep, show a card, accept a touch choice, clear it, and play idle again to expose decoder/heap degradation.

- [ ] **Step 2: Test app restart and ordinary disconnect**

  With a card, choice card, timer, and separate one-shot animation, quit/reopen Taby.app and toggle Mac Bluetooth. Require the same device identity, automatic re-advertising, no duplicate choice, and app-driven restoration of persistent/interactive state. Do not require replay of a completed one-shot.

- [ ] **Step 3: Test reset and restored power**

  Reset and cold-power-cycle the board in idle, on a card, during a timer, and during a command. After power returns, require Bluetooth to start from NVS without USB setup and the app to reconnect to the same identity. Note that the screen cannot operate during the outage.

- [ ] **Step 4: Test cable removal under both power conditions**

  With a charged/protected battery or safe alternate supply, remove USB while BLE is connected; require the session to continue or reconnect without preference loss. Separately remove USB when it is the only power; expect power-off, then require persisted Bluetooth reconnect after repower.

- [ ] **Step 5: Test safe battery-depletion recovery**

  Prefer a safe switched supply to simulate abrupt loss. Only perform a real battery run-down if the board/battery protection makes it safe; never intentionally over-discharge a LiPo. Recharge/repower and require the same identity, valid NVS, no boot loop, and Bluetooth reconnect.

- [ ] **Step 6: Test the second Mac when available**

  Explicitly release/disable Bluetooth on the personal Mac, select the same board on the work Mac, verify the same Taby device ID, issue a distinct animation/card, then hand back. Require one controller at a time. If the work Mac is unavailable, mark this one acceptance item pending rather than claiming it passed.

- [ ] **Step 7: Prove USB recovery**

  Send `TRANSPORT_DEFAULT usb`, reboot, confirm BLE does not advertise and USB still accepts commands/flashing, then restore Bluetooth default through the app and reboot once more.

## Task 10: Finish documentation, history, and draft-PR delivery

**Files:**

- Modify: `README.md`
- Modify: `firmware/README.md`
- Modify: `memory.md`
- Modify: `log.md`
- Modify: `docs/superpowers/specs/2026-10-19-bluetooth-first-taby-design.md`
- Modify: `docs/superpowers/plans/2026-10-19-bluetooth-first-taby.md`

- [x] **Step 1: Document supported Bluetooth behavior and limits**

  Explain one-time USB enablement, remembered app pairing, automatic boot/reconnect, recovery back to USB, one active Mac, features supported over BLE, features still USB-only, and the unbonded personal-test security limitation.

- [x] **Step 2: Record exact verification evidence**

  In `log.md`, record commands/results, app version, firmware commit, build targets, hardware tests, redacted device suffix, and any pending work-Mac or visual checks. In `memory.md`, replace the proposed/pending state with the actual current state and continuation instructions. Never add credentials or a full device identity.

- [x] **Step 3: Mark the plan accurately**

  Check off only completed steps. Do not label the feature complete if the screen sweep, lifecycle cases, or work-Mac acceptance remain pending.

- [x] **Step 4: Run the final verification gate again**

  ```sh
  .venv/bin/python tools/check.py
  .venv/bin/python -m unittest discover -s tests -v
  source work/esp-idf-v5.4.2/export.sh
  python tools/build.py amoled-1.64
  python tools/build.py amoled-1.64-v2
  python tools/build.py round-1.32
  git diff --check
  git status --short
  ```

- [x] **Step 5: Commit, push the feature branch, and open a draft PR**

  ```sh
  git add README.md firmware/README.md memory.md log.md docs/superpowers/specs/2026-10-19-bluetooth-first-taby-design.md docs/superpowers/plans/2026-10-19-bluetooth-first-taby.md
  git commit -m "docs: document bluetooth-first Taby"
  git push -u origin feature/bluetooth-first
  gh pr create --draft --base main --head feature/bluetooth-first
  ```

  Confirm the draft PR targets personal `main`, `upstream` remains the official
  repository, no workflow file was added, and no build artifacts or secrets are
  tracked. Merge only after the office-device acceptance gates are recorded.

## Definition of Done

- Taby.app 1.0.13 switches the board from USB to Bluetooth once and remembers it.
- Protocol 2 reads exact identity on `0007` and choice on `0006`.
- Every one of the 84 AMOLED animation IDs and every inferred intro/loop pair is accepted over the installed helper; visible physical output is separately confirmed.
- Cards, timers, clear/idle, choice touch, orientation, and ordinary reconnect work over BLE within the app's current Bluetooth feature set.
- Bluetooth preference and identity survive app restart, device reset, cable loss, power loss, and safe battery depletion once power is restored.
- A power interruption before default-commit retains the prior durable state; a successful default-commit makes Bluetooth start on every subsequent boot.
- USB recovery and reflashing remain functional.
- Personal and work Macs can use the same board one at a time; if the work Mac is unavailable, that single acceptance item is explicitly pending.
- Host tests, repository checks, all three firmware builds, flashed-board helper tests, and physical display checks are recorded truthfully.
- Documentation, `memory.md`, and `log.md` describe the candidate state; tested
  commits are pushed to a draft pull request for personal `main` with no GitHub
  Actions, and merge waits for the remaining hardware acceptance.
