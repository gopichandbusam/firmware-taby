#include "taby_usb_ble_v2_capability.h"

#include <string.h>

#include "taby_ble_protocol_v2.h"

void taby_usb_add_ble_v2_capability(
    cJSON *capabilities, const taby_identity_t *identity, const char *firmware_version) {
    if (capabilities && identity &&
        memchr(identity->device_id, '\0', sizeof(identity->device_id)) &&
        taby_ble_v2_identity_available(identity->device_id, firmware_version)) {
        cJSON_AddItemToArray(capabilities, cJSON_CreateString("bluetooth_v2"));
    }
}
