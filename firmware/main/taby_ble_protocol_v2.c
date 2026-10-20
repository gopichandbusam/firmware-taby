#include "taby_ble_protocol_v2.h"

#include <stdio.h>

#define TABY_BLE_DEVICE_ID_MAX 120U
#define TABY_BLE_FIRMWARE_VERSION_MAX 80U

static bool valid_device_id(const char *device_id) {
    if (!device_id || !device_id[0]) {
        return false;
    }
    for (size_t i = 0; i <= TABY_BLE_DEVICE_ID_MAX; ++i) {
        unsigned char ch = (unsigned char)device_id[i];
        if (!ch) {
            return true;
        }
        if (i == TABY_BLE_DEVICE_ID_MAX ||
            !((ch >= 'A' && ch <= 'Z') ||
              (ch >= 'a' && ch <= 'z') ||
              (ch >= '0' && ch <= '9') ||
              ch == '.' || ch == '_' || ch == ':' || ch == '-')) {
            return false;
        }
    }
    return false;
}

static bool valid_firmware_version(const char *version) {
    if (!version || !version[0]) {
        return false;
    }
    size_t i = 0;
    while (i < TABY_BLE_FIRMWARE_VERSION_MAX && version[i]) {
        unsigned char lead = (unsigned char)version[i];
        if (lead < 0x80) {
            ++i;
            continue;
        }

        size_t continuation_count;
        unsigned char first_min = 0x80;
        unsigned char first_max = 0xbf;
        if (lead >= 0xc2 && lead <= 0xdf) {
            continuation_count = 1;
        } else if (lead >= 0xe0 && lead <= 0xef) {
            continuation_count = 2;
            if (lead == 0xe0) first_min = 0xa0;
            if (lead == 0xed) first_max = 0x9f;
        } else if (lead >= 0xf0 && lead <= 0xf4) {
            continuation_count = 3;
            if (lead == 0xf0) first_min = 0x90;
            if (lead == 0xf4) first_max = 0x8f;
        } else {
            return false;
        }

        if (i + continuation_count >= TABY_BLE_FIRMWARE_VERSION_MAX) {
            return false;
        }
        for (size_t j = 1; j <= continuation_count; ++j) {
            unsigned char ch = (unsigned char)version[i + j];
            unsigned char low = j == 1 ? first_min : 0x80;
            unsigned char high = j == 1 ? first_max : 0xbf;
            if (ch < low || ch > high) {
                return false;
            }
        }
        i += continuation_count + 1;
    }
    return version[i] == '\0';
}

bool taby_ble_v2_identity_available(const char *device_id, const char *firmware_version) {
    return valid_device_id(device_id) && valid_firmware_version(firmware_version);
}

/* Worst case: every input byte requires a six-byte JSON control escape. */
static void escape_version(const char *version, char escaped[TABY_BLE_FIRMWARE_VERSION_MAX * 6U + 1U]) {
    static const char digits[] = "0123456789abcdef";
    size_t used = 0;
    for (const unsigned char *cursor = (const unsigned char *)version; *cursor; ++cursor) {
        unsigned char ch = *cursor;
        if (ch == '"' || ch == '\\') {
            escaped[used++] = '\\';
            escaped[used++] = (char)ch;
        } else if (ch < 0x20) {
            escaped[used++] = '\\';
            escaped[used++] = 'u';
            escaped[used++] = '0';
            escaped[used++] = '0';
            escaped[used++] = digits[ch >> 4];
            escaped[used++] = digits[ch & 0x0f];
        } else {
            escaped[used++] = (char)ch;
        }
    }
    escaped[used] = '\0';
}

bool taby_ble_v2_format_identity_json(
    const char *device_id,
    const char *firmware_version,
    char *out,
    size_t out_size) {
    if (out && out_size) {
        out[0] = '\0';
    }
    if (!out || !out_size || !taby_ble_v2_identity_available(device_id, firmware_version)) {
        return false;
    }

    char escaped_version[TABY_BLE_FIRMWARE_VERSION_MAX * 6U + 1U];
    escape_version(firmware_version, escaped_version);
    int written = snprintf(
        out, out_size,
        "{\"protocol\":%u,\"deviceId\":\"%s\",\"firmwareVersion\":\"%s\"}",
        TABY_BLE_PROTOCOL_VERSION, device_id, escaped_version);
    if (written < 0 || (size_t)written >= out_size) {
        out[0] = '\0';
        return false;
    }
    return true;
}

bool taby_ble_v2_format_choice_json(
    uint32_t signal,
    taby_reusable_choice_selection_t selection,
    char *out,
    size_t out_size) {
    if (out && out_size) {
        out[0] = '\0';
    }
    if (!out || !out_size) {
        return false;
    }

    const char *choice = NULL;
    switch (selection) {
        case TABY_REUSABLE_CHOICE_NONE: choice = "none"; break;
        case TABY_REUSABLE_CHOICE_1: choice = "left"; break;
        case TABY_REUSABLE_CHOICE_2: choice = "right"; break;
        case TABY_REUSABLE_CHOICE_ACTION: choice = "left"; break;
        default: return false;
    }

    int written = snprintf(out, out_size, "{\"signal\":%lu,\"choice\":\"%s\"}",
                           (unsigned long)signal, choice);
    if (written < 0 || (size_t)written >= out_size) {
        out[0] = '\0';
        return false;
    }
    return true;
}
