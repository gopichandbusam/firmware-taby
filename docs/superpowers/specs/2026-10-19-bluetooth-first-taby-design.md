# Bluetooth-first Physical Taby design

Status: Proposed for owner approval

Date: 2026-10-19

Target: Waveshare ESP32-S3-Touch-AMOLED-1.64 V1.1/V2 (`amoled-1.64-v2`)

Desktop compatibility target: installed Taby for macOS 1.0.13

## Intent

Let the existing Taby desktop app control the physical Taby over Bluetooth Low
Energy after a one-time USB setup. The face should keep the behavior it already
has over USB: animations, title cards, choices, timers, clear/idle behavior,
choice input, display orientation, reconnect, and presentation restoration.

This is a compatibility project, not a new wireless protocol. The installed
Mac app already contains a Bluetooth transport, while the firmware contains an
incomplete version of the matching BLE service. The first release completes
that existing contract and keeps USB as the trusted flashing, recovery, and
diagnostic path.

## What exists today

### Firmware

- USB is the complete and currently working app transport.
- The shared command parser and runtime already keep animation and reusable UI
  behavior independent of the transport.
- A NimBLE GATT service already accepts display, brightness, and orientation
  commands and emits `READY`, `OK`, and `ERR` events.
- Wi-Fi station/setup mode and a local HTTP server already exist, but the HTTP
  interface is unauthenticated and is not used by Taby for macOS 1.0.13.
- Factory-backed devices are marked as USB-onboarded at first boot. The
  on-device first-run chooser currently renders and hit-tests only USB.
- USB `INFO` does not list the `bluetooth_v2` capability.
- BLE is missing the identity and choice characteristics required by the Mac
  app's protocol-2 handshake.

### Installed Mac app

Taby 1.0.13 constructs USB and Bluetooth physical transports. It does not
construct a Wi-Fi transport.

The app only offers USB-to-Bluetooth switching when the device's USB `INFO`
capabilities include `bluetooth_v2`. Its Bluetooth helper expects:

- protocol-2 device identity;
- the existing command and event characteristics;
- the existing readable state characteristic;
- a readable choice signal;
- the ability to reconnect to a remembered CoreBluetooth peripheral; and
- the same physical device ID reported over USB.

The app's Bluetooth adapter supports display commands, choice input, and
orientation. It does not currently expose gesture/hold-to-talk, brightness, or
eye-motion controls over Bluetooth.

## Goals

1. Make Taby 1.0.13 recognize this firmware as Bluetooth-compatible.
2. Let the app switch a USB-connected device to Bluetooth and remember it.
3. Preserve the current display command strings and visual behavior.
4. Preserve the device identity across USB and Bluetooth.
5. Support app-driven choices and display orientation over BLE.
6. Re-advertise after disconnect and reconnect without rebooting the device.
7. Allow the personal Mac and work Mac to use the same board, one controller at
   a time, after each computer explicitly selects the device.
8. Keep USB available for flashing, recovery, verification, and firmware
   updates.
9. Preserve every existing USB command and reply.

## Non-goals for the first release

- A Wi-Fi transport in the Mac app.
- Wi-Fi firmware updates or BLE firmware updates.
- Sending animation assets over Bluetooth.
- Simultaneous control from two computers.
- Simultaneous normal traffic over BLE and Wi-Fi.
- Changing the animation catalog, display driver, or V1/V2 board pins.
- Replacing the current command language with a new framed protocol.
- Patching or re-signing the installed Taby application.
- Claiming full USB feature parity for app features that its Bluetooth adapter
  does not implement: gestures/hold-to-talk, brightness settings, and eye-motion
  settings remain available over USB.

## Product behavior

### First connection

1. The board is flashed and verified over USB as it is today.
2. Taby 1.0.13 discovers the board over USB and reads `INFO`.
3. Because `INFO.capabilities` includes `bluetooth_v2`, the app offers its
   Bluetooth connection action.
