/* SDK boundaries for verbatim production lifecycle functions selected by the
 * Python harness. Real transport preference loading/commit logic is included. */
#include <assert.h>
#include <inttypes.h>
#include <stdatomic.h>
#include <pthread.h>
#include <errno.h>
#include "esp_log.h"
#include "esp_check.h"
#include "taby_ble_transport.h"
#include "nvs.h"
#include <stdlib.h>
#include <string.h>

static bool ready_at_commit;
static struct { int done; int pref; } durable, staged;
static int commits;
static const char *fail_stage;
esp_err_t nvs_open(const char *name, int mode, nvs_handle_t *handle) {
    staged = durable; *handle = 1; return ESP_OK;
}
esp_err_t nvs_get_u8(nvs_handle_t handle, const char *key, uint8_t *out) {
    *out = !strcmp(key, "done") ? durable.done : durable.pref; return ESP_OK;
}
esp_err_t nvs_set_u8(nvs_handle_t handle, const char *key, uint8_t value) {
    if (!strcmp(key, "done")) staged.done = value; else staged.pref = value;
    return ESP_OK;
}
esp_err_t nvs_commit(nvs_handle_t handle) {
    ready_at_commit = taby_ble_transport_is_ready();
    if (fail_stage) return ESP_FAIL;
    durable = staged; commits++; return ESP_OK;
}
void nvs_close(nvs_handle_t handle) {}
#include "../../firmware/main/taby_transport_prefs.c"

#define ESP_ERR_INVALID_STATE 0x103
#define ESP_ERR_NO_MEM 0x101
#define ESP_ERROR_CHECK(x) assert((x) == ESP_OK)
#define BLE_UUID128_INIT(...) {0}
typedef int ble_uuid128_t;
typedef void *QueueHandle_t;
typedef void *TaskHandle_t;
typedef int taby_ble_command_job_t;
#define BLE_OWN_ADDR_PUBLIC 0
#define BLE_HS_CONN_HANDLE_NONE 65535
#define BLE_HS_EALREADY 2
#define BLE_HS_ENOTCONN 7
#define BLE_ERR_REM_USER_CONN_TERM 19
#define BLE_HS_ADV_F_DISC_GEN 2
#define BLE_HS_ADV_F_BREDR_UNSUP 4
#define BLE_GAP_CONN_MODE_UND 2
#define BLE_GAP_DISC_MODE_GEN 2
#define BLE_HS_FOREVER -1
#define pdPASS 1
#define MALLOC_CAP_INTERNAL 1
#define TABY_WIFI_MODE_STATION 1
#define BLE_NPL_OK 0
#define NIMBLE_HS_STACK_SIZE 4096
#define NIMBLE_CORE 0
#define configMAX_PRIORITIES 25
enum { BLE_GAP_EVENT_CONNECT, BLE_GAP_EVENT_DISCONNECT, BLE_GAP_EVENT_SUBSCRIBE,
       BLE_GAP_EVENT_CONN_UPDATE, BLE_GAP_EVENT_ADV_COMPLETE, BLE_GAP_EVENT_MTU };
struct ble_gap_event {
    int type;
    struct { int status; uint16_t conn_handle; } connect;
    struct { struct { uint16_t conn_handle; } conn; int reason; } disconnect;
    struct { uint16_t attr_handle; int cur_notify; } subscribe;
    struct { uint16_t conn_handle; int status; } conn_update;
    struct { int reason; } adv_complete;
    struct { unsigned value; } mtu;
};
struct ble_hs_adv_fields { int flags; ble_uuid128_t *uuids128; int num_uuids128; int uuids128_is_complete;
    const uint8_t *name; size_t name_len; int name_is_complete; };
struct ble_gap_adv_params { int conn_mode; int disc_mode; };
struct { void (*reset_cb)(int); void (*sync_cb)(void); int sm_bonding; int sm_mitm; int sm_sc; } ble_hs_cfg;
struct ble_npl_event { int unused; };
typedef uint32_t ble_npl_time_t;
struct ble_npl_callout { void (*callback)(struct ble_npl_event *); bool pending; bool initialized; };
static struct ble_npl_callout *timer;
static void (*stale_callback)(struct ble_npl_event *);
static int last_delay, backoff = 1;
static int starts, stops, adv_calls, pref_at_stop = -1, shown, usb, display, onboarding, usb_before_ble;
static int before_resync;
static const char *failure;
static atomic_bool controller_active;
static int duplicates, starts_after_stop_intent;
static bool production_desired_active(void);
/* Controlled SDK pause after the production guard, before adv_start. The
 * contender signals either SDK progress (old code) or mutex contention (fixed
 * code). No timing sleeps are needed to choose either interleaving. */
