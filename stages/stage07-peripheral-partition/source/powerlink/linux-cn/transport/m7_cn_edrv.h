#ifndef M7_CN_EDRV_H
#define M7_CN_EDRV_H
#include <stdint.h>
/* Transport component ONLY. No frontend/stack-destroy or hardware approval.
 * The upstream demo does not arm this driver, so init refuses before socket(). */
#define M7_CN_MAX_TX 2048U
#define M7_CN_MAX_RX 4096U
#define M7_CN_ACTIVE_NS UINT64_C(8000000000)
#define M7_CN_JOIN_NS UINT64_C(1000000000)
typedef struct {
    uint32_t armed,attempted,active,stop_attempted,joined,closed,fault,inflight,clock_failed,close_attempted;
    uint64_t tx_attempts,tx_accepted,rx_seen,rx_delivered,rx_dropped;
} M7CnEdrvStats;
/* One owner thread, exactly one grant. Validates eth2/SR9900/onboard USB path.
 * It performs read-only identity checks; it is NOT user approval or IP checks. */
int m7_cn_edrv_arm(void);
void m7_cn_edrv_stats(M7CnEdrvStats* out);
#endif
