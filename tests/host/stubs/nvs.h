#pragma once

#include <stdint.h>
#include "esp_err.h"

#define ESP_ERR_NVS_NOT_FOUND 0x1102
#define NVS_READONLY 1
#define NVS_READWRITE 2

typedef int nvs_handle_t;

esp_err_t nvs_open(const char *name, int open_mode, nvs_handle_t *out_handle);
esp_err_t nvs_get_u8(nvs_handle_t handle, const char *key, uint8_t *out_value);
esp_err_t nvs_set_u8(nvs_handle_t handle, const char *key, uint8_t value);
esp_err_t nvs_commit(nvs_handle_t handle);
void nvs_close(nvs_handle_t handle);
