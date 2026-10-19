# Taby work log

## 2026-10-19

### Repository and USB preparation

- Cloned `https://github.com/TRIIIS-LABS/firmware-taby.git`.
- Read and followed `INSTALL.md`.
- Confirmed a native ESP32-S3 USB Serial/JTAG port appeared on macOS.
- Ran `python3 tools/bootstrap.py` with Python 3.14.7. The repository-local
  environment installed esptool 4.11.0 and pyserial 3.5 successfully.
- Listed ports with:

  ```sh
  .venv/bin/python tools/device.py ports
  ```

- Sent the read-only identification request. Result: `No Taby response`. This
  is not a flashing failure and is expected for a new board/vendor demo.

### Release preparation

- Selected the latest official release, v1.2.0, from the repository's GitHub
  Releases page.
- Downloaded `taby-amoled-1.64.zip` and its matching `.sha256` file into
  `work/amoled-1.64-v1.2.0/`.
- Verified SHA-256:

  ```text
  8431fed8ff4b9e32854c398dec46bf9290c814de447c3bf2020aa6d8d435c396
  ```

- Extracted the bundle to `work/amoled-1.64-v1.2.0/extracted/` and inspected it:

  ```sh
  .venv/bin/python tools/install.py inspect \
    --board amoled-1.64 \
    --bundle work/amoled-1.64-v1.2.0/extracted
  ```

- Inspection passed for board `amoled-1.64`, hardware revision `V1`, firmware
  `1.2.0`, and assets `0.3.3`. All five images, hashes, sizes, and permitted
  offsets were validated. NVS settings and factory identity regions are not in
  the write list.

### Compatibility finding

- The release supports only PCB V1. The firmware uses LCD chip select GPIO9.
- Waveshare's current V1.1 PCB swaps LCD chip select to GPIO46 and is not
  compatible with this bundle. The repository's older wording calls this
  unsupported revision V2.
- Flashing was intentionally paused until the physical PCB marking is confirmed.
- The owner could not locate the marking and explicitly requested that flashing
  proceed. The V1 selection is provisional and must be validated on the physical
  display after installation.

### App state

- Found `/Applications/Taby.app`, version 1.0.13, bundle identifier
  `com.heytaby.desktop`.
- Confirmed the app was not running during USB preparation.
- Documented post-flash flow: verify directly over USB first, complete the
  on-screen setup and select USB, then open Taby and enable physical output.

### Pending commands after V1 confirmation

Replace `PORT` with the currently listed `/dev/cu.usbmodem...` port:

```sh
.venv/bin/python tools/install.py flash \
  --board amoled-1.64 \
  --bundle work/amoled-1.64-v1.2.0/extracted \
  --port PORT \
  --confirmed-board

.venv/bin/python tools/device.py ports

.venv/bin/python tools/install.py verify \
  --board amoled-1.64 \
  --bundle work/amoled-1.64-v1.2.0/extracted \
  --port PORT

.venv/bin/python tools/device.py animation \
  --port PORT \
  --id confirmation
```

After these commands, visually confirm the animation. A successful serial reply
alone does not prove that the display or artwork is correct.

### Provisional V1 flash and verification

- With the owner's explicit authorization, flashed the complete official v1.2.0
  V1 bundle to the connected ESP32-S3.
- Esptool detected an ESP32-S3 with 16 MB flash and verified the hash of each of
  the five written image regions.
- The installer rebooted the board and completed its built-in verification.
- Ran a separate `tools/install.py verify`; result was `verified: true`.
- Reported device metadata: firmware `1.2.0`, assets `0.3.3`, hardware target
  `amoled-1.64`, rectangular display `280 x 456`, and USB bridge ready.
- Sent `tools/device.py animation --id confirmation`; the device returned
  `accepted: true`.
- Physical display validation remains pending because protocol acceptance cannot
  prove the screen is wired compatibly or rendering correctly.

### Desktop app handoff