4. The user chooses Bluetooth in the app.
5. The app sends `TRANSPORT_MODE bluetooth`, then
   `TRANSPORT_DEFAULT bluetooth` over USB.
6. Firmware starts BLE, persists Bluetooth as the preferred transport, displays
   a Bluetooth pairing/advertising hint, and advertises the Taby service.
7. The app scans, shows an anonymous `Taby 1` candidate, and connects after the
   user selects it.
8. The app validates protocol version, device ID, and firmware version, then
   stores the CoreBluetooth peripheral ID paired with the device ID.
9. The device returns to the ordinary Taby face and receives normal app output
   over BLE.

USB remains physically usable throughout. It is not the active presentation
transport after the Bluetooth handoff, but it remains the recovery channel.

### Later starts and reconnects

- The board starts BLE when Bluetooth is the persisted preference.
- The app tries the remembered BLE peripheral first.
- A successful reconnect must return the same device ID as the USB identity.
- If BLE fails, the app may fall back to the matching USB device when the cable
  is connected.
- Firmware advertises again after disconnect.
- The app restores persistent or interactive presentation state through its
  existing reconnect behavior; ephemeral animations are not restored.
- Disconnecting one Mac makes the board available to the other Mac. Only one
  BLE controller is accepted at a time.

### Recovery

- A USB `TRANSPORT_DEFAULT usb` command returns the device to USB-first use.
- USB `ONBOARDING_RESET` and `FACTORY_RESET` retain their current meanings.
- Firmware installation and reinstallation remain USB-only.
- A failed BLE initialization must not prevent the display, USB protocol, or
  recovery commands from starting.

## BLE protocol-2 contract

All additions are additive. Existing UUIDs and payloads remain unchanged.

### Service and existing characteristics

Base UUID family: `54414259-0000-4000-a000-000000000000`

| Suffix | Role | Access | Payload |
| --- | --- | --- | --- |
| `0001` | Primary Taby service | Discover | Existing service UUID |
| `0002` | Command | Write / write without response | One UTF-8 command, no newline, maximum 255 bytes |
| `0003` | Event | Read / notify | Existing `READY`, `OK ...`, or `ERR ...` payload |
| `0004` | State | Read | Existing current state name |
| `0005` | Power | Read | Existing compact power JSON |

### New identity characteristic

Suffix: `0007`

Access: read-only

UTF-8 JSON payload:

```json
{"protocol":2,"deviceId":"DEVICE_ID","firmwareVersion":"1.2.0"}
```

Rules:

- The object contains exactly `protocol`, `deviceId`, and `firmwareVersion`.
- `protocol` is the integer `2`.
- `deviceId` is the same non-empty stable identifier returned by USB `INFO` and
  contains only `A-Z`, `a-z`, `0-9`, `.`, `_`, `:`, or `-`, up to 120 bytes.
- `firmwareVersion` is the build's existing public version, 1 to 80 bytes.
- The payload must fit in a normal GATT read and be generated from device-owned
  identity/build data; it must not contain the device secret, Wi-Fi details, or
  claim owner.
- Missing or unsafe identity makes protocol-2 BLE unavailable. Firmware must not
  invent an identity different from USB.

### New choice characteristic

Suffix: `0006`

Access: read-only

UTF-8 JSON payload:

```json
{"signal":0,"choice":"none"}
```

Rules:

- `signal` is the same monotonically increasing choice counter exposed by USB
  `CHOICE_SIGNAL` and HTTP `/v1/reusable/choice-signal`.
- `choice` is `left`, `right`, or `none`.
- USB selection `choice_1` maps to `left`; `choice_2` maps to `right`; no
  selection maps to `none`.
- The legacy one-button `action` selection maps to `left`. This is the primary
  action and is the only useful representation available in the installed
  app's strict `left|right|none` schema. Taby 1.0.13 does not generate
  one-button action cards through its normal Bluetooth command contract, but
  the mapping keeps the characteristic valid if another transport displayed
  such a card.
