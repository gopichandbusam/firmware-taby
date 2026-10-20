#pragma once

#include "cJSON.h"
#include "taby_identity.h"

void taby_usb_add_ble_v2_capability(
    cJSON *capabilities, const taby_identity_t *identity, const char *firmware_version);
