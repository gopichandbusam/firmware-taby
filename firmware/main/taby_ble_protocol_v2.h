#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "taby_reusable_ui.h"

#define TABY_BLE_PROTOCOL_VERSION 2U

bool taby_ble_v2_identity_available(
    const char *device_id,
    const char *firmware_version);

bool taby_ble_v2_format_identity_json(
    const char *device_id,
    const char *firmware_version,
    char *out,
    size_t out_size);

bool taby_ble_v2_format_choice_json(
    uint32_t signal,
    taby_reusable_choice_selection_t selection,
    char *out,
    size_t out_size);