static pthread_mutex_t gate = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_changed = PTHREAD_COND_INITIALIZER;
static bool race_enabled, first_paused, release_first, contender_observed;
static bool ensure_returned_while_paused, delay_shutdown_callbacks, delayed_adv_complete;
static const char *race_operation;
static pthread_t first_thread;
static void observe_contender(void) {
    pthread_mutex_lock(&gate);
    contender_observed = true;
    pthread_cond_broadcast(&gate_changed);
    pthread_mutex_unlock(&gate);
}
typedef pthread_mutex_t *SemaphoreHandle_t;
#define portMAX_DELAY -1
#define pdTRUE 1
static SemaphoreHandle_t xSemaphoreCreateMutex(void) {
    pthread_mutex_t *mutex = malloc(sizeof(*mutex));
    assert(mutex && pthread_mutex_init(mutex, NULL) == 0);
    return mutex;
}
static int xSemaphoreTake(SemaphoreHandle_t mutex, int ticks) {
    int rc = pthread_mutex_trylock(mutex);
    if (rc == 0) return pdTRUE;
    assert(rc == EBUSY);
    if (race_enabled && ticks) observe_contender();
    if (!ticks) return 0;
    assert(pthread_mutex_lock(mutex) == 0);
    return pdTRUE;
}
static void xSemaphoreGive(SemaphoreHandle_t mutex) { assert(pthread_mutex_unlock(mutex) == 0); }
static taby_identity_t identity = {.device_id = "taby-123456"};
static int gap_event_handler(struct ble_gap_event *, void *);
static bool fails(const char *name) { return !strcmp(failure, name); }
static const char *esp_err_to_name(int err) { return err == ESP_OK ? "ESP_OK" : "ESP_FAIL"; }
static int bt_controller_status_for_log(void) { return 0; }
static uint32_t esp_get_free_heap_size(void) { return 100000; }
static uint32_t heap_caps_get_free_size(int caps) { return 100000; }
static void publish_event_payload(const char *payload, bool notify) {}
static void notify_last_event_payload(void) {}
static void request_fast_connection_params(uint16_t conn) {}
static bool taby_ble_v2_format_identity_json(const char *id, const char *version, char *out, size_t n) { snprintf(out, n, "identity"); return true; }
static const char *taby_firmware_version(void) { return "test"; }
static int nimble_port_init(void) { starts++; usb_before_ble = usb; return fails("init") ? ESP_FAIL : ESP_OK; }
static int nimble_port_deinit(void) { assert(!timer || !timer->initialized); return 0; }
static int nimble_port_stop(void) {
    if (race_enabled && !strcmp(race_operation, "race_shutdown")) {
        pthread_mutex_lock(&gate);
        contender_observed = true; pthread_cond_broadcast(&gate_changed);
        while (!release_first) pthread_cond_wait(&gate_changed, &gate);
        pthread_mutex_unlock(&gate);
    }
    stops++; pref_at_stop = durable.pref;
    if (fails("stop")) return 1;
    controller_active = false; return 0;
}
static int init_gatt_services(void) { return fails("gatt") ? 1 : 0; }
static int ble_svc_gap_device_name_set(const char *name) { return fails("name") ? 1 : 0; }
static void ble_host_task(void *arg) {}
static void ble_command_task(void *arg) {}
static void nimble_port_freertos_init(void (*task)(void *)) { if (!fails("host")) ble_hs_cfg.sync_cb(); }
static int xTaskCreatePinnedToCore(void (*task)(void *), const char *name, int stack, void *arg,
                                   int priority, void **handle, int core) {
    if (fails("host")) return 0;
    ble_hs_cfg.sync_cb(); return pdPASS;
}
static void *xQueueCreate(int n, size_t size) { return fails("queue") ? NULL : (void *)1; }
static void vQueueDelete(void *queue) {}
static int xTaskCreate(void (*task)(void *), const char *name, int stack, void *arg, int pri, void **out) {
    if (fails("command_task")) return 0;
    *out = (void *)1; return pdPASS;
}
static int ble_gap_adv_set_fields(struct ble_hs_adv_fields *fields) {
    if (race_enabled && pthread_equal(pthread_self(), first_thread)) {
        pthread_mutex_lock(&gate);
        first_paused = true; pthread_cond_broadcast(&gate_changed);
        while (!release_first) pthread_cond_wait(&gate_changed, &gate);
        pthread_mutex_unlock(&gate);
    }
    return 0;
}
static int ble_gap_adv_rsp_set_fields(struct ble_hs_adv_fields *fields) { return 0; }
static int ble_gap_adv_start(int own_addr, void *peer, int duration, struct ble_gap_adv_params *params,
                             int (*cb)(struct ble_gap_event *, void *), void *arg) {
    adv_calls++;
    if (!production_desired_active()) starts_after_stop_intent++;
    if (fails("already")) controller_active = true;
    if (atomic_exchange(&controller_active, true)) { duplicates++; return BLE_HS_EALREADY; }
    if (fails("adv_always") || (fails("adv_once") && adv_calls == 1)) { controller_active = false; return 22; }
    return 0;
}
static int ble_hs_id_infer_auto(int privacy, uint8_t *out) { *out = 0; return 0; }
static int ble_gap_adv_stop(void) {
    controller_active = false;
    if (delay_shutdown_callbacks) { delayed_adv_complete = true; return 0; }
    struct ble_gap_event e = {.type = BLE_GAP_EVENT_ADV_COMPLETE};
    gap_event_handler(&e, NULL);
    return 0;
}
static int ble_gap_terminate(uint16_t conn, int reason) {
    struct ble_gap_event e = {.type = BLE_GAP_EVENT_DISCONNECT};
    e.disconnect.conn.conn_handle = conn;
    gap_event_handler(&e, NULL);
    return 0;
}
static void *nimble_port_get_dflt_eventq(void) { return (void *)1; }
static int ble_npl_callout_init(struct ble_npl_callout *co, void *q, void (*cb)(struct ble_npl_event *), void *arg) {
    if (fails("retry_timer")) return 1;
    assert(!co->initialized); co->initialized = true; co->callback = cb; timer = co; stale_callback = cb; return 0;
}
static void ble_npl_callout_stop(struct ble_npl_callout *co) { assert(co->initialized); co->pending = false; }
static void ble_npl_callout_deinit(struct ble_npl_callout *co) { assert(co->initialized); co->initialized = false; co->pending = false; }
static int ble_npl_callout_reset(struct ble_npl_callout *co, uint32_t ticks) {
    assert(co->initialized);
    if ((int)ticks <= last_delay || ticks > 10000) backoff = 0;
    last_delay = ticks; co->pending = true; return 0;
}
static uint32_t ble_npl_time_ms_to_ticks32(uint32_t ms) { return ms; }
static void fire_retry(void) {
    if (timer && timer->pending) { timer->pending = false; timer->callback(NULL); }
}
static const taby_identity_t *taby_identity_get_fake(void) { return &identity; }
#define taby_identity_get taby_identity_get_fake
static int taby_wifi_shutdown(void) { return 0; }
static bool taby_wifi_is_provisioned(void) { return false; }
static int taby_wifi_start_setup_mode(const taby_identity_t *id) { return 0; }
static int taby_wifi_mode(void) { return 0; }
static bool taby_wifi_is_connected(void) { return false; }
static int taby_wifi_connect_saved_networks(void) { return 0; }
static void taby_onboarding_show_transport_banner(int mode) { shown = mode; }
static void taby_onboarding_show_usb_hint(void) { shown = 1; }
static void taby_onboarding_show_wifi_setup(void) { shown = 2; }
static void taby_onboarding_show_bluetooth_hint(void) { shown = 3; }
static void taby_runtime_refresh_current_state(void) {}
static int taby_identity_init_fake(void) { return 0; }
#define taby_identity_init taby_identity_init_fake
static int board_amoled_1_64_init(void) { display++; return 0; }
static void taby_reusable_ui_start(void) {}
static void taby_asset_store_init(void) {}
static void taby_runtime_start(void) {}
static int taby_power_button_start(void) { return 0; }
static int taby_usb_serial_init(void) { usb++; return 0; }
static int taby_power_init(void) { return 0; }
static int taby_wifi_init(const taby_identity_t *id) { return 0; }
static void taby_onboarding_start(void) { onboarding++; }

