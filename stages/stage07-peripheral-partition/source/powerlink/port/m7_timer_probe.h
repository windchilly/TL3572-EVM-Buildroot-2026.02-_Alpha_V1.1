/* Explicit P3c diagnostic only. Pure types across the RTOS/PLK boundary. */
#ifndef M7_TIMER_PROBE_H
#define M7_TIMER_PROBE_H
#include <stdint.h>
typedef struct {
    uint64_t counter, ticks, affinity, interrupts, maxIrqLate;
    uint32_t level, frequency, cntp, cntv, enabled, pending, active;
    uint32_t group, config, priority30, priority27;
    uint32_t typer, cpuControl;
} M7TimerHardware;
typedef struct {
    M7TimerHardware before, after;
    uint64_t callbacks, maxTaskLate;
    uint32_t result, clean, samples;
} M7TimerProbeResult;
enum { M7_TIMER_OK, M7_TIMER_CONTEXT, M7_TIMER_ACQUIRE, M7_TIMER_NO_IRQ,
       M7_TIMER_COUNTS, M7_TIMER_CALLBACK, M7_TIMER_CLEANUP, M7_TIMER_STATE,
       M7_TIMER_TICK, M7_TIMER_TIMEOUT };
/* May trap if firmware denies CNTP access; no fallback/automatic reboot. */
int m7_timer_diag_reset(void);
int m7_timer_diag_snapshot(M7TimerHardware* out);
uint32_t m7_timer_probe(M7TimerProbeResult* out);
#endif
