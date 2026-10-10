/* Actual target/timer/probe, only register/RTOS boundary mocked. */
#define main RtosRegressionMain
#define m7_plk_timer_now oldMockTimerNow
#include "test_powerlink_rtos.c"
#undef m7_plk_timer_now
#undef main
#include "m7_timer_probe.h"
#include "m7_plk_gic.h"
static uint64_t diagIrqs, diagLate;
static int noIrq, duplicateIrq, badTick, badPriority, frozen, diagFail;
uint64_t m7_plk_timer_now(void)
{
    if (!frozen) now += 120; /* 5us per read */
    if (timerArmed && !irqMasked && !noIrq && now >= deadline + 48) {
        uint64_t late = now - deadline;
        if (late > diagLate) diagLate = late;
        isr = 1; ++diagIrqs; m7_hrestimer_interrupt();
        if (duplicateIrq) { ++diagIrqs; m7_hrestimer_interrupt(); }
        isr = 0;
    }
    return now;
}
int m7_timer_diag_reset(void) { diagIrqs = diagLate = 0; return !diagFail; }
int m7_timer_diag_snapshot(M7TimerHardware* out)
{
    *out = (M7TimerHardware){0}; out->counter = now; out->ticks = badTick ? 0 : now / 24000;
    out->affinity = 0x101; out->level = 4; out->frequency = frequency;
    out->cntp = timerArmed ? 1 : 2; out->cntv = 1; out->enabled = (1U << 27) | (leased ? 1U << 30 : 0);
    out->priority30 = badPriority && diagIrqs ? 0xa0 : 0x80; out->priority27 = 0x90;
    out->interrupts = diagIrqs; out->maxIrqLate = diagLate; return 1;
}
int main(int argc, char** argv)
{
    M7TimerProbeResult out;
    unsigned i;
    assert(argc == 2 && m7_timer_probe(NULL) == M7_TIMER_CONTEXT);
    if (!strcmp(argv[1], "normal")) {
        for (i = 0; i < 10; ++i) {
            assert(m7_timer_probe(&out) == M7_TIMER_OK && out.clean && out.samples == 24);
            assert(out.after.interrupts == 24 && out.callbacks == 24 && out.after.maxIrqLate >= 48);
            assert(out.after.ticks > out.before.ticks && !leased && !m7_plk_owner());
        }
    } else if (!strcmp(argv[1], "gic")) {
        assert(m7_plk_gic_usable(1U << 10, 0, 1, 0, 0, 0, 0)); /* RAZ view */
        assert(!m7_plk_gic_usable(1U << 10, 0, 0, 0, 0, 0, 0));
        assert(m7_plk_gic_usable(0, 0, 1, 0, 0, 0, 0)); /* SecurityExtn absent Group0 */
        assert(!m7_plk_gic_usable(0, 1U << 30, 1, 0, 0, 0, 0));
        assert(m7_plk_gic_usable(0, 1U << 30, 2, 0, 0, 0, 0));
        assert(!m7_plk_gic_usable(1U << 10, 0, 1, 1U << 30, 0, 0, 0));
        assert(!m7_plk_gic_usable(1U << 10, 0, 1, 0, 1U << 30, 0, 0));
        assert(!m7_plk_gic_usable(1U << 10, 0, 1, 0, 0, 1U << 30, 0));
        assert(!m7_plk_gic_usable(1U << 10, 0, 1, 0, 0, 0, 1U << 29));
    } else if (!strcmp(argv[1], "no_irq")) {
        noIrq = 1; assert(m7_timer_probe(&out) == M7_TIMER_NO_IRQ && out.clean && !out.callbacks);
    } else if (!strcmp(argv[1], "duplicate")) {
        duplicateIrq = 1; assert(m7_timer_probe(&out) == M7_TIMER_COUNTS && out.clean && !out.callbacks);
    } else if (!strcmp(argv[1], "release_failure")) {
        failRelease = 1; assert(m7_timer_probe(&out) == M7_TIMER_CLEANUP && !out.clean);
        assert(leased && m7_plk_owner() && m7_plk_faulted());
        assert(m7_timer_probe(&out) == M7_TIMER_CONTEXT); /* no automatic retry */
    } else if (!strcmp(argv[1], "acquire_failure")) {
        failAcquire = 1; assert(m7_timer_probe(&out) == M7_TIMER_ACQUIRE && out.clean && !leased);
    } else if (!strcmp(argv[1], "partial_acquire")) {
        frequency = 0; failRelease = 1;
        assert(m7_timer_probe(&out) == M7_TIMER_CLEANUP && !out.clean && leased);
        assert(m7_plk_owner() && m7_plk_faulted());
    } else if (!strcmp(argv[1], "tick")) {
        badTick = 1; assert(m7_timer_probe(&out) == M7_TIMER_TICK && out.clean);
    } else if (!strcmp(argv[1], "priority")) {
        badPriority = 1; assert(m7_timer_probe(&out) == M7_TIMER_STATE && !out.clean);
    } else if (!strcmp(argv[1], "frozen")) {
        frozen = 1; assert(m7_timer_probe(&out) == M7_TIMER_TIMEOUT && out.clean && !out.callbacks);
    } else if (!strcmp(argv[1], "context")) {
        isr = 1; assert(m7_timer_probe(&out) == M7_TIMER_CONTEXT && !out.clean); isr = 0;
        irqMasked = 1; assert(m7_timer_probe(&out) == M7_TIMER_CONTEXT); irqMasked = 0;
        assert(!target_init()); assert(m7_timer_probe(&out) == M7_TIMER_CONTEXT); assert(!target_cleanup());
    } else if (!strcmp(argv[1], "diag")) {
        diagFail = 1; assert(m7_timer_probe(&out) == M7_TIMER_CONTEXT && !m7_plk_owner());
    } else assert(0);
    puts("P3c actual target/timer/probe native PASS (mock IRQ, NOT physical IRQ proof)"); return 0;
}