#include "production_lifecycle.h"

static bool production_desired_active(void) { return s_desired_active; }
static void *race_first(void *arg) {
    first_thread = pthread_self();
    if (!strcmp(race_operation, "race_ensure")) stale_callback(NULL);
    else taby_ble_transport_ensure_advertising();
    return NULL;
}
static void *race_contender(void *arg) {
    if (!strcmp(race_operation, "race_shutdown")) taby_ble_transport_shutdown();
    else if (!strcmp(race_operation, "race_ensure")) {
        taby_ble_transport_ensure_advertising();
        pthread_mutex_lock(&gate);
        ensure_returned_while_paused = !release_first;
        pthread_mutex_unlock(&gate);
    }
    else stale_callback(NULL);
    observe_contender();
    return NULL;
}
static void run_race(const char *op) {
    race_operation = op; race_enabled = true;
    pthread_t first, second;
    assert(pthread_create(&first, NULL, race_first, NULL) == 0);
    pthread_mutex_lock(&gate);
    while (!first_paused) pthread_cond_wait(&gate_changed, &gate);
    pthread_mutex_unlock(&gate);
    assert(pthread_create(&second, NULL, race_contender, NULL) == 0);
    pthread_mutex_lock(&gate);
    while (!contender_observed) pthread_cond_wait(&gate_changed, &gate);
    release_first = true; pthread_cond_broadcast(&gate_changed);
    pthread_mutex_unlock(&gate);
    pthread_join(first, NULL); pthread_join(second, NULL);
    race_enabled = false;
}

