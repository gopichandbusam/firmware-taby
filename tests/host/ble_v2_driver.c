/* Host-only probe for the real BLE protocol-v2 payload formatter. */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "taby_ble_protocol_v2.h"

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