- Opened Taby 1.0.13 after the serial tools released the USB port.
- Advanced onboarding through language, appearance, display, and microphone
  using their existing defaults.
- Paused at the Permissions page rather than deciding whether to grant access to
  open-app context, browser-page context, or notifications on the owner's behalf.
- Physical-device connection remains pending until onboarding continues.

### Blank-screen diagnosis

- The owner reported that nothing appeared on the physical display after the
  accepted `confirmation` animation command.
- A fresh `tools/device.py identify` still returned firmware `1.2.0`, assets
  `0.3.3`, target `amoled-1.64`, USB ready, preferred transport `usb`, and
  onboarding complete.
- The Taby app showed `Physical Taby Connected` during onboarding.
- Captured runtime serial output reported the asset-backed idle animation as
  rendered successfully:

  ```text
  taby_display: render_state=ambient_idle animation_id=idle_01_loop source=asset_pack_memory
  taby_runtime: render_state=ambient_idle has_animation=1 rendered=1
  ```

- These results locate the failure after firmware rendering, at the physical
  panel/control path. With the PCB revision unconfirmed, the leading explanation
  is the unsupported V1.1 wiring: V1 firmware uses LCD_CS GPIO9; V1.1 uses
  GPIO46.
- Stopped without another flash, full-chip erase, eFuse change, or speculative
  pin patch, following `INSTALL.md` guidance for a blank display after successful
  verification.

### V1.1 / V2 implementation

- Confirmed Waveshare's V1.1 pin map and upstream firmware PR #9 use LCD chip
  select GPIO46 while preserving GPIO9 for the original V1 target.
- Added a distinct `amoled-1.64-v2` target rather than changing the existing
  `amoled-1.64` target globally. The new target reuses the same 280 x 456 asset
  pack but reports its own hardware target and revision.
- Updated firmware selection, board metadata, asset lookup, packaging, CI,
  hardware catalog, installer guidance, and documentation.
- Added tests for V2 metadata, shared assets, pin separation, and rejection of
  cross-revision bundles. The full host suite passed: 56 tests passed and the optional Pillow
  visual test was skipped because Pillow is not installed.
- Installed ESP-IDF v5.4.2 in ignored `work/esp-idf-v5.4.2` and installed CMake
  and Ninja with Homebrew after the first build identified both as missing host
  dependencies.
- Built the target successfully:

  ```sh
  source work/esp-idf-v5.4.2/export.sh
  python tools/build.py amoled-1.64-v2
  ```

- Built the original `amoled-1.64` and `round-1.32` targets successfully as
  backward-compatibility checks after the shared tooling changes.

- Packaged and inspected the resulting bundle at
  `work/dist-v2-20261019/taby-amoled-1.64-v2`. Firmware is `1.2.0`; assets are
  `0.3.3`; NVS and factory identity partitions are not written.

### Custom V2 flash and app verification

- Flashed the custom bundle to `/dev/cu.usbmodem1101` with the confirmed
  `amoled-1.64-v2` target. Esptool verified every written image hash.
- The installer's post-flash check returned `verified: true` and reported target
  `amoled-1.64-v2`, 280 x 456 rectangular display, USB ready, and onboarding
  complete.
- Sent `idle_01_loop`; the device returned `accepted: true`.
- Opened Taby 1.0.13 and confirmed its setup summary reports `Physical Taby
  Connected`. Its independent Brain model download is paused at 2.9 GB of
  5.7 GB and is not needed for the firmware/USB connection.
- Visible screen output remains pending the owner's direct observation.

### Personal fork setup

- Created the personal GitHub fork `gopichandbusam/firmware-taby`.
- Configured local `origin` as the personal fork and `upstream` as
  `TRIIIS-LABS/firmware-taby`.
- Created branch `feature/waveshare-amoled-1.64-v2` so personal `main` can remain
  aligned with upstream updates.
- Added the no-history-rewrite upstream synchronization procedure to
  `memory.md`.
