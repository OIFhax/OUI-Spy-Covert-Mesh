# OUI-Spy Covert

Configurable BLE and WiFi surveillance detection firmware with Meshtastic mesh network output. This deployment keeps the Mesh-Detect detector XIAO ESP32-S3 and uses a separate XIAO ESP32-S3 with a Wio-SX1262 module mounted on its B2B connector as the Meshtastic radio. Configure target devices through the detector's web UI and receive alerts on the private Mesh-Detect channel.

Part of the [mesh-detect](https://github.com/colonelpanichacks/mesh-detect) hardware project.

## How It Works

1. **Boot** — Device starts in config mode, creates a WiFi access point
2. **Configure** — Connect to the AP, open the web UI, add target OUI prefixes / MAC addresses / BLE device names
3. **Scan** — Device shuts down the AP and begins dual BLE + WiFi scanning
4. **Alert** — When a target is detected, a plain-text message is sent over UART to your Meshtastic radio, which broadcasts it across the mesh

```
Detector XIAO (GPIO5 TX) ──UART 115200──> Radio XIAO + Wio-SX1262 ──LoRa──> Mesh-Detect receivers
```

## Detection Methods

| Method | What It Matches | Example |
|--------|----------------|---------|
| **OUI Prefix** | First 3 bytes of MAC (manufacturer) | `58:8e:81` |
| **Full MAC** | Exact device MAC address | `58:8e:81:ab:cd:ef` |
| **Device Name** | BLE advertised name (case-insensitive substring) | `Flock` |
| **Meta glasses signature** | Meta or Luxottica manufacturer ID together with Meta service UUID `FD5F`, when a Meta/Oakley/Ray-Ban name filter is configured | Unnamed Meta glasses advertisement |
| **WiFi Probe** | Source MAC from WiFi management frames (promiscuous mode) | Channels 1-13 |

The signature can match an unnamed advertisement even when the Bluetooth address
rotates. It can only detect a pair while that pair advertises; a pair that stops
advertising after connecting to its phone cannot be tracked continuously. The
manufacturer and service identifiers are shared across Meta products, so this
signature is a family-level match rather than proof of a specific pair of glasses.
It includes [OUI Spy's Meta/Ray-Ban `0x0D53` + `FD5F` composite](https://github.com/colonelpanichacks/oui-spy-unified-blue#mode-1-detector)
and the `0x01AB` + `FD5F` combination observed during Skyler power-up.
In live tests, connected Oakley Meta glasses advertised repeatedly. Shortly
after a first-generation Ray-Ban Meta Skyler pair was switched on, the scan saw
an unnamed `0x01AB` + `FD5F` advertisement. A repeat power-on triggered the
detector's `Meta BLE signature` alert, which another
Meshtastic radio received on the private Mesh-Detect channel. Opening the case,
removing the glasses, and two connected-wear observations produced no
identifiable Skyler advertisement in this test. A separate six-phase
case-to-face scan captured 11,080 BLE callbacks without `FD5F`, a Meta
manufacturer ID, or an advertised `Skyler` name. A model name shown in the
phone app is not necessarily a BLE advertised name.

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
This firmware scans BLE advertisements and WiFi management frames, so it
cannot see the measured Classic link transition. Changing BLE filters or
alert cooldowns cannot by itself generate dependable case-to-wear alerts
for any nearby Gen 1 pair. An app on a paired phone could report that phone's
own [ACL connection events and transport](https://developer.android.com/reference/android/bluetooth/BluetoothDevice#ACTION_ACL_CONNECTED).
Detecting arbitrary nearby pairs needs a separately
validated over-the-air signature; [ordinary Classic inquiry only finds
discoverable devices](https://www.bluetooth.com/wp-content/uploads/Files/Specification/HTML/Core-62/out/en/host/generic-access-profile.html).

## Meshtastic Messages

Plain text over Serial1 UART at 115200 baud:

```
Device Detected: 58:8e:81:ab:cd:ef
Redetection: Device 58:8e:81:ab:cd:ef
```

Run the [Seeed XIAO ESP32-S3/Wio-SX1262 Meshtastic firmware](https://wiki.seeedstudio.com/xiao_esp32s3_&_wio_SX1262_kit_for_meshtastic/) on the **radio XIAO**. The detector XIAO continues to run this repository's firmware and retains its saved filters when the radio is changed.

| Wio Meshtastic setting | Value |
|------------------------|-------|
| LoRa region | `US` |
| Modem preset | `LONG_FAST` |
| LoRa frequency slot | `20` (set explicitly) |
| Primary channel 0 | `Mesh-Detect`, with the same private key as the receiving radio's Mesh-Detect secondary channel |
| Serial module | Enabled, `TEXTMSG` mode |
| Serial RX (`serial.rxd`) | `2` (radio XIAO D1/GPIO2) |
| Serial TX (`serial.txd`) | `4` (radio XIAO D3/GPIO4) |
| Serial baud (`serial.baud`) | `BAUD_115200` |

[Meshtastic `TEXTMSG` sends UART text on the radio's default channel](https://meshtastic.org/docs/configuration/module/serial/), so set the Wio's channel 0 to Mesh-Detect in place of LongFast. The receiving radio may keep Mesh-Detect as a secondary channel. Its private channel name and key, region, preset, and frequency slot must match the Wio. Setting slot 20 explicitly keeps the Wio on the receiver's US LongFast radio frequency when its primary channel name changes; otherwise [Meshtastic can derive a different slot from that name](https://meshtastic.org/docs/configuration/tips/). Store the private key in the radios' channel settings, not in this repository.

## Web UI

Green-on-black terminal interface at `http://192.168.4.1`:

- OUI prefixes, full MAC addresses, BLE device names
- AP SSID/password config
- Live detection feed
- Burn-in mode (permanently lock settings, skip config on boot)

Default AP: `mesh-detect` / `meshdetect1`

## Hardware

The Wio-SX1262 is mounted on the **radio** XIAO through its B2B connector. Connect that XIAO to the existing detector XIAO with 3.3 V UART signals and a shared ground:

| Detector XIAO ESP32-S3 | Radio XIAO ESP32-S3 | Connection |
|-----------------------|--------------------|------------|
| D4/GPIO5, Serial1 TX | D1/GPIO2, Meshtastic Serial RX | Detector alerts to radio |
| D5/GPIO6, Serial1 RX | D3/GPIO4, Meshtastic Serial TX | UART return line; detector firmware does not currently process incoming text |
| GND | GND | Shared signal ground |

Detector pins and status indicators:

| Component | Pin | Function |
|-----------|-----|----------|
| Serial1 TX | GPIO5 (D4) | UART to Wio radio RX on GPIO2 |
| Serial1 RX | GPIO6 (D5) | UART from Wio radio TX on GPIO4 |
| NeoPixel | GPIO1 (D0) | Green breathing = scanning, red/white flash = detection |
| Onboard LED | GPIO21 | Status (inverted logic) |
| Boot Button | GPIO0 | Hold 1.5s to force config mode |

**Target**: Mesh-Detect detector XIAO ESP32-S3 plus a separate Seeed XIAO ESP32-S3/Wio-SX1262 B2B Meshtastic radio.

## Build & Flash

### PlatformIO

The pinned PlatformIO configuration builds with pioarduino Arduino 3.0.7 and
NimBLE-Arduino 2.5.1. PlatformIO Core 6.2.0 was used for the bundled binary.

```bash
pio run                    # Build
pio run -t upload          # Flash
pio device monitor -b 115200   # Monitor
```

### Pre-built Binary

`firmware/mesh-detect-meta-glasses.bin` is the default detector app image. Flashing only
the app partition preserves saved filters and WiFi settings. This requires the
detector's existing bootloader and partition table. If more than one ESP device
is attached, select the detector when the script prompts for a port. Keep
Meshtastic firmware on the radio XIAO.
The bundled image SHA-256 is
`bf1588d3ad4c5803c47a5fa34ef925e41df03d585fd75a7059f6529169783304`.

```bash
pip install esptool pyserial
python flash.py --single   # Flash one detector, retaining saved settings
python flash.py --single --erase  # Reset saved settings in NVS, then flash
```

Run `python flash.py` without `--single` to flash boards in a batch. Pass an
explicit binary path to use the original `mesh-detect-v1.0.bin` image.

## Dependencies

- [NimBLE-Arduino](https://github.com/h2zero/NimBLE-Arduino) 2.5.1
- [ESP Async WebServer](https://github.com/mathieucarbou/ESPAsyncWebServer) 3.0.6
- [Async TCP](https://github.com/mathieucarbou/AsyncTCP) 3.1.4
- [Adafruit NeoPixel](https://github.com/adafruit/Adafruit_NeoPixel) 1.15.5

## Author

[colonelpanichacks](https://github.com/colonelpanichacks)