int main(int argc, char **argv) {
    if (argc != 5) return 2;
    const char *op = argv[1]; durable.pref = atoi(argv[2]); durable.done = atoi(argv[3]); failure = argv[4];
    int result = 0;
    if (!strcmp(op, "boot") || !strcmp(op, "factory")) {
        identity.has_factory_data = !strcmp(op, "factory"); app_main();
    } else {
        assert(taby_transport_prefs_init() == ESP_OK);
        if (strstr(op, "usb")) assert(taby_ble_transport_init(&identity) == ESP_OK);
        if (fails("commit")) fail_stage = "commit";
        if (!strcmp(op, "mode_bt")) result = taby_onboarding_activate_transport_mode(3);
        else if (!strcmp(op, "default_bt")) result = taby_onboarding_set_transport_default(3);
        else if (!strcmp(op, "mode_usb")) result = taby_onboarding_activate_transport_mode(1);
        else if (!strcmp(op, "default_usb")) result = taby_onboarding_set_transport_default(1);
        else {
            assert(taby_ble_transport_init(&identity) == ESP_OK);
            if (!strncmp(op, "race_", 5)) run_race(op);
            else if (!strcmp(op, "delayed_shutdown")) {
                delay_shutdown_callbacks = true;
                taby_ble_transport_shutdown();
                assert(delayed_adv_complete);
                struct ble_gap_event e = {.type = BLE_GAP_EVENT_ADV_COMPLETE};
                gap_event_handler(&e, NULL);
                e.type = BLE_GAP_EVENT_DISCONNECT;
                gap_event_handler(&e, NULL);
            }
            else if (!strcmp(op, "retry")) { for (int i = 0; i < 20; i++) fire_retry(); }
            else if (!strcmp(op, "recover_early")) { taby_ble_transport_ensure_advertising(); fire_retry(); }
            else if (!strcmp(op, "cancel_retry")) { taby_ble_transport_shutdown(); if (stale_callback) stale_callback(NULL); }
            else if (!strcmp(op, "reset_retry")) {
                controller_active = false; on_reset(1); fire_retry(); before_resync = adv_calls; on_sync();
            } else if (!strcmp(op, "restart")) {
                taby_ble_transport_init(&identity); taby_ble_transport_shutdown(); taby_ble_transport_shutdown();
                taby_ble_transport_init(&identity);
            } else {
                struct ble_gap_event e = {.type = BLE_GAP_EVENT_CONNECT};
                e.connect.conn_handle = 10;
                if (strstr(op, "connected") || !strcmp(op, "disconnect")) { controller_active = false; gap_event_handler(&e, NULL); }
                if (strstr(op, "shutdown")) taby_ble_transport_shutdown();
                else {
                    e.type = !strcmp(op, "disconnect") ? BLE_GAP_EVENT_DISCONNECT :
                             !strcmp(op, "connect_fail") ? BLE_GAP_EVENT_CONNECT : BLE_GAP_EVENT_ADV_COMPLETE;
                    controller_active = false; e.connect.status = 1; gap_event_handler(&e, NULL);
                }
            }
        }
    }
    printf("result=%d starts=%d stops=%d adv_calls=%d durable=%d live=%d commits=%d ready=%d advertising=%d "
           "ready_at_commit=%d pref_at_stop=%d shown=%d usb=%d display=%d onboarding=%d usb_before_ble=%d "
           "pending=%d backoff=%d before_resync=%d controller_active=%d duplicates=%d starts_after_stop_intent=%d ensure_returned_while_paused=%d error=%s\n", result, starts, stops, adv_calls, durable.pref,
           taby_transport_preferred_mode(), commits, taby_ble_transport_is_ready(), taby_ble_transport_is_advertising(),
           ready_at_commit, pref_at_stop, shown, usb, display, onboarding, usb_before_ble,
           timer && timer->pending, backoff, before_resync, controller_active, duplicates, starts_after_stop_intent, ensure_returned_while_paused,
           taby_ble_transport_last_error()[0] ? taby_ble_transport_last_error() : "none");
    return 0;
}
