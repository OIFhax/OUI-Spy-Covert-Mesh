# OUI-Spy Covert Mesh: one-board XIAO ESP32-S3 + Wio-SX1262 build

This directory builds the detector **inside Meshtastic** for the assembled [Seeed XIAO ESP32-S3/Wio-SX1262 kit](https://wiki.seeedstudio.com/wio_sx1262_with_xiao_esp32s3_kit/). One XIAO performs BLE and Wi-Fi scanning and drives the mounted SX1262 LoRa radio. No Heltec, second detector board, or UART wiring is used.

The build pins Meshtastic release `v2.7.15.567b8ea` at commit `567b8ea1c2b2d100c24b0d6cbc437ec89fae0a56` and PlatformIO environment `seeed-xiao-s3`. [`build.sh`](build.sh) clones that exact source into a private temporary directory, applies `meshtastic-2.7.15-oui-spy.patch`, copies this branch's tracked filter seed, and builds the images. It never opens a serial port or flashes hardware.

**Status (2026-10-19):** The combined application was flashed and verified at `0x10000` on the configured Wio XIAO. Its USB API works, its private channel matches the preflash backup, and five OUI plus two name filters were verified in NVS. Two Oakley power-ups and one Gen 1 Skyler physical power-up generated alerts received by the second radio on `Mesh-Detect` and shown locally by the Wio USB client. Oakley's observed BLE address differed between power-ups. Skyler's case-to-wear reconnect with its power switch left on generated no new alert in this test. The obsolete Meshtastic Serial UART relay module was disabled.

The `Pervert Glasses Detected: <observed MAC>` and `Pervert Glasses Still On: <observed MAC>` texts in this branch are source changes. The configured Wio has not been flashed or field-tested with those new texts.

## Bundled filters

This branch intentionally tracks `wio/generated/meshdetect_filter_seed.h` with the five OUI and two BLE name filters used on the configured Wio. A fresh build includes the seed without needing the private backup. To check or intentionally regenerate the header from a validated detector NVS backup:

```sh
python3 tools/export_filter_seed.py --nvs /path/to/detector-nvs.bin
python3 tools/export_filter_seed.py --nvs /path/to/detector-nvs.bin --check
```

The exporter validates the backup and writes the header with mode `0600`. It rejects backups whose filter counts or format differ from the validated profile. It does not export AP credentials, detection history, radio configuration, or channel keys. The build script copies the header into its temporary Meshtastic checkout with mode `0600`. This branch publishes only the seven filter values; keep full-flash backups and channel configuration exports private. A built image contains the published filters but does not include the private channel key.

At first boot, the module imports the seed into the Wio's `meshdetect` NVS namespace **only if it finds no target or name filters there**. Existing NVS filters win. Rebuilding with a different seed and app-only flashing does not replace filters already in NVS. If the seed is removed and the Wio has no saved filters, the firmware uses generic `Meta`, `Oakley`, and `Ray-Ban` name filters and the Meta BLE signature. That fallback does not include the saved OUIs.

The combined image has **no detector AP or web filter editor**. Updating filters after the initial seed requires a targeted `meshdetect` NVS change as well as a revised seed or source. A blanket NVS erase can disrupt unrelated persisted device state.

## Build

Install Git and PlatformIO CLI. From the repository root, run:

```sh
./wio/build.sh
```

Set `WIO_PIO` to the full path of a PlatformIO executable if `pio` is not on `PATH`. The script prints its private temporary checkout and image paths. `WIO_TMPDIR` can select another existing temporary parent; `PLATFORMIO_CORE_DIR` can select an existing package cache. The patch must apply cleanly to the pinned commit. Keep machine-specific package paths and channel keys out of the patch.

The build produces these files under the printed checkout's `.pio/build/seeed-xiao-s3/`:

| File | Purpose |
| --- | --- |
| `firmware.bin` | Application image for an app-only or compatible OTA update. It contains no bootloader or partition table. |
| `firmware.factory.bin` | Bootloader, partition table, and application for factory provisioning. Do **not** write it to the configured radio; doing so can replace its partition layout and erase saved settings. |

## Update this configured radio

The current Wio XIAO has **8 MB flash**. Its installed partition table has active app0 at offset `0x10000`, size `0x250000` (2,424,832 bytes); OTA metadata selects app0. The pinned Meshtastic build target selects a different `default_8MB.csv` layout with a larger app slot. For an **app-only** update, the existing partition table stays in place, so check the produced `firmware.bin` against the **installed `0x250000` app0 limit**, not the build target's larger slot. Recheck the active slot and installed partition table on any other board.

Before flashing, keep private backups of the radio's full flash and Meshtastic configuration, including its `Mesh-Detect` key. Use an ignored, access-restricted location such as `local-backups/`; the channel export and flash backup contain secrets. Keep the LoRa antenna attached. Put the XIAO in ESP32-S3 ROM download mode, identify its ROM serial port, and set the following values for the image from this build and that port:

```sh
IMAGE="/absolute/path/to/firmware.bin"
ROM_PORT="/dev/cu.usbmodemXXXX"
wc -c < "$IMAGE"
```

Proceed only if the byte count is **at most 2,424,832** and the installed app0 layout and active OTA selection still match the values above. Then write the application at app0 without an erase:

```sh
python3 -m esptool --chip esp32s3 --port "$ROM_PORT" \
  --before no_reset --after hard_reset write_flash 0x10000 "$IMAGE"
```

Do not use `firmware.factory.bin`, `erase_flash`, the root detector-only `flash.py`, or the root PlatformIO upload command for this update. The app-only write preserves the existing NVS, LittleFS, private Meshtastic channel settings, and partition table. Retain the backup until the radio and detector are verified.

## Verify operation

After reboot, confirm Meshtastic reconnects over USB or Bluetooth and still has primary channel 0 named exactly `Mesh-Detect` with its private key, `US` region, `LONG_FAST` preset, and explicit frequency slot 20. The module refuses detector alerts if channel 0 is not the private `Mesh-Detect` channel. Bring a known matching device near the XIAO and check that `Pervert Glasses Detected: <observed MAC>` appears both on the Wio's local Meshtastic client and on a second radio joined to `Mesh-Detect`. A matching advertisement after at least 30 seconds of absence can produce `Pervert Glasses Still On: <observed MAC>`. The detector spaces outbound alerts at least 10 seconds apart.

This scanner observes BLE advertisements and Wi-Fi management-frame addresses. It cannot see the Bluetooth Classic reconnection measured during a Gen 1 Ray-Ban Meta case-to-wear test, so another alert on every case removal is not guaranteed. See the [main README](../README.md#first-generation-case-to-wear-test) for the observed transport behavior.
