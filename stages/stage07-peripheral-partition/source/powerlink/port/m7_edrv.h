#ifndef M7_EDRV_H
#define M7_EDRV_H
#include <kernel/edrv.h>
/* P1 polling baseline, NOT a real-time MN scheduler. All calls must be serialized
 * by one UP2 owner; no ISR/timer may concurrently modify driver or stack state.
 * Callbacks may send/free TX, but may not init/exit/poll recursively. RX callbacks
 * must consume synchronously. Deferred RX, auto-response and launch-time are OFF.
 */
tOplkError m7_edrv_poll(UINT rxBudget);
typedef struct {
    UINT32 txCompleted, txErrors, rxDelivered, rxDropped, rxErrors;
    UINT32 rxDeferredRejected, dmaFatal;
} tM7EdrvStats;
const tM7EdrvStats* m7_edrv_stats(void);
#endif
