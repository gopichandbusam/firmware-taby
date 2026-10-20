# Taby 1.64 V1.1 / V2 firmware target

This development target supports the newer Waveshare
ESP32-S3-Touch-AMOLED-1.64 PCB. Waveshare's current documentation calls it
**V1.1**; this repository and its existing upstream support branch call it
**V2**. Its version silkscreen is on the right side near the pin headers.

The actively used firmware difference is:

| Signal | V1 | V1.1 / V2 |
| --- | --- | --- |
| LCD_CS | GPIO9 | GPIO46 |
| IMU_INT1 | GPIO46 | GPIO9 |

The firmware polls the IMU and does not currently configure its interrupt pin.
The newer PCB also exposes IMU_INT2 on GPIO17, TP_INT on GPIO18, and LCD_TE on
GPIO45; those optional signals are not used here. The target reuses V1's
`sdkconfig.defaults`, `partitions.csv`, and `assets/amoled-1.64` pack.

```sh
python tools/build.py amoled-1.64-v2
python tools/package_release.py amoled-1.64-v2
.venv/bin/python tools/install.py inspect \
  --board amoled-1.64-v2 \
  --bundle dist/taby-amoled-1.64-v2
```

Continue with the shared [flash and verification guide](../../../INSTALL.md#4-inspect-install-and-verify).
For the complete original/new target matrix and all-target commands, see
[the target guide](../README.md) and [firmware guide](../../README.md).

A V1 image on this PCB, or this image on V1, leaves the screen black. For
manual download mode, hold BOOT, press and release RESET, keep holding BOOT for
about two seconds, then release it. Holding BOOT while plugging in USB also
works. Press RESET alone after flashing to start Taby.

Sources: [Waveshare revision guide](https://docs.waveshare.com/ESP32-S3-Touch-AMOLED-1.64)
and the existing [upstream V2 support PR](https://github.com/TRIIIS-LABS/firmware-taby/pull/9).
