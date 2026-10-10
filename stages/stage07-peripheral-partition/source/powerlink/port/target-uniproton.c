/* Real UniProton target via the pinned UP2 platform hooks; no POSIX fallback.
 * Mutexes use count-1 RTOS semaphores, task-only/nonrecursive, no PI promise.
 * A single stack owner makes blocking contention a contract violation. */
#include <common/target.h>
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
#define MUTEX_COUNT 8U
typedef struct { uintptr_t token; uint16_t sem; int locked; } Mutex;
static Mutex mutexes[MUTEX_COUNT];
static uintptr_t sequence;
static uint32_t ownerTask, irqDepth;
static uintptr_t savedIrq;
static int initialized, faulted;

int m7_plk_owner(void)
{
    uint32_t current;
    return initialized && !m7_plk_in_interrupt() &&
        m7_plk_task_id(&current) && current == ownerTask;
}
int m7_plk_ready(void) { return m7_plk_owner() && !faulted; }
void m7_plk_fault(void)
{
    faulted = 1;
    if (m7_hrestimer_active()) m7_plk_timer_mask();
}
int m7_plk_faulted(void) { return faulted; }

tOplkError target_init(void)
{
    if (initialized || m7_plk_in_interrupt() || !m7_plk_task_id(&ownerTask))
        return kErrorInvalidOperation;
    initialized = 1; faulted = 0; irqDepth = 0;
    return kErrorOk;
}
tOplkError target_cleanup(void)
{
    unsigned i;
    if (!m7_plk_owner() || irqDepth || m7_hrestimer_active())
        return kErrorInvalidOperation;
    for (i = 0; i < MUTEX_COUNT; ++i)
        if (mutexes[i].token) return kErrorInvalidOperation;
    initialized = 0;
    return kErrorOk;
}
void target_enableGlobalInterrupt(BOOL enable)
{
    if (!m7_plk_owner()) { m7_plk_fault(); return; }
    if (!enable) {
        uintptr_t state = m7_plk_irq_save();
        if (!irqDepth) savedIrq = state;
        if (irqDepth == UINT32_MAX) { m7_plk_fault(); return; }
        ++irqDepth;
    } else {
        if (!irqDepth) { m7_plk_fault(); return; }
        if (!--irqDepth) m7_plk_irq_restore(savedIrq);
    }
}
UINT32 target_getTickCount(void) { return (UINT32)m7_plk_milliseconds(); }
void target_msleep(UINT32 ms)
{
    if (!m7_plk_ready() || irqDepth || !m7_plk_sleep(ms)) m7_plk_fault();
}
static Mutex* findMutex(OPLK_MUTEX_T handle)
{
    uintptr_t token = (uintptr_t)handle;
    unsigned index = (unsigned)(token & 15U);
    if (!index || index > MUTEX_COUNT || mutexes[index-1].token != token)
        return NULL;
    return &mutexes[index-1];
}
tOplkError target_createMutex(const char* name, OPLK_MUTEX_T* handle)
{
    unsigned i;
    (void)name;
    if (!m7_plk_ready() || irqDepth || !m7_plk_irq_enabled() || !handle || *handle)
        return kErrorInvalidOperation;
    for (i = 0; i < MUTEX_COUNT && mutexes[i].token; ++i) {}
    if (i == MUTEX_COUNT || sequence >= (UINTPTR_MAX >> 4)) return kErrorNoResource;
    if (!m7_plk_sem_create(&mutexes[i].sem)) return kErrorNoResource;
    mutexes[i].token = (++sequence << 4) | (i + 1U);
    mutexes[i].locked = 0; *handle = (OPLK_MUTEX_T)mutexes[i].token;
    return kErrorOk;
}
tOplkError target_lockMutex(OPLK_MUTEX_T handle)
{
    Mutex* mutex = findMutex(handle);
    if (!m7_plk_ready() || irqDepth || !m7_plk_irq_enabled() || !mutex || mutex->locked)
        return kErrorInvalidOperation;
    if (!m7_plk_sem_take(mutex->sem)) { m7_plk_fault(); return kErrorNoResource; }
    mutex->locked = 1;
    return kErrorOk;
}
void target_unlockMutex(OPLK_MUTEX_T handle)
{
    Mutex* mutex = findMutex(handle);
    if (!m7_plk_owner() || irqDepth || !m7_plk_irq_enabled() || !mutex || !mutex->locked ||
        !m7_plk_sem_give(mutex->sem)) { m7_plk_fault(); return; }
    mutex->locked = 0;
}
void target_destroyMutex(OPLK_MUTEX_T handle)
{
    Mutex* mutex = findMutex(handle);
    if (!m7_plk_owner() || irqDepth || !m7_plk_irq_enabled() || !mutex || mutex->locked ||
        !m7_plk_sem_delete(mutex->sem)) { m7_plk_fault(); return; }
    mutex->token = 0;
}
static void cache(const void* address, size_t length, int invalidate)
{
    if (!m7_plk_ready() || (length && !m7_plk_cache(address, length, invalidate)))
        m7_plk_fault();
}
void m7_powerlink_cache_flush(const void* address, size_t length) { cache(address, length, 0); }
void m7_powerlink_cache_invalidate(const void* address, size_t length) { cache(address, length, 1); }
