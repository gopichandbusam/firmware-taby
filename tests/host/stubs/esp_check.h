#pragma once

#include "esp_err.h"

#define ESP_ERR_INVALID_ARG 0x102
#define ESP_RETURN_ON_ERROR(expression, tag, message) do { \
    (void)(tag); \
    (void)(message); \
    esp_err_t check_err = (expression); \
    if (check_err != ESP_OK) return check_err; \
} while (0)
