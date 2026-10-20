#pragma once

typedef struct cJSON {
    int is_bluetooth_v2;
} cJSON;

cJSON *cJSON_CreateString(const char *value);
void cJSON_AddItemToArray(cJSON *array, cJSON *item);
