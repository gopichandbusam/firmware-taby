# Firmware target guide

This repository preserves the original firmware targets and adds an isolated
target for the newer Waveshare 1.64-inch PCB. Select by the physical board
revision, never by screen size or USB ID alone.

| Target | Exact hardware | Flash | Assets | Availability |
| --- | --- | --- | --- | --- |
| `amoled-1.64` | Waveshare ESP32-S3-Touch-AMOLED-1.64 V1 | 16 MB | `assets/amoled-1.64` | Official v1.0.8-v1.2.0 bundles and PR source build |
| `amoled-1.64-v2` | Waveshare ESP32-S3-Touch-AMOLED-1.64 V1.1/V2 | 16 MB | aliases `assets/amoled-1.64` | PR source build only; no official historical bundle |
| `round-1.32` | Waveshare ESP32-S3-Touch-AMOLED-1.32 | 8 MB | `assets/round-1.32` | Official v1.0.8-v1.2.0 bundles and PR source build |

The two rectangular targets use different LCD chip-select pins. A mismatched
image can boot and answer protocol commands while the screen remains black.

Build and package all three from the repository root in an ESP-IDF v5.4.2
terminal:

```sh
python tools/build.py amoled-1.64
python tools/build.py amoled-1.64-v2
python tools/build.py round-1.32
python tools/package_release.py amoled-1.64
python tools/package_release.py amoled-1.64-v2
python tools/package_release.py round-1.32
```

See the [firmware guide](../README.md#build-and-package-every-included-target)
for checks and bundle inspection, then use the [installation guide](../../INSTALL.md)
for board identification, flashing, post-flash verification, Bluetooth setup,
recovery, and rollback links.

Generated builds and ZIPs are intentionally ignored and are not committed to a
pull request. A published firmware release should attach the ZIP and `.sha256`
for each hardware-accepted target.
