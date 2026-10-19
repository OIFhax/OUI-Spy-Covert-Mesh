#!/usr/bin/env python3
"""Export only the old detector's OUI and name filters as a C++ seed.

The Pervert-Detector branch tracks the generated header so fresh Wio builds include
its filters. No AP settings, detected-device history, radio settings, or channel
keys are exported.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import struct
import sys
import tempfile
import zlib


PAGE_SIZE = 4096
ENTRY_SIZE = 32
ENTRY_COUNT = 126
WRITTEN = 2
VALID_PAGE_STATES = {0xFFFFFFFE, 0xFFFFFFFC, 0xFFFFFFF8}
NVS_KEY = re.compile(rb"[A-Za-z][A-Za-z0-9_]{0,14}\Z")
OUI = re.compile(r"[0-9a-fA-F]{2}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\Z")
EXPECTED_OUIS = 5
EXPECTED_NAMES = 2
REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NVS = Path("/private/tmp/meshdetect-nvs-after-meta-patch-20261018.bin")
OUTPUT = REPO_ROOT / "wio/generated/meshdetect_filter_seed.h"


class ExportError(Exception):
    """A backup or generated file failed validation."""


def _entries(image: bytes):
    if len(image) < PAGE_SIZE or len(image) % PAGE_SIZE:
        raise ExportError("NVS backup must consist of complete 4096-byte pages")

    for page_number in range(len(image) // PAGE_SIZE):
        page = image[page_number * PAGE_SIZE : (page_number + 1) * PAGE_SIZE]
        page_state, sequence = struct.unpack_from("<II", page)
        if page_state not in VALID_PAGE_STATES:
            continue

        bitmap = page[32:64]
        slot = 0
        while slot < ENTRY_COUNT:
            entry_state = (bitmap[slot // 4] >> (2 * (slot % 4))) & 3
            if entry_state != WRITTEN:
                slot += 1
                continue

            offset = 64 + slot * ENTRY_SIZE
            entry = page[offset : offset + ENTRY_SIZE]
            namespace_id, value_type, span = entry[:3]
            key_bytes = entry[8:24].split(b"\0", 1)[0]
            if not (1 <= span <= ENTRY_COUNT - slot and NVS_KEY.fullmatch(key_bytes)):
                slot += 1
                continue
            expected_crc = struct.unpack_from("<I", entry, 4)[0]
            actual_crc = zlib.crc32(entry[:4] + entry[8:], 0xFFFFFFFF)
            if actual_crc != expected_crc:
                slot += 1
                continue

            # Keep only a pointer to the page. In particular, do not decode or
            # copy values for AP credentials or other unrelated NVS keys.
            yield (sequence, slot, namespace_id, value_type, span,
                   key_bytes.decode("ascii"), page, entry)
            slot += span


def _latest(entries, namespace_id: int, key: str):
    matches = [item for item in entries if item[2] == namespace_id and item[5] == key]
    if not matches:
        raise ExportError(f"required filter key is missing: {key}")
    return max(matches, key=lambda item: (item[0], item[1]))


def _int32(item, key: str) -> int:
    if item[3] != 0x14 or item[4] != 1:
        raise ExportError(f"filter key has the wrong type: {key}")
    return struct.unpack_from("<i", item[7], 24)[0]


def _bool(item, key: str) -> bool:
    if item[3] != 0x01 or item[4] != 1:
        raise ExportError(f"filter key has the wrong type: {key}")
    value = item[7][24]
    if value not in (0, 1):
        raise ExportError(f"filter key has an invalid boolean: {key}")
    return bool(value)


def _string(item, key: str) -> str:
    if item[3] != 0x21 or item[4] < 2:
        raise ExportError(f"filter key has the wrong type: {key}")
    slot, span, page, entry = item[1], item[4], item[6], item[7]
    size = struct.unpack_from("<H", entry, 24)[0]
    if size < 2 or size > (span - 1) * ENTRY_SIZE:
        raise ExportError(f"filter string has an invalid length: {key}")
    first = 64 + (slot + 1) * ENTRY_SIZE
    payload = page[first : first + size]
    data_crc = struct.unpack_from("<I", entry, 28)[0]
    if zlib.crc32(payload, 0xFFFFFFFF) != data_crc:
        raise ExportError(f"filter string failed CRC validation: {key}")
    if not payload.endswith(b"\0") or b"\0" in payload[:-1]:
        raise ExportError(f"filter string is not properly terminated: {key}")
    try:
        return payload[:-1].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ExportError(f"filter string is not valid UTF-8: {key}") from exc


def load_filters(image: bytes) -> tuple[list[str], list[str]]:
    entries = list(_entries(image))
    namespaces = {
        item[7][24]
        for item in entries
        if item[2] == 0 and item[3] == 0x01 and item[4] == 1
        and item[5] == "meshdetect"
    }
    if len(namespaces) != 1:
        raise ExportError("expected one meshdetect NVS namespace")
    namespace_id = namespaces.pop()

    oui_count = _int32(_latest(entries, namespace_id, "filterCount"), "filterCount")
    name_count = _int32(_latest(entries, namespace_id, "nameCount"), "nameCount")
    if oui_count != EXPECTED_OUIS or name_count != EXPECTED_NAMES:
        raise ExportError("filter counts do not match the validated detector backup")

    ouis = []
    for index in range(oui_count):
        if _bool(_latest(entries, namespace_id, f"mac_{index}"), f"mac_{index}"):
            raise ExportError("backup contains a full-MAC filter; this exporter only seeds OUIs")
        identifier = _string(_latest(entries, namespace_id, f"id_{index}"), f"id_{index}")
        normalized = identifier.lower().replace("-", ":").replace(" ", "")
        if not OUI.fullmatch(normalized):
            raise ExportError(f"invalid OUI identifier in id_{index}")
        ouis.append(identifier)

    names = []
    for index in range(name_count):
        name = _string(_latest(entries, namespace_id, f"name_{index}"), f"name_{index}")
        if not name or any(ord(char) < 32 for char in name):
            raise ExportError(f"invalid name filter in name_{index}")
        names.append(name)
    return ouis, names


def _cpp_literal(value: str) -> str:
    # Fixed-width octal escapes preserve UTF-8 bytes and avoid C++ hex escapes
    # consuming a following digit. Escape '?' as well to avoid trigraphs.
    parts = []
    for byte in value.encode("utf-8"):
        if 32 <= byte <= 126 and byte not in (34, 63, 92):
            parts.append(chr(byte))
        else:
            parts.append(f"\\{byte:03o}")
    return '"' + "".join(parts) + '"'


def make_header(ouis: list[str], names: list[str]) -> bytes:
    lines = [
        "// Pervert-Detector filter seed from the validated detector NVS backup.",
        "// Contains only OUI and BLE name filters; no radio key or AP credentials.",
        "#pragma once",
        "#include <stddef.h>",
        "",
        "static const char* const kOuis[] = {",
        *(f"    {_cpp_literal(oui)}," for oui in ouis),
        "};",
        "static const size_t kOuiCount = sizeof(kOuis) / sizeof(kOuis[0]);",
        "",
        "static const char* const kNames[] = {",
        *(f"    {_cpp_literal(name)}," for name in names),
        "};",
        "static const size_t kNameCount = sizeof(kNames) / sizeof(kNames[0]);",
        "",
    ]
    return "\n".join(lines).encode("ascii")


def export_header(contents: bytes) -> None:
    directory = OUTPUT.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    directory.chmod(0o700)
    fd, temp_name = tempfile.mkstemp(prefix=".meshdetect-filter-seed-", dir=directory)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_name, 0o600)
        os.replace(temp_name, OUTPUT)
        OUTPUT.chmod(0o600)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nvs", type=Path, default=DEFAULT_NVS,
                        help="old detector NVS backup (default: validated 2026-10-18 backup)")
    parser.add_argument("--check", action="store_true",
                        help="validate the generated header without rewriting it")
    args = parser.parse_args()
    try:
        ouis, names = load_filters(args.nvs.read_bytes())
        contents = make_header(ouis, names)
        if args.check:
            if not OUTPUT.is_file() or OUTPUT.read_bytes() != contents:
                raise ExportError("generated header does not match validated filter backup")
            action = "validated"
        else:
            export_header(contents)
            action = "exported"
    except (ExportError, OSError) as exc:
        print(f"filter seed error: {exc}", file=sys.stderr)
        return 1

    print(f"{action} {len(ouis)} OUI filters and {len(names)} name filters: {OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
