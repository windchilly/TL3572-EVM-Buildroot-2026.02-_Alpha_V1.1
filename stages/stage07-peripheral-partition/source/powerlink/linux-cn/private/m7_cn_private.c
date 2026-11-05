/* No names, shm, unlink or process-global network state. The kernel CAL owns
 * two unnamed process-private semaphores; user CAL only attaches/detaches.
 * P4c's global join proof is required before destruction. No retry on failure. */
#include <common/m7_cn_private.h>
#include <common/m7_cn_lifecycle.h>
static struct { sem_t user,kernel; unsigned attempted,ready,user_attached,user_detached,exit_attempted; } events;
tOplkError m7_cn_event_sems_init(void)
{
    if (events.attempted) return kErrorInvalidOperation;
    events.attempted=1;
    if (sem_init(&events.user,0,0) || sem_init(&events.kernel,0,0)) return kErrorNoResource;
    events.ready=1;return kErrorOk;
}
tOplkError m7_cn_event_sems_attach(void)
{
    if (!events.ready || events.user_attached || m7_cn_stopping()) return kErrorInvalidOperation;
    events.user_attached=1;return kErrorOk;
}
sem_t* m7_cn_event_sem(int kernel)
{
    if (!events.ready) return NULL;
    return kernel?&events.kernel:&events.user;
}
tOplkError m7_cn_event_sems_detach(void)
{
    if (!m7_cn_can_release() || !events.user_attached || events.user_detached) return kErrorInvalidOperation;
    events.user_detached=1;return kErrorOk;
}
tOplkError m7_cn_event_sems_exit(void)
{
    if (!m7_cn_can_release() || !events.ready || !events.user_detached || events.exit_attempted)
        return kErrorInvalidOperation;
    events.exit_attempted=1;
    if (sem_destroy(&events.user) || sem_destroy(&events.kernel)) return m7_cn_fail(kErrorInvalidOperation);
    events.ready=0;return kErrorOk;
}
