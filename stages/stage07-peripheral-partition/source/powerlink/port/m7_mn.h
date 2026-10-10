/* P3a single-task passive MN boundary. No NMT reset/start/send API. */
#ifndef M7_POWERLINK_MN_H
#define M7_POWERLINK_MN_H
#include <stddef.h>
#include <stdint.h>
enum M7MnState { M7_MN_COLD, M7_MN_IDLE, M7_MN_PREPARED, M7_MN_FAULT };
typedef struct {
    uint32_t state, owner, lastError, lastEvent, nmtState;
    uint64_t processes, events;
} M7MnStatus;
int m7_mn_cdc_valid(const uint8_t* data, size_t length);
uint32_t m7_mn_initialize(void);
uint32_t m7_mn_prepare(void);
uint32_t m7_mn_process(void);
uint32_t m7_mn_stop(void);
uint32_t m7_mn_exit(void);
uint32_t m7_mn_status(M7MnStatus* out);
#endif