- Reading does not consume or reset the signal.
- The Mac app owns deduplication and prompt correlation, as it does over USB.

The UUID mapping and strict JSON shapes were confirmed against the installed
Taby 1.0.13 native Bluetooth helper: choice is `0006`, identity is `0007`, and
both values are decoded as JSON. A compatibility fixture or helper-driven
integration test must lock that mapping before the capability is advertised.
The app binary is the authority for this personal compatibility build.

### Command/event behavior

- Keep the existing service, command, event, state, and power UUIDs.
- The client subscribes to the event characteristic before writing.
- Each app display command is one complete UTF-8 characteristic value; the
  first release does not add fragmentation.
- Successful commands notify `OK <STATE>`.
- Unsupported animation remains a successful BLE write with
  `OK <STATE> unsupported_animation <ID>` so the app keeps the connection.
- Other known refusals notify `ERR <reason>` and use the existing ATT error
  behavior expected by the helper.
- `CLEAR` compatibility continues through the app's existing `S` command.
- UI commands, timers, choices, and animation IDs continue to use the shared
  transport parser/runtime rather than separate BLE behavior.

## Firmware changes

### `taby_ble_transport.[ch]`

- Retain the existing service and characteristics.
- Store a safe copy/reference of the initialized device identity.
- Add read-only choice (`0006`) and identity (`0007`) characteristics.
- Generate identity JSON with bounded `snprintf` and explicit truncation/error
  checks.
- Generate choice JSON from the reusable UI's existing signal source.
- Keep one connection, reconnect advertising, event notification, command queue,
  and connection parameters unchanged.
- Report a clear internal diagnostic when identity cannot satisfy protocol 2.

### `taby_usb_serial.c`

- Add `bluetooth_v2` to `INFO.capabilities` only when the compiled firmware has
  the complete identity/choice contract and a usable stable device identity.
- Preserve every existing capability and reply field.
- Keep `TRANSPORT_MODE bluetooth` and `TRANSPORT_DEFAULT bluetooth` behavior.

### `app_main.c` and onboarding

- Keep the current factory USB shipping default for the first release. USB is
  the one-time trusted setup and recovery path.
- Do not start BLE on a normal USB-preferred boot.
- Continue starting BLE automatically when Bluetooth is the persisted default.
- Preserve the existing Bluetooth hint/banner shown by the app-driven transport
  switch.
- Do not expose the dormant three-way on-device chooser in this release. Doing
  so would allow unauthenticated pairing without the app's explicit USB handoff
  and would expand test scope.

### Build configuration

- Keep NimBLE enabled and the current resource limits unless measured hardware
  testing proves they are insufficient.
- Do not change partitions or the board data model.
- Do not enable Classic Bluetooth; ESP32-S3 uses BLE only.

## Security and privacy boundary

The installed app's current helper and the inherited firmware use an unbonded,
unencrypted application protocol. Adding bonding, passkeys, a new token, or an
encrypted characteristic requirement would change the app/firmware contract and
cannot be done in firmware alone.

For this personal compatibility release:

- BLE only starts after the user explicitly enables it through a USB-connected
  Taby app, or when that preference was already persisted.
- Only one controller can be connected.
- BLE identity exposes only protocol version, device ID, and firmware version.
- Device secrets, Wi-Fi credentials, claim data, logs, and diagnostics are never
  exposed through BLE.
- Firmware does not accept Wi-Fi provisioning, factory reset, claiming, or
  firmware installation over BLE.
- The limitation that nearby users could connect while the board is advertising
  must be documented. This build is suitable for the owner's personal desk
  testing, not for a public security claim.

A public/upstream release requires security/API-contract review and coordinated
Mac app work for authenticated pairing or bonded/encrypted characteristics.
That review is intentionally outside this firmware-only first release.

## Compatibility and migration

