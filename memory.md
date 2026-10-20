# Taby project memory

Last updated: 2026-10-19

## Goal

Install the official Physical Taby firmware on a connected Waveshare
ESP32-S3-Touch-AMOLED-1.64, verify the display with an animation, and connect it
to the Taby desktop app. Preserve enough context to continue on another
computer or improve the project later.

## Current state

- Primary repository: `gopichandbusam/firmware-taby`, branch `main`. The
  personal fork is local remote `origin`; the original
  `TRIIIS-LABS/firmware-taby` repository is remote `upstream`.
- Personal development happens directly on `main`; the owner does not want
  feature branches or GitHub Actions in this fork. The workflow file is absent
  and Actions are disabled in the personal repository settings.
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
- The V2 target passed `tools/check.py`, all 56 runnable unit tests, an ESP-IDF
  production build, release packaging, and bundle inspection. Clean production
  builds also passed for the unchanged `amoled-1.64` and `round-1.32` targets.
- The custom bundle was flashed successfully. Every image hash verified, and
  post-flash USB verification reports firmware `1.2.0`, assets `0.3.3`, target
  `amoled-1.64-v2`, rectangle `280 x 456`, and `usb_bridge_ready: true`.
- The device accepted `idle_01_loop`, and Taby 1.0.13 reports `Physical Taby
  Connected`. Physical screen visibility still requires the owner's direct
  confirmation; a successful USB response is not proof of visible pixels.
- The owner approved the Bluetooth-first compatibility design on 2026-10-19 at
  `docs/superpowers/specs/2026-10-19-bluetooth-first-taby-design.md`. The
  installed Taby 1.0.13 already contains USB and BLE transports but no Wi-Fi
  physical transport. Its BLE protocol 2 requires choice JSON on GATT UUID
  suffix `0006`, identity JSON on `0007`, and the USB `bluetooth_v2`
  capability; this firmware currently provides only suffixes `0002`-`0005` and
  does not advertise that capability.
- The approved first wireless release keeps one-time USB setup/update/recovery,
  then uses BLE for animations, cards, timers, clear, choices, orientation, and
  reconnect. Wi-Fi is deferred because it needs Mac app work and authenticated
  local control.
- The implementation plan is at
  `docs/superpowers/plans/2026-10-19-bluetooth-first-taby.md`. It makes the
  USB-to-BLE preference commit atomic, covers all 84 AMOLED animation IDs,
  tests app/device restart and restored power, and retains USB recovery. The
  plan awaits the owner's final confirmation before firmware edits begin.
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

1. Get the owner's confirmation of the Bluetooth implementation plan.
2. Execute the plan with parallel sub-agents, host tests first, directly on
   personal `main`.
3. Flash the completed V2 build and run the installed-app/helper BLE tests.
4. Physically validate the full manifest-driven animation sweep and lifecycle
   recovery; do not treat protocol acceptance as proof of visible output.
5. Test the work-Mac handoff when that computer is available.
6. Finish the desktop app's separate Brain download only when the owner wants
   the local AI features; it is not required for firmware or USB detection.
7. Before a public/upstream Bluetooth release, obtain security/API-contract
   review because Taby 1.0.13 expects unbonded BLE protocol 2.
8. On the other work computer, clone this branch, run `python3 tools/bootstrap.py`,
   connect the board, and use `tools/device.py ports` and `info`; reflashing is
   unnecessary unless the firmware changes.

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
