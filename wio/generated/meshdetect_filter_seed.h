// Pervert-Detector filter seed from the validated detector NVS backup.
// Contains only OUI and BLE name filters; no radio key or AP credentials.
#pragma once
#include <stddef.h>

static const char* const kOuis[] = {
    "7C:2A:9E",
    "CC:66:0A",
    "F4:03:43",
    "5C:E9:1E",
    "98:59:49",
};
static const size_t kOuiCount = sizeof(kOuis) / sizeof(kOuis[0]);

static const char* const kNames[] = {
    "Oakley",
    "Meta",
};
static const size_t kNameCount = sizeof(kNames) / sizeof(kNames[0]);
