/* Native tests of the REAL target/timer port with mocked RTOS/register boundary.
 * This cannot prove EL2 permissions, cache instructions or physical IRQ timing. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <common/target.h>
#include <kernel/hrestimer.h>
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
#include "m7_plk_cache.h"
static uint32_t task = 1, frequency = 24000000U;
static int isr, irqMasked, timerArmed, leased, failAcquire, failRelease, failSem;
static uint64_t now, deadline, milliseconds;
static unsigned calls, action, cacheCalls, sleeps;
static uint32_t arguments[16];
static tTimerHdl first, second;
static int semaphores[16];
int m7_plk_task_id(uint32_t* id) { *id = task; return 1; }
int m7_plk_in_interrupt(void) { return isr; }
int m7_plk_irq_enabled(void) { return !irqMasked; }
uintptr_t m7_plk_irq_save(void) { int old = irqMasked; irqMasked = 1; return (uintptr_t)old; }
void m7_plk_irq_restore(uintptr_t state) { irqMasked = (int)state; }
uint64_t m7_plk_milliseconds(void) { return milliseconds; }
int m7_plk_sleep(uint32_t ms) { if (irqMasked || isr) return 0; sleeps += ms; return 1; }
int m7_plk_sem_create(uint16_t* handle)
{
    unsigned i;
    if (failSem) return 0;
    for (i = 0; i < 16; ++i) if (!semaphores[i]) { semaphores[i] = 1; *handle = (uint16_t)i; return 1; }
    return 0;
}
int m7_plk_sem_take(uint16_t handle)
{ if (failSem || handle >= 16 || semaphores[handle] != 1) return 0; semaphores[handle] = 2; return 1; }
int m7_plk_sem_give(uint16_t handle)
{ if (failSem || handle >= 16 || semaphores[handle] != 2) return 0; semaphores[handle] = 1; return 1; }
int m7_plk_sem_delete(uint16_t handle)
{ if (failSem || handle >= 16 || semaphores[handle] != 1) return 0; semaphores[handle] = 0; return 1; }
int m7_plk_cache(const void* address, size_t length, int invalidate)
{ assert(invalidate == 0 || invalidate == 1); ++cacheCalls; return m7_plk_cache_range((uintptr_t)address, length) != 0; }
int m7_plk_timer_acquire(uint32_t* freq)
{ if (failAcquire || leased) return 0; *freq = frequency; leased = 1; return 1; }
int m7_plk_timer_release(void)
{ if (failRelease) return 0; leased = 0; return 1; }
uint64_t m7_plk_timer_now(void) { return now; }
void m7_plk_timer_arm(uint64_t value) { assert(leased); deadline = value; timerArmed = 1; }
void m7_plk_timer_mask(void) { timerArmed = 0; }
static tOplkError callback(const tTimerEventArg* event)
{
    assert(!isr && !irqMasked); assert(calls < 16);
    arguments[calls++] = event->argument.value;
    if (action == 1) {
        assert(m7_hrestimer_process() == kErrorInvalidOperation);
        assert(hrestimer_exit() == kErrorInvalidOperation);
        assert(hrestimer_deleteTimer(&second) == kErrorOk);
        assert(hrestimer_modifyTimer(&first, 1000, callback, 3, FALSE) == kErrorOk);
    }
    if (action == 3 && event->argument.value == 1) now += 50;
    return action == 2 ? kErrorNoResource : kErrorOk;
}
static void start(void) { assert(target_init() == kErrorOk); assert(hrestimer_init() == kErrorOk); }
static void finish(void) { assert(hrestimer_exit() == kErrorOk); assert(target_cleanup() == kErrorOk); }
static void conversion(void)
{
    uint64_t ticks;
    assert(m7_hrestimer_ticks(1, 24000000, &ticks) && ticks == 1);
    assert(m7_hrestimer_ticks(42, 24000000, &ticks) && ticks == 2);
    assert(m7_hrestimer_ticks(1000, 24000000, &ticks) && ticks == 24);
    assert(m7_hrestimer_ticks(1000000001ULL, 24000000, &ticks) && ticks == 24000001);
    assert(m7_hrestimer_ticks(UINT64_MAX, 1, &ticks) && ticks == 18446744074ULL);
    assert(!m7_hrestimer_ticks(UINT64_MAX, 1000000000, &ticks));
    assert(!m7_hrestimer_ticks(0, 24000000, &ticks));
    assert(!m7_hrestimer_ticks(1, 0, &ticks));
    assert(!m7_hrestimer_ticks(1, 1000000001, &ticks));
    assert(!m7_hrestimer_ticks(1, 24000000, NULL));
}
static void lifecycle(void)
{
    assert(target_init() == kErrorOk); assert(target_init() == kErrorInvalidOperation);
    failAcquire = 1; assert(hrestimer_init() == kErrorNoResource); failAcquire = 0;
    assert(!m7_hrestimer_active()); assert(hrestimer_init() == kErrorOk);
    assert(hrestimer_init() == kErrorNoResource); assert(target_cleanup() == kErrorInvalidOperation);
    failRelease = 1; assert(hrestimer_exit() == kErrorNoResource);
    assert(m7_hrestimer_active() && m7_plk_faulted() && !timerArmed);
    failRelease = 0; finish();
    start(); finish();
    assert(target_init() == kErrorOk); frequency = 0;
    assert(hrestimer_init() == kErrorNoResource); assert(!leased); assert(m7_plk_faulted());
    assert(target_cleanup() == kErrorOk);
}
static void expiry(void)
{
    M7PlkTimerStats stat;
    start(); now = UINT64_MAX - 10;
    assert(hrestimer_modifyTimer(&first, 1000, callback, 1, FALSE) == kErrorOk);
    assert(deadline == 13); now = 12; assert(m7_hrestimer_process() == kErrorOk && !calls);
    now = 13; isr = 1; m7_hrestimer_interrupt(); assert(!calls && !timerArmed);
    assert(m7_hrestimer_process() == kErrorInvalidOperation); isr = 0;
    assert(m7_hrestimer_process() == kErrorOk && calls == 1 && arguments[0] == 1);
    assert(m7_hrestimer_process() == kErrorOk && calls == 1);
    m7_hrestimer_stats(&stat); assert(stat.interrupts == 1 && stat.callbacks == 1);
    assert(hrestimer_deleteTimer(&first) == kErrorOk); finish();
    start(); now = 0;
    assert(hrestimer_modifyTimer(&first, 2000, callback, 1, FALSE) == kErrorOk);
    assert(hrestimer_modifyTimer(&second, 1000, callback, 2, FALSE) == kErrorOk);
    now = 48; assert(m7_hrestimer_process() == kErrorOk);
    assert(calls == 3 && arguments[1] == 2 && arguments[2] == 1); finish();
}
static void periodic(void)
{
    M7PlkTimerStats stat;
    start(); assert(hrestimer_modifyTimer(&first, 1000, callback, 1, TRUE) == kErrorOk);
    now = 24 * 6 + 5; assert(m7_hrestimer_process() == kErrorOk);
    assert(calls == 1 && deadline == 24 * 7);
    m7_hrestimer_stats(&stat); assert(stat.skipped_periods == 5 && stat.max_late_ticks == 125);
    assert(m7_hrestimer_process() == kErrorOk && calls == 1);
    now = deadline; assert(m7_hrestimer_process() == kErrorOk && calls == 2);
    assert(deadline == 24 * 8); finish();
}
static void callback_test(void)
{
    start(); action = 1;
    assert(hrestimer_modifyTimer(&first, 1000, callback, 1, FALSE) == kErrorOk);
    assert(hrestimer_modifyTimer(&second, 1000, callback, 2, FALSE) == kErrorOk);
    now = 24; assert(m7_hrestimer_process() == kErrorOk && calls == 1 && !second);
    action = 0; now = 48;
    assert(m7_hrestimer_process() == kErrorOk && calls == 2 && arguments[1] == 3); finish();
}
static void stale(void)
{
    tTimerHdl old, third = 0;
    start(); assert(hrestimer_modifyTimer(&first, 1000, callback, 0, FALSE) == kErrorOk);
    old = first; assert(hrestimer_modifyTimer(&first, 2000, callback, 0, FALSE) == kErrorOk);
    assert(first != old && hrestimer_deleteTimer(&old) == kErrorTimerInvalidHandle);
    assert(hrestimer_modifyTimer(&old, 1000, callback, 0, FALSE) == kErrorTimerInvalidHandle);
    assert(hrestimer_modifyTimer(&second, 1000, callback, 0, FALSE) == kErrorOk);
    assert(hrestimer_modifyTimer(&third, 1000, callback, 0, FALSE) == kErrorTimerNoTimerCreated);
    assert(hrestimer_modifyTimer(&third, 0, callback, 0, FALSE) == kErrorInvalidInstanceParam);
    assert(hrestimer_modifyTimer(NULL, 1, callback, 0, FALSE) == kErrorInvalidInstanceParam);
    assert(hrestimer_deleteTimer(NULL) == kErrorTimerInvalidHandle);
    old = first; finish(); start(); first = 0;
    assert(hrestimer_modifyTimer(&first, 1000, callback, 0, FALSE) == kErrorOk);
    assert(old != first && hrestimer_deleteTimer(&old) == kErrorTimerInvalidHandle); finish();
}
static void slow_callback(void)
{
    M7PlkTimerStats stat;
    start(); action = 3;
    assert(hrestimer_modifyTimer(&first, 1000, callback, 1, FALSE) == kErrorOk);
    assert(hrestimer_modifyTimer(&second, 1000, callback, 2, TRUE) == kErrorOk);
    now = 24; assert(m7_hrestimer_process() == kErrorOk && calls == 2 && deadline == 96);
    m7_hrestimer_stats(&stat); assert(stat.max_late_ticks == 50 && stat.skipped_periods == 2);
    finish();
}
static void fault(void)
{
    start(); action = 2;
    assert(hrestimer_modifyTimer(&first, 1000, callback, 0, TRUE) == kErrorOk);
    now = 24; assert(m7_hrestimer_process() == kErrorNoResource);
    assert(m7_plk_faulted() && !timerArmed); finish();
    start(); hrestimer_controlExtSyncIrq(FALSE); assert(!m7_plk_faulted());
    hrestimer_controlExtSyncIrq(TRUE); assert(m7_plk_faulted() && !timerArmed); finish();
}
static void mutex_test(void)
{
    OPLK_MUTEX_T handles[9] = {0};
    OPLK_MUTEX_T old;
    unsigned i;
    assert(target_init() == kErrorOk);
    failSem = 1; assert(target_createMutex("x", &handles[0]) == kErrorNoResource); failSem = 0;
    for (i = 0; i < 8; ++i) assert(target_createMutex("x", &handles[i]) == kErrorOk);
    assert(target_createMutex("x", &handles[8]) == kErrorNoResource);
    assert(target_lockMutex(handles[0]) == kErrorOk);
    assert(target_lockMutex(handles[0]) == kErrorInvalidOperation);
    target_destroyMutex(handles[0]); assert(m7_plk_faulted());
    assert(target_cleanup() == kErrorInvalidOperation);
    target_unlockMutex(handles[0]);
    old = handles[0];
    for (i = 0; i < 8; ++i) target_destroyMutex(handles[i]);
    assert(target_cleanup() == kErrorOk); assert(target_init() == kErrorOk);
    handles[0] = 0; assert(target_createMutex("x", &handles[0]) == kErrorOk);
    assert(old != handles[0] && target_lockMutex(old) == kErrorInvalidOperation);
    target_unlockMutex(handles[0]); assert(m7_plk_faulted());
    target_destroyMutex(handles[0]); assert(target_cleanup() == kErrorOk);
}
static void critical(void)
{
    assert(target_init() == kErrorOk); irqMasked = 1;
    target_enableGlobalInterrupt(FALSE); target_enableGlobalInterrupt(FALSE);
    target_enableGlobalInterrupt(TRUE); assert(irqMasked);
    target_enableGlobalInterrupt(TRUE); assert(irqMasked); /* preserve masked entry */
    irqMasked = 0;
    target_enableGlobalInterrupt(FALSE); target_enableGlobalInterrupt(FALSE);
    target_enableGlobalInterrupt(TRUE); assert(irqMasked);
    target_enableGlobalInterrupt(TRUE); assert(!irqMasked);
    target_msleep(7); assert(sleeps == 7);
    milliseconds = UINT32_MAX + 5ULL; assert(target_getTickCount() == 4);
    target_enableGlobalInterrupt(TRUE); assert(m7_plk_faulted());
    assert(target_cleanup() == kErrorOk); assert(target_init() == kErrorOk);
    target_enableGlobalInterrupt(FALSE); target_msleep(1); assert(m7_plk_faulted());
    assert(target_cleanup() == kErrorInvalidOperation);
    target_enableGlobalInterrupt(TRUE); assert(target_cleanup() == kErrorOk);
}
static void cache_test(void)
{
    assert(m7_plk_cache_range(0x7c200000, 0x800000) == 1);
    assert(m7_plk_cache_range(0x7ca10000, 0x10000) == 2);
    assert(!m7_plk_cache_range(0x7ca00000, 1));
    assert(!m7_plk_cache_range(0x7c1fffff, 1));
    assert(!m7_plk_cache_range(0x7c9fffff, 2));
    assert(!m7_plk_cache_range(0x7ca1ffff, 2));
    assert(!m7_plk_cache_range(UINTPTR_MAX - 4, 8));
    assert(!m7_plk_cache_range(0x7b200000, 64));
    assert(target_init() == kErrorOk);
    m7_powerlink_cache_flush(NULL, 0); assert(!cacheCalls && !m7_plk_faulted());
    m7_powerlink_cache_flush((void*)0x7c200003, 45);
    m7_powerlink_cache_invalidate((void*)0x7ca10000, 64);
    assert(cacheCalls == 2 && !m7_plk_faulted());
    m7_powerlink_cache_flush((void*)0x7b200000, 64); assert(m7_plk_faulted());
    assert(target_cleanup() == kErrorOk);
}
static void owner(void)
{
    OPLK_MUTEX_T handle = NULL;
    start(); task = 2;
    assert(!m7_plk_owner()); assert(hrestimer_modifyTimer(&first, 1, callback, 0, FALSE) == kErrorInvalidOperation);
    assert(target_createMutex("x", &handle) == kErrorInvalidOperation);
    assert(target_cleanup() == kErrorInvalidOperation); task = 1; isr = 1;
    assert(!m7_plk_owner()); assert(hrestimer_exit() == kErrorInvalidOperation);
    isr = 0; irqMasked = 1;
    assert(m7_hrestimer_process() == kErrorInvalidOperation);
    assert(target_createMutex("x", &handle) == kErrorInvalidOperation);
    irqMasked = 0; finish();
}
int main(int argc, char** argv)
{
    assert(argc == 2);
    if (!strcmp(argv[1], "conversion")) conversion();
    else if (!strcmp(argv[1], "lifecycle")) lifecycle();
    else if (!strcmp(argv[1], "expiry")) expiry();
    else if (!strcmp(argv[1], "periodic")) periodic();
    else if (!strcmp(argv[1], "callback")) callback_test();
    else if (!strcmp(argv[1], "slow_callback")) slow_callback();
    else if (!strcmp(argv[1], "stale")) stale();
    else if (!strcmp(argv[1], "fault")) fault();
    else if (!strcmp(argv[1], "mutex")) mutex_test();
    else if (!strcmp(argv[1], "critical")) critical();
    else if (!strcmp(argv[1], "cache")) cache_test();
    else if (!strcmp(argv[1], "owner")) owner();
    else assert(0);
    printf("P2 native %s PASS (mock hardware, not IRQ/latency acceptance)\n", argv[1]);
    return 0;
}
