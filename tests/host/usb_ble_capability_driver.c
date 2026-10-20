#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cJSON.h"
#include "taby_identity.h"

static int capability_count;

cJSON *cJSON_CreateString(const char *value) {
    cJSON *item = calloc(1, sizeof(*item));
    if (item && value && strcmp(value, "bluetooth_v2") == 0) {
        item->is_bluetooth_v2 = 1;
    }
    return item;
}

void cJSON_AddItemToArray(cJSON *array, cJSON *item) {
    (void)array;
    if (item) {
        capability_count += item->is_bluetooth_v2;
        free(item);
    }
}

/* With no firmware helper yet, the missing capability is observable as zero. */
__attribute__((weak)) void taby_usb_add_ble_v2_capability(
    cJSON *capabilities, const taby_identity_t *identity, const char *firmware_version) {
    (void)capabilities;
    (void)identity;
    (void)firmware_version;
}

int main(int argc, char **argv) {
    if (argc != 3) return 2;
    taby_identity_t identity = {0};
    if (strcmp(argv[1], "__NONTERMINATED__") == 0) {
        memset(identity.device_id, 'x', sizeof(identity.device_id));
    } else {
        snprintf(identity.device_id, sizeof(identity.device_id), "%s", argv[1]);
    }
    cJSON array = {0};
    taby_usb_add_ble_v2_capability(&array, &identity, argv[2]);
    printf("%d\n", capability_count);
    return 0;
}
