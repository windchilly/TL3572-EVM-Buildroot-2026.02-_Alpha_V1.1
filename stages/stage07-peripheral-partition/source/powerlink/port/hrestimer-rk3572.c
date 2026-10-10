/* Two logical timers multiplexed onto UP2 CNTP/PPI30. IRQ only masks/latches;
 * the same task that runs EDRV dispatches callbacks. No TaskDelay per cycle.
 * Does not guarantee cycle deadlines until owner-loop latency is measured. */
#include <kernel/hrestimer.h>
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
#define TIMER_COUNT 2U
typedef struct {
    tTimerEventArg event;
    tTimerkCallback callback;
    uint64_t deadline, period;
    int armed;
} Timer;
static Timer timers[TIMER_COUNT];
static uintptr_t sequence;
static M7PlkTimerStats stats;
static volatile uint64_t interrupts;

int m7_hrestimer_ticks(uint64_t ns, uint32_t frequency, uint64_t* ticks)
{
    uint64_t seconds = ns / 1000000000U, remainder = ns % 1000000000U, value, tail;
    if (!ticks || !ns || !frequency || frequency > 1000000000U ||
        seconds > (uint64_t)INT64_MAX / frequency) return 0;
    value = seconds * frequency;
    tail = (remainder * frequency + 999999999U) / 1000000000U;
    if (value > (uint64_t)INT64_MAX - tail) return 0;
    *ticks = value + tail;
    return *ticks != 0;
}
int m7_hrestimer_active(void) { return stats.leased; }
void m7_hrestimer_stats(M7PlkTimerStats* out)
{
    uintptr_t state;
    if (!out || !m7_plk_owner()) return;
    state = m7_plk_irq_save(); *out = stats; out->interrupts = interrupts;
    m7_plk_irq_restore(state);
}
void m7_hrestimer_interrupt(void)
{
    m7_plk_timer_mask();
    ++interrupts;
}
static Timer* findTimer(tTimerHdl handle)
{
    unsigned index = (unsigned)(handle & 3U);
    if (!index || index > TIMER_COUNT || timers[index-1].event.timerHdl.handle != handle)
        return NULL;
    return &timers[index-1];
}
/* signed modular differences are valid for every admitted <=INT64_MAX delta. */
static void rearm(void)
{
    unsigned i;
    Timer* first = NULL;
    uintptr_t state = m7_plk_irq_save();
    m7_plk_timer_mask();
    if (!m7_plk_faulted()) {
        for (i = 0; i < TIMER_COUNT; ++i)
            if (timers[i].armed && (!first ||
                (int64_t)(timers[i].deadline - first->deadline) < 0)) first = &timers[i];
        if (first) m7_plk_timer_arm(first->deadline);
    }
    m7_plk_irq_restore(state);
}
tOplkError hrestimer_init(void)
{
    uint32_t frequency;
    if (!m7_plk_ready() || stats.leased || !m7_plk_timer_acquire(&frequency))
        return kErrorNoResource;
    stats = (M7PlkTimerStats){0}; stats.leased = 1; stats.frequency = frequency;
    interrupts = 0; memset(timers, 0, sizeof(timers));
    if (!frequency || frequency > 1000000000U) {
        m7_plk_fault(); (void)hrestimer_exit(); return kErrorNoResource;
    }
    return kErrorOk;
}
tOplkError hrestimer_exit(void)
{
    if (!m7_plk_owner() || stats.dispatching) return kErrorInvalidOperation;
    if (!stats.leased) return kErrorOk;
    m7_plk_timer_mask();
    if (!m7_plk_timer_release()) { m7_plk_fault(); return kErrorNoResource; }
    memset(timers, 0, sizeof(timers)); stats.leased = 0;
    return kErrorOk;
}
tOplkError hrestimer_modifyTimer(tTimerHdl* handle, ULONGLONG ns,
    tTimerkCallback callback, ULONG argument, BOOL continuous)
{
    Timer* timer = NULL;
    uint64_t ticks;
    unsigned i;
    if (!m7_plk_ready() || !stats.leased) return kErrorInvalidOperation;
    if (!handle || !callback || !m7_hrestimer_ticks(ns, stats.frequency, &ticks) ||
        argument > UINT32_MAX) return kErrorInvalidInstanceParam;
    if (*handle) {
        timer = findTimer(*handle);
        if (!timer) return kErrorTimerInvalidHandle;
    } else {
        for (i = 0; i < TIMER_COUNT; ++i)
            if (!timers[i].event.timerHdl.handle) { timer = &timers[i]; break; }
        if (!timer) return kErrorTimerNoTimerCreated;
    }
    if (sequence >= (UINTPTR_MAX >> 2)) return kErrorNoResource;
    timer->event.timerHdl.handle = (++sequence << 2) | ((unsigned)(timer - timers) + 1U);
    timer->event.argument.value = (UINT32)argument;
    timer->callback = callback; timer->deadline = m7_plk_timer_now() + ticks;
    timer->period = continuous ? ticks : 0; timer->armed = 1;
    *handle = timer->event.timerHdl.handle; rearm();
    return kErrorOk;
}
tOplkError hrestimer_deleteTimer(tTimerHdl* handle)
{
    Timer* timer;
    if (!m7_plk_owner() || !stats.leased) return kErrorInvalidOperation;
    if (!handle) return kErrorTimerInvalidHandle;
    if (!*handle) return kErrorOk;
    timer = findTimer(*handle);
    if (!timer) return kErrorTimerInvalidHandle;
    memset(timer, 0, sizeof(*timer)); *handle = 0; rearm();
    return kErrorOk;
}
void hrestimer_controlExtSyncIrq(BOOL enable)
{
    /* No external sync pin wired in this port. Reject activation, not fake OK. */
    if (enable) { m7_plk_fault(); if (stats.leased) m7_plk_timer_mask(); }
}
tOplkError m7_hrestimer_process(void)
{
    tTimerHdl due[TIMER_COUNT] = {0};
    unsigned order[TIMER_COUNT] = {0, 1};
    uint64_t now;
    unsigned i;
    tOplkError result = kErrorOk;
    if (!m7_plk_ready() || !m7_plk_irq_enabled() || !stats.leased || stats.dispatching)
        return kErrorInvalidOperation;
    stats.dispatching = 1; now = m7_plk_timer_now();
    /* Snapshot due generations so callback rearm cannot fire again in this pass. */
    for (i = 0; i < TIMER_COUNT; ++i)
        if (timers[i].armed && (int64_t)(now - timers[i].deadline) >= 0)
            due[i] = timers[i].event.timerHdl.handle;
    if (due[0] && due[1] && (int64_t)(timers[1].deadline - timers[0].deadline) < 0) {
        order[0] = 1; order[1] = 0;
    }
    for (i = 0; i < TIMER_COUNT && !m7_plk_faulted(); ++i) {
        unsigned index = order[i];
        Timer* timer = due[index] ? findTimer(due[index]) : NULL;
        tTimerEventArg event;
        tTimerkCallback callback;
        uint64_t late, skipped;
        if (!timer || !timer->armed) continue;
        /* Include time consumed by earlier callbacks in this pass. */
        now = m7_plk_timer_now();
        late = now - timer->deadline;
        if (late > stats.max_late_ticks) stats.max_late_ticks = late;
        event = timer->event; callback = timer->callback;
        if (timer->period) {
            skipped = late / timer->period;
            stats.skipped_periods += skipped;
            timer->deadline = now + (timer->period - late % timer->period);
        } else timer->armed = 0;
        ++stats.callbacks;
        result = callback(&event);
        if (result != kErrorOk) m7_plk_fault();
    }
    stats.dispatching = 0; rearm();
    if (m7_plk_faulted() && result == kErrorOk) result = kErrorInvalidOperation;
    return result;
}
