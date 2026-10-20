# Taby Round 1.32 firmware target

This target is isolated from the working `amoled-1.64` firmware build.

It uses:

- Waveshare ESP32-S3-Touch-AMOLED-1.32
- 466x466 round AMOLED panel using the board's CO5300-compatible QSPI command set
- CST820 touch at I2C address `0x15`
- 8MB flash and 8MB octal PSRAM
- the isolated `assets/round-1.32` pack at the repository root

From the repository root, use the checked wrapper so the repository checks,
isolated build directory, target metadata, and build fingerprint are applied:

```sh
python tools/build.py round-1.32
python tools/package_release.py round-1.32
.venv/bin/python tools/install.py inspect \
  --board round-1.32 \
  --bundle dist/taby-round-1.32
```

Continue with the shared [flash and verification guide](../../../INSTALL.md#4-inspect-install-and-verify).
For the complete original/new target matrix and all-target commands, see
[the target guide](../README.md) and [firmware guide](../../README.md).
