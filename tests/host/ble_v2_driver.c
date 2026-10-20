/* Host-only probe for the real BLE protocol-v2 payload formatter. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "taby_ble_protocol_v2.h"

static int hex_value(char ch) {
    if (ch >= '0' && ch <= '9') return ch - '0';
    if (ch >= 'a' && ch <= 'f') return ch - 'a' + 10;
    if (ch >= 'A' && ch <= 'F') return ch - 'A' + 10;
    return -1;
}

int main(int argc, char **argv) {
    if (argc < 2) {
        return 2;
    }

    if (strcmp(argv[1], "available") == 0 && argc == 6) {
        const char *id = strcmp(argv[4], "null") == 0 ? NULL : argv[2];
        const char *version = strcmp(argv[5], "null") == 0 ? NULL : argv[3];
        printf("%d\n", taby_ble_v2_identity_available(id, version) ? 1 : 0);
        return 0;
    }

    if (strcmp(argv[1], "version-hex") == 0 && argc == 3) {
        size_t hex_length = strlen(argv[2]);
        if (!hex_length || (hex_length & 1U) || hex_length > 160U) {
            return 2;
        }
        char version[81];
        for (size_t i = 0; i < hex_length; i += 2) {
            int high = hex_value(argv[2][i]);
            int low = hex_value(argv[2][i + 1]);
            if (high < 0 || low < 0 || (high == 0 && low == 0)) {
                return 2;
            }
            version[i / 2] = (char)((high << 4) | low);
        }
        version[hex_length / 2] = '\0';
        char payload[512] = {0};
        bool available = taby_ble_v2_identity_available("id", version);
        bool formatted = taby_ble_v2_format_identity_json("id", version, payload, sizeof(payload));
        printf("%d\t%d\t", available ? 1 : 0, formatted ? 1 : 0);
        for (size_t i = 0; payload[i]; ++i) {
            printf("%02x", (unsigned char)payload[i]);
        }
        putchar('\n');
        return 0;
    }

    char output[512] = {0};
    bool ok = false;
    if (strcmp(argv[1], "identity") == 0 && argc == 8) {
        size_t out_size = (size_t)strtoul(argv[4], NULL, 10);
        if (out_size > sizeof(output)) {
            return 2;
        }
        const char *id = strcmp(argv[5], "null") == 0 ? NULL : argv[2];
        const char *version = strcmp(argv[6], "null") == 0 ? NULL : argv[3];
        char *out = strcmp(argv[7], "null") == 0 ? NULL : output;
        ok = taby_ble_v2_format_identity_json(id, version, out, out_size);
    } else if (strcmp(argv[1], "choice") == 0 && argc == 6) {
        size_t out_size = (size_t)strtoul(argv[4], NULL, 10);
        if (out_size > sizeof(output)) {
            return 2;
        }
        char *out = strcmp(argv[5], "null") == 0 ? NULL : output;
        ok = taby_ble_v2_format_choice_json(
            (uint32_t)strtoul(argv[2], NULL, 10),
            (taby_reusable_choice_selection_t)strtol(argv[3], NULL, 10),
            out,
            out_size);
    } else {
        return 2;
    }

    printf("%d\t%s\n", ok ? 1 : 0, output);
    return 0;
}
