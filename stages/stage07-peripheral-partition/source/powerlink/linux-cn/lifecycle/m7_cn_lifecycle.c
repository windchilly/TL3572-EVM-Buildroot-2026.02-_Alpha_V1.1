/* One owner, one create, one stop attempt. All callback sources must join before
 * any stack resource release. Partial init is terminal: quiet is not releasable.
 * The frontend must separately gate authorization, process/interface ownership,
 * signals and shared IPC. This library must not be used as a runnable CN yet. */
#include <common/m7_cn_lifecycle.h>
#include <common/m7_cn_edrv.h>
#include <kernel/edrv.h>
#include <errno.h>
#include <time.h>
#define LOAD(x) __atomic_load_n(&(x), __ATOMIC_ACQUIRE)
#define STORE(x,v) __atomic_store_n(&(x), (v), __ATOMIC_RELEASE)
static struct {
    M7CnLifecycleStats stats;
    pthread_t owner, threads[M7_CN_THREADS];
    unsigned claim, stop, attempted_slots;
} life;
static int owner(void) { return LOAD(life.stats.begun) && pthread_equal(life.owner,pthread_self()); }
tOplkError m7_cn_fail(tOplkError error)
{
    tOplkError clear=kErrorOk;
    if (error!=kErrorOk)
        __atomic_compare_exchange_n(&life.stats.first_error,&clear,error,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
    return LOAD(life.stats.first_error);
}
tOplkError m7_cn_lifecycle_begin(void)
{
    M7CnEdrvStats transport;unsigned clear=0;
    m7_cn_edrv_stats(&transport);
    if (!transport.armed || transport.attempted ||
        !__atomic_compare_exchange_n(&life.claim,&clear,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE))
        return kErrorInvalidOperation;
    life.owner=pthread_self();STORE(life.stats.begun,1);
    return kErrorOk;
}
tOplkError m7_cn_create_begin(void)
{
    if (!owner() || life.stats.create_attempted || m7_cn_stopping() || life.stats.first_error)
        return kErrorInvalidOperation;
    life.stats.create_attempted=1;
    return kErrorOk;
}
tOplkError m7_cn_init_result(tOplkError error)
{
    M7CnEdrvStats transport;
    if (!owner() || !life.stats.create_attempted) return kErrorInvalidOperation;
    if (error!=kErrorOk) return m7_cn_fail(error);
    if (life.stats.first_error || m7_cn_stopping()) return kErrorInvalidOperation;
    m7_cn_edrv_stats(&transport);
    if (life.stats.created!=((1U<<M7_CN_THREADS)-1) || !transport.armed || !transport.attempted ||
        !transport.active || transport.stop_attempted || transport.closed || transport.fault)
        return m7_cn_fail(kErrorInvalidOperation);
    life.stats.initialized=1;return kErrorOk;
}
int m7_cn_thread_create(enum M7CnThread slot,pthread_t* thread,void* (*entry)(void*),void* argument)
{
    unsigned bit;int result;
    if (!owner() || !life.stats.create_attempted || slot<0 || slot>=M7_CN_THREADS ||
        !thread || !entry || m7_cn_stopping()) return EPERM;
    bit=1U<<slot;
    if (life.attempted_slots&bit) return EPERM;
    life.attempted_slots|=bit;
    result=pthread_create(thread,NULL,entry,argument);
    if (result) { m7_cn_fail(kErrorNoResource);return result; }
    life.threads[slot]=*thread;life.stats.created|=bit;return 0;
}
int m7_cn_stopping(void) { return LOAD(life.stop)!=0; }
tOplkError m7_cn_quiesce(void)
{
    struct timespec deadline;M7CnEdrvStats transport;
    unsigned slot;int failed=0;
    if (!owner()) return kErrorInvalidOperation;
    if (life.stats.quiet) return life.stats.first_error;
    if (life.stats.stop_attempted) return m7_cn_fail(kErrorInvalidOperation);
    life.stats.stop_attempted=1;STORE(life.stop,1);
    /* Stop all producers first. EDRV also excludes in-flight synchronous TX. */
    m7_cn_edrv_stats(&transport);
    if (transport.attempted && edrv_exit()!=kErrorOk) failed=1;
    /* One shared 1s deadline for the four stack workers, in addition to EDRV's
     * own <=1s cooperative join budget. No cancel, kill, detach or second join. */
    if (clock_gettime(CLOCK_MONOTONIC,&deadline)) return m7_cn_fail(kErrorInvalidOperation);
    deadline.tv_sec++;
    for (slot=0;slot<M7_CN_THREADS;slot++) {
        unsigned bit=1U<<slot;
        if (!(life.stats.created&bit)) continue;
        if (pthread_clockjoin_np(life.threads[slot],NULL,CLOCK_MONOTONIC,&deadline)) failed=1;
        else life.stats.joined|=bit;
    }
    m7_cn_edrv_stats(&transport);
    if (transport.attempted && (!transport.joined || !transport.closed || transport.inflight)) failed=1;
    if (failed || life.stats.joined!=life.stats.created) return m7_cn_fail(kErrorInvalidOperation);
    life.stats.quiet=1;
    if (transport.fault) m7_cn_fail(kErrorInvalidOperation);
    return life.stats.first_error;
}
tOplkError m7_cn_release_begin(void)
{
    tOplkError result=m7_cn_quiesce();
    if (result!=kErrorOk) return result;
    if (!life.stats.initialized || life.stats.release_started) return m7_cn_fail(kErrorInvalidOperation);
    life.stats.release_started=1;return kErrorOk;
}
int m7_cn_can_release(void)
{
    return owner() && life.stats.quiet && life.stats.initialized && life.stats.release_started &&
        !life.stats.released && !life.stats.first_error;
}
tOplkError m7_cn_kernel_release_begin(void)
{
    if (!m7_cn_can_release() || life.stats.kernel_release_started) return m7_cn_fail(kErrorInvalidOperation);
    life.stats.kernel_release_started=1;return kErrorOk;
}
tOplkError m7_cn_release_finish(void)
{
    if (!m7_cn_can_release() || !life.stats.kernel_release_started) return m7_cn_fail(kErrorInvalidOperation);
    life.stats.released=1;return kErrorOk;
}
int m7_cn_released(void) { return owner() && life.stats.released && !life.stats.first_error; }
tOplkError m7_cn_environment_exit_begin(void)
{
    if (!m7_cn_released() || life.stats.environment_exit_attempted) return kErrorInvalidOperation;
    life.stats.environment_exit_attempted=1;return kErrorOk;
}
void m7_cn_lifecycle_stats(M7CnLifecycleStats* stats)
{
    /* Snapshot is for the owner, after joins; not a concurrent telemetry API. */
    if (stats && owner()) *stats=life.stats;
}
