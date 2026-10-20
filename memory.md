# Taby project memory

Last updated: 2026-10-20

## Goal

Install the official Physical Taby firmware on a connected Waveshare
ESP32-S3-Touch-AMOLED-1.64, verify the display with an animation, and connect it
to the Taby desktop app. Preserve enough context to continue on another
computer or improve the project later.

## Current state

- Primary repository: `gopichandbusam/firmware-taby`. The personal fork is
  local remote `origin`; the original `TRIIIS-LABS/firmware-taby` repository is
  remote `upstream`.
- The Bluetooth-first work is on `feature/bluetooth-first` for a draft pull
  request into the personal fork's `main`, at the owner's explicit request for
  office-device review. The fork still has no GitHub Actions workflow and
  Actions remain disabled.
- Connected hardware was detected by macOS as an ESP32-S3 native USB
  Serial/JTAG device. The exact `/dev/cu.usbmodem...` name is machine-specific
  and may change after reset or when moving to another computer.
- The board is new or running the Waveshare vendor demo. The read-only
  `tools/device.py identify` command returned `No Taby response`, which is
  expected before the first Taby installation.
- Python communication tools are installed in the repository-local `.venv`:
  esptool 4.11.0 and pyserial 3.5.
- Official firmware release v1.2.0 for `amoled-1.64` was downloaded to the
  ignored `work/` directory. Its SHA-256 and bundle inspection passed. That V1
  build was useful for diagnosis but does not drive the newer panel correctly.
- The installed macOS desktop app is Taby 1.0.13 (`com.heytaby.desktop`). It was
  closed during USB preparation so it did not claim the serial port.
- The PCB marking could not be located. On 2026-10-19, the owner explicitly
  authorized a provisional V1 firmware test despite the unresolved revision.
  Display validation is therefore required after flashing; do not treat USB
  metadata or protocol verification as proof of hardware compatibility.
- The complete official V1 bundle was flashed successfully, but its screen
  stayed blank. Serial diagnostics showed successful rendering, which isolated
  the failure to the physical panel control path.
- Serial diagnostics show the firmware loading the asset pack and reporting a
  successful render of `idle_01_loop`; USB/device logic is running while the
  physical panel produces no visible output.
- The Taby desktop app reports `Physical Taby Connected`, and the device now
  reports USB onboarding complete. The app connection does not validate the
  display wiring.
- The evidence matches the newer Waveshare V1.1 PCB: released V1 firmware drives
  LCD chip select on GPIO9, while V1.1 uses GPIO46. The repository and upstream
  pull request #9 call this newer revision `amoled-1.64-v2`.
- A separate `amoled-1.64-v2` development target is now implemented locally. It
  preserves the original V1 GPIO9 target, reuses the existing asset pack, and
  selects GPIO46 only for V1.1/V2.
- ESP-IDF 5.4.2 is installed under ignored `work/esp-idf-v5.4.2`; the required
  host tools CMake and Ninja were installed with Homebrew.
- The original V2-board work passed its then-current repository suite and clean
  builds for all three targets. The later Bluetooth candidate at `1803bef`
  passed `tools/check.py` and 123 host tests (118 passed, five expected hardware
  skips); the corrected V2 target also rebuilt, packaged, and inspected.
- The custom bundle was flashed successfully. Every image hash verified, and
  post-flash USB verification reports firmware `1.2.0`, assets `0.3.3`, target
  `amoled-1.64-v2`, rectangle `280 x 456`, and `usb_bridge_ready: true`.
- The device accepted `idle_01_loop`, and Taby 1.0.13 reports `Physical Taby
  Connected`. Physical screen visibility still requires the owner's direct
  confirmation; a successful USB response is not proof of visible pixels.
- The owner approved the Bluetooth-first compatibility design on 2026-10-19 at
  `docs/superpowers/specs/2026-10-19-bluetooth-first-taby-design.md`. The
  installed Taby 1.0.13 contains USB and BLE transports but no Wi-Fi physical
  transport. The firmware now implements its BLE protocol 2 contract: choice
  JSON on GATT UUID suffix `0006`, identity JSON on `0007`, and the gated USB
  `bluetooth_v2` capability, while preserving suffixes `0002`-`0005`.
- The approved first wireless release keeps one-time USB setup/update/recovery,
  then uses BLE for animations, cards, timers, clear, choices, orientation, and
  reconnect. Wi-Fi is deferred because it needs Mac app work and authenticated
  local control.
- The implementation plan is at
  `docs/superpowers/plans/2026-10-19-bluetooth-first-taby.md`. Tasks 1-7 are
  implemented with host coverage for protocol payloads, all manifest
  animations, atomic preference writes, advertising/reconnect lifecycle, and
  the installed-helper harness. USB remains initialized for recovery.
- A reviewed build at `f0a08cc` was flashed successfully and proved stable USB
  identity, the `bluetooth_v2` capability, atomic Bluetooth-default handoff,
  and preference restoration after reset. Its real-helper BLE tests stopped at
  macOS Bluetooth privacy authorization before discovery.