- USB clients see only one additive capability: `bluetooth_v2`.
- Existing Bluetooth UUIDs and event payloads remain stable.
- Devices already persisted to USB stay on USB until the app changes the
  preference.
- Devices already persisted to Bluetooth start the completed protocol-2 service
  after updating.
- Firmware downgrade may leave `bluetooth` persisted on a version without the
  complete contract. USB remains available to restore `usb` as the default.
- The Mac app may remember a CoreBluetooth peripheral per computer. The board's
  stable device ID prevents a remembered peripheral from being accepted as a
  different Taby.

## Validation

### Host and static tests

- Identity JSON contains exactly the protocol-2 fields and rejects/withholds the
  capability for missing or unsafe identity.
- Identity payload uses the same device ID and firmware version sources as USB.
- Choice JSON maps none/left/right, maps legacy one-button action to left, and
  preserves the monotonic counter.
- GATT table contains `0001` through `0007` with the required access flags.
- `bluetooth_v2` appears in USB `INFO` only when its contract is available.
- Existing USB/protocol/eye-motion tests remain green.
- `python tools/check.py` passes.
- `python -m unittest discover -s tests -v` passes.
- Clean ESP-IDF builds pass for `amoled-1.64`, `amoled-1.64-v2`, and
  `round-1.32` because BLE code is shared.

### Installed-app compatibility tests

Using the installed Taby 1.0.13 Bluetooth helper:

1. USB discovery reports `bluetooth_v2`.
2. The app successfully sends the transport-mode/default commands.
3. BLE scan returns exactly one candidate for the test board.
4. Connect returns protocol 2, the USB device ID, and firmware version.
5. The app remembers the peripheral and reconnects after app restart.
6. Wrong/missing identity and choice characteristics fail without corrupting
   USB operation.

### Physical board tests

On the `amoled-1.64-v2` board:

- show the Bluetooth ready/connected state visibly;
- play at least two animations;
- display and clear a title card;
- run and update a timer;
- show a two-choice prompt and receive left/right selections;
- read and change display orientation;
- disconnect/reconnect the Mac without rebooting;
- close the personal Mac connection and connect from the work Mac;
- power-cycle and reconnect using the saved Bluetooth preference;
- connect USB and restore USB as the default;
- verify USB flashing still works after Bluetooth use; and
- visually confirm the AMOLED output after the final build.

The firmware build and protocol replies are not sufficient evidence of visible
display or touch success.

## Acceptance criteria

The first release is complete when:

- Taby 1.0.13 enables Bluetooth for the device without patching the app;
- the device connects and reconnects over BLE with the same identity as USB;
- animations, cards, timers, clear, choices, and orientation work through the
  installed app;
- the other Mac can connect after the first Mac disconnects;
- no existing USB behavior regresses;
- all host checks and all three target builds pass;
- the physical V2 board passes the test list; and
- the documentation clearly states the BLE security limitation and USB-only
  update/recovery path.

## Follow-up phase: secure Wi-Fi

Wi-Fi is a separate project because the installed app has no Wi-Fi physical
transport and the current firmware HTTP API is unauthenticated.

A future Wi-Fi design should include:

- a Mac app transport using Bonjour discovery;
- a Taby-specific service rather than only generic `_http._tcp`;
- an explicit protocol and capability handshake;
- proof-of-possession pairing and authenticated requests;
- a transport-neutral command router so USB/BLE/Wi-Fi cannot drift;
- reliable request IDs, timeouts, and event delivery; and
- a decision about BLE fallback while Wi-Fi is active on the shared 2.4 GHz
  radio.

That phase must receive security and API-contract review before implementation.

## Builder-owned implementation details

The builder may decide internal helper names, exact test-fixture organization,
and whether bounded JSON formatting lives inside `taby_ble_transport.c` or a
small private helper module. Those choices must not alter the wire contract,
activation flow, security boundary, or acceptance criteria above.
