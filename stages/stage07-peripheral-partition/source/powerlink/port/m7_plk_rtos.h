/* Single-task P2 contract. P3 must gate every public stack/EDRV entry with this
 * owner check and pump timers and EDRV from the same task. No ISR callbacks. */
#ifndef M7_PLK_RTOS_H
#define M7_PLK_RTOS_H
#include <common/oplkinc.h>
typedef struct {
    uint64_t interrupts, callbacks, skipped_periods, max_late_ticks;
    uint32_t frequency;
    int leased, dispatching;
} M7PlkTimerStats;
int m7_plk_owner(void);
int m7_plk_ready(void);
void m7_plk_fault(void);
int m7_plk_faulted(void);
int m7_hrestimer_active(void);
void m7_hrestimer_interrupt(void);
tOplkError m7_hrestimer_process(void);
void m7_hrestimer_stats(M7PlkTimerStats* stats);
/* Exact conversion, ceil; 0/overflow or > INT64_MAX ticks are rejected. */
int m7_hrestimer_ticks(uint64_t ns, uint32_t frequency, uint64_t* ticks);
#endif