- A later compiled-byte test found and fixed the identity UUID at `1803bef`.
  All host tests and the corrected V2 build/package passed, but the connected
  board stopped responding before the corrected image could be flashed. No
  flash data was written by those failed connection attempts, so the earlier
  image remains installed.
- macOS System Settings on the personal Mac now visibly shows Bluetooth access
  enabled for both ChatGPT/Codex and Taby, but no successful BLE connection was
  established. Permission is per Mac and must be checked again at the office.
  The helper suite has not yet been rerun because the current board no longer
  answers serial commands. The corrected build still needs office-device
  flashing and BLE/visual/lifecycle acceptance.
- The 2026-10-20 pre-PR gate passed from the candidate tree: repository checks,
  123 host tests (118 passed, five expected skips), and ESP-IDF builds for all
  three targets. These results verify source/build compatibility, not physical
  BLE or visible display behavior.
- Draft PR #2 is the office-test handoff:
  `https://github.com/gopichandbusam/firmware-taby/pull/2`. Do not merge it until
  the pending physical checks are recorded.
- The repository and PR preserve all three current board targets and the old
  v1.0.8, v1.1.0, and v1.2.0 tags. Upstream historical downloads exist for the
  original 1.64 V1 and round boards; there is no historical V2 bundle.
- Clean candidate bundles for original 1.64 V1, newer 1.64 V1.1/V2, and round
  1.32 were packaged and inspected from `43878ff`. They are ignored local test
  artifacts, not files committed to the PR. The candidate still reports
  firmware `1.2.0`, so match its manifest commit during office testing and
  choose a distinct version before publishing binaries.
- "Paired" for this personal compatibility build means Taby.app remembers the
  CoreBluetooth peripheral ID plus the stable device ID; Taby 1.0.13 does not
  perform OS-level BLE bonding/passkey pairing. The board cannot operate while
  unpowered, but must return to persisted Bluetooth mode after power returns.

## Hardware revision notes

The official firmware v1.2.0 release supports only the Waveshare 1.64-inch
**V1** PCB. Waveshare calls the newer board **V1.1**; this local development
target follows the existing repository/upstream name **V2**.

- Supported V1: revision silkscreen is at the top of the PCB and LCD chip
  select is GPIO9.
- V1.1 / local V2 target: revision silkscreen is on the right side near the pin
  headers and LCD chip select is GPIO46.

Do not infer PCB revision from the USB ID, ESP32 chip ID, screen size, or flash
size. Select the target from the physical PCB marking or known purchase revision.

## Next steps

1. Review the draft pull request from `feature/bluetooth-first` into the
   personal fork's `main`; do not merge it merely because host/build checks pass.
2. The personal test board now runs the inspected V2 bundle from commit
   `7590388`: firmware `1.2.0`, assets `0.3.3`, target `amoled-1.64-v2`.
   Flash hashes, direct USB `INFO`, a `confirmation` animation command, visible
   animation output, and Taby.app USB detection all passed. Use this exact
   source commit when comparing office-device results.
3. Run the installed-app/helper BLE tests after confirming macOS Bluetooth
   access for Taby; record only a redacted device-ID suffix.
4. Physically validate the full manifest-driven animation sweep and lifecycle
   recovery; do not treat protocol acceptance as proof of visible output.
5. Test the work-Mac handoff when that computer is available.
6. Finish the desktop app's separate Brain download only when the owner wants
   the local AI features; it is not required for firmware or USB detection.
7. Before a public/upstream Bluetooth release, obtain security/API-contract
   review because Taby 1.0.13 expects unbonded BLE protocol 2.
8. On the other work computer, check out the pull-request branch, run
   `python3 tools/bootstrap.py`, connect the board, and use
   `tools/device.py ports` and `info`. The board should report target
   `amoled-1.64-v2`, firmware `1.2.0`, assets `0.3.3`, and Bluetooth as its
   preferred transport before BLE acceptance begins.

## Keeping the personal fork updated

After cloning the personal fork on another computer, add the original project
once:

```sh
git remote add upstream https://github.com/TRIIIS-LABS/firmware-taby.git
```

Bring new upstream commits into personal `main` without rewriting published
history:

```sh
git fetch upstream
git switch main
git merge upstream/main
git push origin main
```

If the merge reports a conflict, stop and review the conflicting firmware
changes before pushing. Preserve the `amoled-1.64-v2` target and keep the
personal fork's GitHub Actions workflow absent unless the owner changes this
policy. Never force-push merely to bypass an upstream conflict.

## Safety and repository hygiene

- Use only official release assets and their matching checksum from the same
  release.
- Do not erase the whole flash or alter eFuses/security settings as a routine
  workaround.
- Do not commit `.venv`, downloaded firmware bundles, credentials, tokens,
  factory identity data, or private device logs.
- `work/` is intentionally ignored; it contains reproducible downloads rather
  than source.
