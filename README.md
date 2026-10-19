# OUI-Spy Covert Mesh

The target hardware is **one Seeed XIAO ESP32-S3 with a Wio-SX1262 mounted on its B2B connector**. The XIAO runs the BLE/Wi-Fi detector inside Meshtastic firmware; the Wio supplies the SX1262 LoRa transceiver. Matching device sightings become text alerts on the private `Mesh-Detect` channel. See [Seeed's kit guide](https://wiki.seeedstudio.com/wio_sx1262_with_xiao_esp32s3_kit/).

Source repository: [OIFhax/OUI-Spy-Covert-Mesh](https://github.com/OIFhax/OUI-Spy-Covert-Mesh).

**Status (2026-10-19):** The combined image is installed on the configured Wio XIAO. Its USB API is responsive, the private `Mesh-Detect` channel matches the preflash backup, and all five OUI and two name filters were verified in device NVS. Two Oakley power-ups and one Gen 1 Skyler power-up produced alerts on the receiving radio's private channel and the Wio's USB client. Removing Skyler from its case and reconnecting it while its power switch stayed on produced no new alert in this test. Build and update instructions are in [`wio/`](wio/README.md).

The root `src/main.cpp`, `platformio.ini`, bundled `firmware/mesh-detect-meta-glasses.bin`, and `flash.py` belong to the earlier **detector-only** XIAO. That image has no Meshtastic stack or Wio driver. `flash.py` requires `--legacy-detector` to guard against installing it on the one-board radio. The old detector XIAO is no longer installed.

Part of the [mesh-detect](https://github.com/colonelpanichacks/mesh-detect) hardware project.

## How the one-board firmware works

```text
Nearby BLE advertisements and Wi-Fi management frames
                         ↓
XIAO ESP32-S3: scan → apply detector filters → create a text alert
                         ↓
Meshtastic channel 0, Mesh-Detect → mounted Wio-SX1262 → LoRa receivers
```

The detector module is applied to pinned Meshtastic `v2.7.15.567b8ea` source by [`wio/build.sh`](wio/build.sh). It sends matching sightings through Meshtastic's text-message service so the Wio's own Meshtastic client can show locally generated alerts. There is **no Heltec, second XIAO, or external UART link** in this design. Stock Meshtastic on the kit can transmit messages but does not scan for this project's targets.

## Detection Methods

| Match | Source |
| --- | --- |
| Saved three-byte OUI or full MAC | BLE address or Wi-Fi management-frame source address |
| Saved name pattern | Case-insensitive substring of a BLE advertised name |
| Meta glasses signature | BLE service UUID `FD5F` together with manufacturer ID `0x01AB` or `0x0D53`, when a Meta-family name filter enables signature matching |

When at least one address filter exists and Meshtastic Wi-Fi is disabled, the Wi-Fi monitor hops across US channels 1–11. A first matching sighting queues `Device Detected: <observed MAC>`. The same observed address can queue `Redetection: Device <observed MAC>` after at least 30 seconds without a matching sighting. Alerts are spaced at least 10 seconds apart across targets. A rotating BLE address may appear as a new device.

The signature can match an unnamed advertisement even when the Bluetooth address
rotates. It can only detect a pair while that pair advertises; a pair that stops
advertising after connecting to its phone cannot be tracked continuously. The
manufacturer and service identifiers are shared across Meta products, so this
signature is a family-level match rather than proof of a specific pair of glasses.
It includes [OUI Spy's Meta/Ray-Ban `0x0D53` + `FD5F` composite](https://github.com/colonelpanichacks/oui-spy-unified-blue#mode-1-detector)
and the `0x01AB` + `FD5F` combination observed during Skyler power-up.
In earlier tests with a **separate detector board**, connected Oakley Meta glasses advertised repeatedly. Shortly
after a first-generation Ray-Ban Meta Skyler pair was switched on, the scan saw
an unnamed `0x01AB` + `FD5F` advertisement. A repeat power-on triggered the
detector's `Meta BLE signature` alert, which another
Meshtastic radio received on the private Mesh-Detect channel. Opening the case,
removing the glasses, and two connected-wear observations produced no
identifiable Skyler advertisement in this test. A separate six-phase
case-to-face scan captured 11,080 BLE callbacks without `FD5F`, a Meta
manufacturer ID, or an advertised `Skyler` name. A model name shown in the
phone app is not necessarily a BLE advertised name. With the combined Wio
firmware, a Skyler physical power-switch startup produced a new alert on both
radios. A later case-to-wear reconnection with the switch left on produced no
new alert during the monitored interval.

### First-generation case-to-wear test

On 2026-10-18, the Android phone paired with the Gen 1 Skyler pair identified
it as `RB Meta 021N` and a dual-mode Bluetooth device. With Skyler docked in
the closed case, Android reported `[ACL BR/EDR:N LE:Y]`. When worn and
connected, it reported `[ACL BR/EDR:Y LE:Y]`. Its Bluetooth history recorded
a Skyler-initiated Classic connection at 12:09:45, a Skyler-initiated Classic
disconnection after docking at 12:10:27, and another Skyler-initiated Classic
connection after removal at 12:10:54 (local MDT). A2DP opened after both connections.
No Skyler BLE ACL disconnect/reconnect appeared in that interval. These are
observations for this pair and phone, not a model-wide fingerprint.

The [ESP32-S3 supports BLE but not Bluetooth Classic](https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-guides/bt-architecture/overview.html).
This firmware scans BLE advertisements and Wi-Fi management frames, so it
cannot see the measured Classic link transition. Its 30-second rearm can alert
on another matching BLE advertisement after absence; it cannot guarantee an
alert for every Gen 1 case removal or reconnection to a paired phone. An app
on a paired phone could report that phone's own
[ACL connection events and transport](https://developer.android.com/reference/android/bluetooth/BluetoothDevice#ACTION_ACL_CONNECTED).
Detecting arbitrary nearby pairs in that state needs a separately validated
over-the-air signature; [ordinary Classic inquiry only finds discoverable
devices](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/host/generic-access-profile.html).

## Private Meshtastic channel

The single XIAO's existing Meshtastic configuration was tested by sending a manual text message from the Wio kit; the receiving radio displayed it on `Mesh-Detect`. The combined detector's two Oakley alerts and one Skyler power-up alert were also received there and shown by the Wio's USB client. Oakley used a different observed BLE address after its second power-up, so both were first-sighting messages. The detector creates alerts such as:

```
Device Detected: <observed MAC>
Redetection: Device <observed MAC>
```

Preserve these settings when installing a combined image:

| Setting | Wio XIAO | Receiving radio |
|---------|----------|-----------------|
| LoRa region | `US` | `US` |
| Modem preset | `LONG_FAST` | `LONG_FAST` |
| LoRa frequency slot | `20` (explicit) | `20` (effective) |
| `Mesh-Detect` channel | Primary, index 0 | Secondary, index 2 |
| Channel key | Same private key on both radios | Same private key on both radios |

The module checks that the Wio's primary channel 0 is named exactly `Mesh-Detect` and has a nondefault private key before sending. If that check fails, it does not send detector alerts on public LongFast. Setting slot 20 explicitly keeps the radios on the same US LongFast frequency when the Wio's primary channel is named Mesh-Detect; [Meshtastic can otherwise derive a slot from the channel name](https://meshtastic.org/docs/configuration/tips/). Keep the private channel key in device configuration or a local backup, not in this repository. The old two-board `Serial` module was disabled on the configured Wio.

## Filter configuration

The validated backup from the removed detector XIAO contains **five OUI filters and two name filters**, with no full-MAC filters. [`tools/export_filter_seed.py`](tools/export_filter_seed.py) extracts only those filters into the ignored `wio/generated/meshdetect_filter_seed.h`; it does not copy the old access-point credentials, detection history, or Meshtastic channel key. The build script includes this local seed when present.

On first boot, the combined module copies the seed into the Wio's `meshdetect` NVS namespace **only when that namespace has no target or name filters**. Existing Wio detector filters take precedence. Later app-only firmware updates keep those NVS filters; changing the seed and rebuilding alone does not replace them. Without saved filters or a seed, the module falls back to built-in `Meta`, `Oakley`, and `Ray-Ban` BLE name patterns and their enabled Meta signature. See the [one-board build guide](wio/README.md) for the local export and build commands.

The combined firmware currently has **no detector access point or web filter editor**. To change filters, prepare a revised local seed or source and rebuild, then arrange a targeted update to the `meshdetect` NVS namespace. Erasing all NVS to force reseeding can disrupt unrelated persisted device state. The earlier detector-only firmware's web UI and AP password do not configure this one-board build.

## Hardware

Use the [Seeed XIAO ESP32-S3/Wio-SX1262 B2B kit](https://wiki.seeedstudio.com/wio_sx1262_with_xiao_esp32s3_kit/) with its LoRa antenna attached. The SX1262 connects to the XIAO through the mounted expansion board. There is no external UART wiring or second microcontroller. The GPIO5/GPIO6 `Serial1` and NeoPixel assignments in the detector-only source are legacy and are not part of the combined module.

## Build & Flash

### Combined one-board image

Follow [`wio/README.md`](wio/README.md) to export the private local seed, build the pinned Meshtastic image, verify its size against the **installed** app0 partition, and install only the application image. The configured radio's active app0 starts at `0x10000` and has size `0x250000`. Keep a private full-flash and channel-configuration backup before updating it. The build's `firmware.factory.bin` contains a partition table and is not the update image for this configured radio.

After installation, verify that the Wio still has the private `Mesh-Detect` primary channel and frequency slot 20, then verify a matched detector sighting appears locally on the Wio and on the receiving radio. Gen 1 case-to-wear behavior must be evaluated within the Bluetooth limitation above.

### Legacy detector-only PlatformIO target

The root pinned PlatformIO configuration builds with pioarduino Arduino 3.0.7 and
NimBLE-Arduino 2.5.1. PlatformIO Core 6.2.0 was used for the bundled detector-only binary. These commands are for a **physically separate legacy detector XIAO only**:

```bash
pio run                         # Build legacy detector image
pio run -t upload               # Upload only to a separate detector XIAO
pio device monitor -b 115200   # Monitor that detector
```

### Pre-built legacy detector binary

The bundled `firmware/mesh-detect-meta-glasses.bin` is a detector-only app image (SHA-256 `bf1588d3ad4c5803c47a5fa34ef925e41df03d585fd75a7059f6529169783304`). It is **not an image for the one-board Wio kit**. `flash.py` refuses to run without an explicit `--legacy-detector` option to prevent an accidental radio overwrite. Its optional `--erase` clears the old detector's saved filters and AP credentials. Do not use `flash.py` or `pio run -t upload` on the installed Wio XIAO with this target.

```bash
pip install esptool pyserial
python flash.py --legacy-detector --single  # Only for a separate legacy detector
```

Run `python flash.py --legacy-detector` without `--single` to flash legacy detector boards in a batch. Pass an explicit binary path to use the original `mesh-detect-v1.0.bin` image, also only on a separate legacy detector board.

## Legacy detector dependencies

- [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino) 2.5.1
- [ESP Async WebServer](https://github.com/mathieucarbou/ESPAsyncWebServer) 3.0.6
- [Async TCP](https://github.com/mathieucarbou/AsyncTCP) 3.1.4
- [Adafruit NeoPixel](https://github.com/adafruit/Adafruit_NeoPixel) 1.15.5

## Author

[colonelpanichacks](https://github.com/colonelpanichacks)
