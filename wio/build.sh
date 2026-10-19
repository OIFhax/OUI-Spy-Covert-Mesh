#!/usr/bin/env bash

# Build the detector inside the same Meshtastic firmware that drives the Wio.
# This script does not connect to, erase, or flash a device.
set -euo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
readonly MESHTASTIC_REPO="https://github.com/meshtastic/firmware.git"
readonly MESHTASTIC_TAG="v2.7.15.567b8ea"
readonly MESHTASTIC_COMMIT="567b8ea1c2b2d100c24b0d6cbc437ec89fae0a56"
readonly PATCH_FILE="$SCRIPT_DIR/meshtastic-2.7.15-oui-spy.patch"
readonly SEED_FILE="$SCRIPT_DIR/generated/meshdetect_filter_seed.h"
readonly PIO_ENV="seeed-xiao-s3"

fail() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

[[ -s "$PATCH_FILE" ]] || fail "Required detector patch is missing: $PATCH_FILE"
if [[ -e "$SEED_FILE" && ( ! -f "$SEED_FILE" || -L "$SEED_FILE" ) ]]; then
  fail "Filter seed must be a regular file: $SEED_FILE"
fi

pio_command="${WIO_PIO:-pio}"
command -v "$pio_command" >/dev/null 2>&1 || fail \
  "PlatformIO CLI is unavailable. Install it or set WIO_PIO to its executable path."

temp_parent="${WIO_TMPDIR:-${TMPDIR:-/private/tmp}}"
[[ -d "$temp_parent" ]] || fail "Temporary directory does not exist: $temp_parent"

build_root="$(mktemp -d "$temp_parent/oui-spy-covert-wio.XXXXXXXX")" || fail \
  "Could not create a private build directory in $temp_parent"
source_dir="$build_root/firmware"

# Keep PlatformIO's package cache outside the source checkout so a fresh,
# pinned checkout can be used on every run. An existing setting takes priority.
if [[ -z "${PLATFORMIO_CORE_DIR:-}" ]]; then
  export PLATFORMIO_CORE_DIR="$temp_parent/oui-spy-covert-pio-cache"
  mkdir -p "$PLATFORMIO_CORE_DIR"
  chmod 700 "$PLATFORMIO_CORE_DIR"
else
  [[ -d "$PLATFORMIO_CORE_DIR" && -w "$PLATFORMIO_CORE_DIR" ]] || fail \
    "PLATFORMIO_CORE_DIR must be an existing writable directory."
fi

printf 'Build directory: %s\n' "$build_root"
printf 'Fetching Meshtastic %s...\n' "$MESHTASTIC_TAG"
git clone --quiet --depth 1 --branch "$MESHTASTIC_TAG" "$MESHTASTIC_REPO" "$source_dir"
actual_commit="$(git -C "$source_dir" rev-parse HEAD)"
[[ "$actual_commit" == "$MESHTASTIC_COMMIT" ]] || fail \
  "Meshtastic tag did not resolve to the required commit ($MESHTASTIC_COMMIT)."

git -C "$source_dir" submodule update --init --recursive --quiet
git -C "$source_dir" apply --check "$PATCH_FILE" || fail \
  "Detector patch does not apply to Meshtastic $MESHTASTIC_COMMIT."
git -C "$source_dir" apply "$PATCH_FILE"

if [[ -f "$SEED_FILE" ]]; then
  install -m 600 "$SEED_FILE" "$source_dir/src/modules/esp32/meshdetect_filter_seed.h"
  printf 'Applied local filter seed.\n'
else
  printf 'No local filter seed; building with the patch defaults.\n'
fi

printf 'Building %s...\n' "$PIO_ENV"
"$pio_command" run --project-dir "$source_dir" --environment "$PIO_ENV"

artifact_dir="$source_dir/.pio/build/$PIO_ENV"
app_image="$artifact_dir/firmware.bin"
factory_image="$artifact_dir/firmware.factory.bin"
[[ -s "$app_image" ]] || fail "PlatformIO did not produce firmware.bin."
[[ -s "$factory_image" ]] || fail "PlatformIO did not produce firmware.factory.bin."

printf '\nBuild complete at Meshtastic commit %s.\n' "$actual_commit"
printf 'Application image: %s\n' "$app_image"
printf 'Factory image:     %s\n' "$factory_image"
printf 'No device was flashed.\n'
