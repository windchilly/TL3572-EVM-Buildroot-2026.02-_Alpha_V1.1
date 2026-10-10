/* Real target + hrestimer, NOT oplk_initialize/create or Ethernet.
 * 8 one-shots each at 100 us, 1 ms, 10 ms (~89 ms idle-board workload).
 * Process ONLY after a real ISR latch; polling a due counter is not IRQ proof.
 * Per-shot 20 ms timeout + iteration guard. No latency certification claim. */
#include <kernel/hrestimer.h>
#include <common/target.h>
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
#include "m7_timer_probe.h"
static tTimerHdl expectedHandle;
static uint64_t callbackCount;
static tOplkError callback(const tTimerEventArg* event)
{
    if (!m7_plk_ready() || !m7_plk_irq_enabled() || !event ||
        event->timerHdl.handle != expectedHandle || event->argument.value != 0x3572U)
        return kErrorInvalidOperation;
    ++callbackCount; return kErrorOk;
}
uint32_t m7_timer_probe(M7TimerProbeResult* out)
{
    static const uint64_t intervals[] = {100000U, 1000000U, 10000000U};
    M7PlkTimerStats stats = {0};
    uint64_t timeout, start;
    unsigned round, sample;
    int acquired = 0;
    uint32_t result = M7_TIMER_OK;
    if (!out) return M7_TIMER_CONTEXT;
    *out = (M7TimerProbeResult){0};
    if (m7_plk_in_interrupt() || !m7_plk_irq_enabled() || m7_plk_owner() ||
        m7_hrestimer_active()) return out->result = M7_TIMER_CONTEXT;
    if (!m7_timer_diag_reset() || !m7_timer_diag_snapshot(&out->before))
        return out->result = M7_TIMER_CONTEXT;
    if (target_init() != kErrorOk) return out->result = M7_TIMER_CONTEXT;
    if (hrestimer_init() != kErrorOk) {
        if (m7_hrestimer_active()) {
            /* init already attempted stop and failed: no automatic second try */
            (void)m7_timer_diag_snapshot(&out->after);
            return out->result = M7_TIMER_CLEANUP;
        }
        result = M7_TIMER_ACQUIRE; goto cleanup;
    }
    acquired = 1; callbackCount = 0; expectedHandle = 0;
    m7_hrestimer_stats(&stats);
    if (!m7_hrestimer_ticks(20000000U, stats.frequency, &timeout)) {
        result = M7_TIMER_ACQUIRE; goto cleanup;
    }
    for (round = 0; round < 3; ++round) for (sample = 0; sample < 8; ++sample) {
        uint64_t previous = stats.interrupts;
        unsigned spins = 0;
        start = m7_plk_timer_now();
        if (hrestimer_modifyTimer(&expectedHandle, intervals[round], callback, 0x3572U, FALSE)) {
            result = M7_TIMER_CALLBACK; goto cleanup;
        }
        do {
            m7_hrestimer_stats(&stats);
            if (stats.interrupts != previous) break;
            if (m7_plk_timer_now() - start >= timeout) { result = M7_TIMER_NO_IRQ; goto cleanup; }
            if (++spins == 10000000U) { result = M7_TIMER_TIMEOUT; goto cleanup; }
        } while (1);
        if (stats.interrupts != previous + 1U) { result = M7_TIMER_COUNTS; goto cleanup; }
        if (m7_hrestimer_process()) { result = M7_TIMER_CALLBACK; goto cleanup; }
        m7_hrestimer_stats(&stats);
        ++out->samples;
        if (callbackCount != out->samples || stats.callbacks != callbackCount ||
            stats.interrupts != callbackCount) { result = M7_TIMER_COUNTS; goto cleanup; }
        if (hrestimer_deleteTimer(&expectedHandle)) { result = M7_TIMER_CALLBACK; goto cleanup; }
    }
cleanup:
    m7_hrestimer_stats(&stats);
    out->callbacks = stats.callbacks; out->maxTaskLate = stats.max_late_ticks;
    /* Stop before target cleanup. A failed release retains lease/FAULT; do not
     * call target cleanup, retry, or free anything under a potentially live ISR. */
    if (hrestimer_exit() != kErrorOk || target_cleanup() != kErrorOk) {
        result = M7_TIMER_CLEANUP;
    } else out->clean = 1;
    if (!m7_timer_diag_snapshot(&out->after)) { result = M7_TIMER_STATE; out->clean = 0; }
    if (acquired && out->clean && ((out->after.cntp & 1U) ||
        (out->after.enabled | out->after.pending | out->after.active) & (1U << 30) ||
        ((out->before.enabled ^ out->after.enabled) & (1U << 27)) ||
        ((out->before.cntv ^ out->after.cntv) & 3U) ||
        out->before.priority27 != out->after.priority27 ||
        out->before.priority30 != out->after.priority30 ||
        out->before.typer != out->after.typer || out->before.cpuControl != out->after.cpuControl ||
        ((out->before.group ^ out->after.group) & (1U << 30)) ||
        ((out->before.config ^ out->after.config) & (1U << 29)))) {
        result = M7_TIMER_STATE; out->clean = 0;
    }
    if (!result && (out->after.interrupts != out->callbacks || out->samples != 24U))
        result = M7_TIMER_COUNTS;
    if (!result && out->after.ticks <= out->before.ticks) result = M7_TIMER_TICK;
    out->result = result; return result;
}
