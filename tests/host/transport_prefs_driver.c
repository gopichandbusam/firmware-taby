#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "nvs.h"
#include "taby_transport_prefs.h"

typedef struct {
    int done;
    int pref;
} pair_t;

static pair_t durable;
static pair_t staged;
static bool handle_open;
static int handle_mode;
static int opens;
static int closes;
static int commits;
static const char *fail_stage;
static int set_calls;

static bool fail_at(const char *stage) {
    if (fail_stage && strcmp(fail_stage, stage) == 0) {
        fail_stage = NULL;
        return true;
    }
    return false;
}

esp_err_t nvs_open(const char *name, int mode, nvs_handle_t *out_handle) {
    if (strcmp(name, "taby_setup") != 0 || !out_handle || handle_open) return ESP_FAIL;
    if (fail_at("open")) return ESP_FAIL;
    if (mode == NVS_READONLY && durable.done < 0 && durable.pref < 0) return ESP_ERR_NVS_NOT_FOUND;
    if (mode != NVS_READONLY && mode != NVS_READWRITE) return ESP_FAIL;
    handle_open = true;
    handle_mode = mode;
    staged = durable;
    set_calls = 0;
    *out_handle = 1;
    opens++;
    return ESP_OK;
}

esp_err_t nvs_get_u8(nvs_handle_t handle, const char *key, uint8_t *value) {
    if (handle != 1 || !handle_open || !value) return ESP_FAIL;
    int stored;
    if (strcmp(key, "done") == 0) stored = durable.done;
    else if (strcmp(key, "pref") == 0) stored = durable.pref;
    else return ESP_FAIL;
    if (stored < 0) return ESP_ERR_NVS_NOT_FOUND;
    *value = (uint8_t)stored;
    return ESP_OK;
}

esp_err_t nvs_set_u8(nvs_handle_t handle, const char *key, uint8_t value) {
    if (handle != 1 || !handle_open || handle_mode != NVS_READWRITE) return ESP_FAIL;
    set_calls++;
    if (fail_at(set_calls == 1 ? "first_set" : "second_set")) return ESP_FAIL;
    if (strcmp(key, "done") == 0) staged.done = value;
    else if (strcmp(key, "pref") == 0) staged.pref = value;
    else return ESP_FAIL;
    return ESP_OK;
}

esp_err_t nvs_commit(nvs_handle_t handle) {
    if (handle != 1 || !handle_open || handle_mode != NVS_READWRITE) return ESP_FAIL;
    if (fail_at("commit")) return ESP_FAIL;
    durable = staged;
    commits++;
    return ESP_OK;
}

void nvs_close(nvs_handle_t handle) {
    if (handle != 1 || !handle_open) abort();
    handle_open = false;
    closes++;
}

/* Include the actual firmware source so this host driver can discard its static RAM state. */
#include "../../firmware/main/taby_transport_prefs.c"

static void reboot(void) {
    s_state = (taby_transport_prefs_state_t){0};
    if (taby_transport_prefs_init() != ESP_OK) abort();
}

int main(int argc, char **argv) {
    if (argc != 7) return 2;
    durable.done = atoi(argv[1]);
    durable.pref = atoi(argv[2]);
    const char *operation = argv[3];
    int candidate_pref = atoi(argv[4]);
    int candidate_done = atoi(argv[5]);
    if (taby_transport_prefs_init() != ESP_OK) return 3;
    int before_done = taby_transport_onboarding_complete();
    int before_pref = taby_transport_preferred_mode();
    fail_stage = strcmp(argv[6], "none") == 0 ? NULL : argv[6];

    esp_err_t result;
    if (strcmp(operation, "set") == 0) {
        result = taby_transport_set_preferred_mode(candidate_pref, candidate_done != 0);
    } else if (strcmp(operation, "clear") == 0) {
        result = taby_transport_clear_onboarding();
    } else if (strcmp(operation, "reset") == 0) {
        result = taby_transport_reset_incomplete_on_boot();
    } else {
        return 4;
    }
    int after_done = taby_transport_onboarding_complete();
    int after_pref = taby_transport_preferred_mode();
    int durable_done = durable.done;
    int durable_pref = durable.pref;
    reboot();
    printf("before=%d,%d result=%d after=%d,%d durable=%d,%d reboot=%d,%d opens=%d closes=%d commits=%d\n",
           before_done, before_pref, result, after_done, after_pref,
           durable_done, durable_pref, taby_transport_onboarding_complete(),
           taby_transport_preferred_mode(), opens, closes, commits);
    return handle_open ? 5 : 0;
}
