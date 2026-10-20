# Installed Taby Bluetooth helper hardware tests

`tests/test_ble_v2_helper.py` tests the JSON-lines process harness with a fake
helper on every run. The four physical-board tests skip unless
`TABY_BLE_HARDWARE=1`. The real tests invoke the unmodified installed Taby
1.0.13 helper at
`/Applications/Taby.app/Contents/Resources/native/taby-bluetooth-probe`.

Before enabling the sweep, flash the matching `amoled-1.64-v2` bundle, complete
the one-time USB-to-Bluetooth handoff, and close Taby.app so it does not own the
board's BLE connection. Keep the board powered and advertising. Capture its
stable `device_id` from USB `INFO` before the BLE test; `tools/device.py info`
intentionally omits that field. For example, with Taby.app closed and the
actual serial port substituted:

```sh
.venv/bin/python -c 'import json,sys; sys.path.insert(0,"tools"); from device import exchange; print(json.loads(exchange(sys.argv[1],"INFO","TABY:INFO "))["device_id"])' /dev/cu.usbmodemXXXX
```

Then run from the repository root, substituting the ID returned by USB:

```sh
TABY_BLE_HARDWARE=1 TABY_USB_DEVICE_ID='YOUR_USB_DEVICE_ID' \
  .venv/bin/python -m unittest tests.test_ble_v2_helper -v
```

If more than one Taby peripheral is in range, set `TABY_BLE_PERIPHERAL_ID` to
the intended CoreBluetooth peripheral ID. `TABY_BLE_HELPER` can override the
helper executable for diagnosis; the default is the installed binary above.
The test checks scan, protocol-2 identity against the captured USB ID, choice,
state, command acknowledgements, retention after an unsupported animation,
re-advertising and reconnect from a fresh helper, all 84 current manifest IDs,
and every inferred `*_in>*_loop` pair. It reads state throughout the sweep to
detect a lost link. A passing protocol sweep does not establish that frames
rendered correctly; visually inspect animation behavior separately.
