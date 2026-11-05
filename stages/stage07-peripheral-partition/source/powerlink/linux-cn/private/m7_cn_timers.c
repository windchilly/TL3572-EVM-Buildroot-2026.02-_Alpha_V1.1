/* Linux software-CN timers: fixed storage and generation handles, no POSIX
 * timer signals/heap pointers/fd ownership. Two tracked workers preserve P4c's
 * four-worker quiescence contract. CLOCK_MONOTONIC condvars wake on a changed
 * deadline, or at least every 10ms to observe global stop. Not hard realtime. */
#include <common/m7_cn_private.h>
#include <common/m7_cn_lifecycle.h>
#include <kernel/hrestimer.h>
#include <user/timeru.h>
#include <user/eventu.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdint.h>
#include <time.h>
#define LOAD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define STORE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#define NS_SECOND UINT64_C(1000000000)
#define USER_SLOTS 64U
typedef char handle_must_be_64_bit[(sizeof(tTimerHdl)==8)?1:-1];
typedef struct {
    tTimerHdl handle;
    UINT64 due,period;
    unsigned allocated,active,fired;
    tTimerArg user;
    tTimerkCallback callback;
    ULONG argument;
} Timer;
typedef struct {
    pthread_mutex_t mutex;
    pthread_cond_t wake;
    pthread_t thread;
    Timer timers[USER_SLOTS];
    unsigned count,highres,attempted,initialized,exit_attempted;
    UINT64 generation,callbacks,skipped;
    tOplkError fault;
} Timers;
static Timers high={.mutex=PTHREAD_MUTEX_INITIALIZER,.count=2,.highres=1};
static Timers user={.mutex=PTHREAD_MUTEX_INITIALIZER,.count=USER_SLOTS};
static tOplkError fault(Timers* timers,tOplkError error)
{
    tOplkError clear=kErrorOk;
    __atomic_compare_exchange_n(&timers->fault,&clear,error,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
    return error;
}
static int now_ns(Timers* timers,UINT64* result)
{
    struct timespec value;
    if (clock_gettime(CLOCK_MONOTONIC,&value) || value.tv_sec<0 || value.tv_nsec<0 || value.tv_nsec>=1000000000 ||
        (UINT64)value.tv_sec>(UINT64_MAX-(UINT64)value.tv_nsec)/NS_SECOND) {
        fault(timers,kErrorInvalidOperation);return 0;
    }
    *result=(UINT64)value.tv_sec*NS_SECOND+(UINT64)value.tv_nsec;return 1;
}
static Timer* find(Timers* timers,tTimerHdl handle)
{
    unsigned index=(unsigned)(handle&255U);
    if (!index || index>timers->count) return NULL;
    if (!timers->timers[index-1].allocated || timers->timers[index-1].handle!=handle) return NULL;
    return &timers->timers[index-1];
}
static tTimerHdl generation(Timers* timers,unsigned index)
{
    if (timers->generation>=(UINT64_MAX>>9)) { fault(timers,kErrorNoResource);return 0; }
    return (tTimerHdl)((++timers->generation<<8)|(index+1)|(timers->highres?(UINT64_C(1)<<63):0));
}
static tOplkError deliver(Timers* timers,const Timer* snapshot)
{
    tTimerEventArg argument;
    memset(&argument,0,sizeof(argument));argument.timerHdl.handle=snapshot->handle;
    if (timers->highres) {
        argument.argument.value=snapshot->argument;
        /* Upstream ignores this callback's return (it posts its own errors). */
        snapshot->callback(&argument);
    } else {
        tEvent event;
        memset(&event,0,sizeof(event));
        memcpy(&argument.argument,&snapshot->user.argument,sizeof(snapshot->user.argument));
        event.eventType=kEventTypeTimer;event.eventSink=snapshot->user.eventSink;
        event.eventArg.pEventArg=&argument;event.eventArgSize=sizeof(argument);
        return eventu_postEvent(&event); /* queue copies bytes, never a Timer*. */
    }
    return kErrorOk;
}
static void* worker(void* parameter)
{
    Timers* timers=parameter;
    while (!m7_cn_stopping() && !LOAD(timers->fault)) {
        UINT64 now,deadline;unsigned i;Timer snapshot,*due=NULL;int result;
        struct timespec timeout;
        pthread_mutex_lock(&timers->mutex);
        if (!now_ns(timers,&now) || now>UINT64_MAX-10000000U) {
            fault(timers,kErrorInvalidOperation);pthread_mutex_unlock(&timers->mutex);break;
        }
        deadline=now+10000000U;
        for (i=0;i<timers->count;i++) if (timers->timers[i].active) {
            Timer* candidate=&timers->timers[i];
            if (candidate->due<=now && (!due || candidate->due<due->due)) due=candidate;
            if (candidate->due<deadline) deadline=candidate->due;
        }
        if (due && !m7_cn_stopping()) {
            UINT64 skipped=0;
            snapshot=*due;due->fired=1;
            if (due->period) {
                skipped=(now-due->due)/due->period;
                if (skipped>=UINT64_MAX/due->period || due->due>UINT64_MAX-(skipped+1)*due->period) {
                    fault(timers,kErrorInvalidOperation);pthread_mutex_unlock(&timers->mutex);break;
                }
                due->due+=(skipped+1)*due->period;
            } else due->active=0;
            timers->callbacks++;timers->skipped+=skipped;
            pthread_mutex_unlock(&timers->mutex);
            /* No slot/heap dereference after unlock: concurrent delete/modify
             * cannot invalidate this snapshot. It cannot recall a callback
             * already committed here; the app must retain its own argument. */
            {
                tOplkError error=deliver(timers,&snapshot);
                if (error!=kErrorOk) fault(timers,error);
            }
            continue;
        }
        timeout.tv_sec=(time_t)(deadline/NS_SECOND);timeout.tv_nsec=(long)(deadline%NS_SECOND);
        result=pthread_cond_timedwait(&timers->wake,&timers->mutex,&timeout);
        if (result && result!=ETIMEDOUT) fault(timers,kErrorInvalidOperation);
        pthread_mutex_unlock(&timers->mutex);
    }
    return NULL;
}
static tOplkError init(Timers* timers,enum M7CnThread slot)
{
    pthread_condattr_t attr;
    if (timers->attempted) return kErrorInvalidOperation;
    timers->attempted=1;
    if (pthread_condattr_init(&attr)) return fault(timers,kErrorNoResource);
    if (pthread_condattr_setclock(&attr,CLOCK_MONOTONIC)) {
        pthread_condattr_destroy(&attr);return fault(timers,kErrorNoResource);
    }
    if (pthread_cond_init(&timers->wake,&attr)) {
        pthread_condattr_destroy(&attr);return fault(timers,kErrorNoResource);
    }
    if (pthread_condattr_destroy(&attr)) return fault(timers,kErrorNoResource);
    timers->initialized=1;
    if (m7_cn_thread_create(slot,&timers->thread,worker,timers)) return fault(timers,kErrorNoResource);
    return kErrorOk;
}
static tOplkError shutdown(Timers* timers)
{
    if (!m7_cn_can_release() || !timers->initialized || timers->exit_attempted) return kErrorInvalidOperation;
    timers->exit_attempted=1;
    if (LOAD(timers->fault)) return m7_cn_fail(LOAD(timers->fault));
    if (pthread_cond_destroy(&timers->wake)) return m7_cn_fail(fault(timers,kErrorInvalidOperation));
    pthread_mutex_lock(&timers->mutex);memset(timers->timers,0,sizeof(timers->timers));timers->initialized=0;
    pthread_mutex_unlock(&timers->mutex);return kErrorOk;
}
static tOplkError set(Timers* timers,tTimerHdl* handle,UINT64 delay,UINT64 period,
                      tTimerkCallback callback,ULONG argument,const tTimerArg* user_argument,int modify)
{
    UINT64 now;tTimerHdl new_handle;Timer* timer=NULL;unsigned i;tOplkError result=kErrorOk;
    if (!handle || (!timers->highres && !user_argument) || (timers->highres && !callback)) return kErrorTimerInvalidHandle;
    pthread_mutex_lock(&timers->mutex);
    if (!timers->initialized || timers->exit_attempted || m7_cn_stopping() || LOAD(timers->fault)) {
        result=kErrorInvalidOperation;goto done;
    }
    if (*handle) {
        if (!modify || !(timer=find(timers,*handle))) { result=kErrorTimerInvalidHandle;goto done; }
        i=(unsigned)(timer-timers->timers);
    } else {
        for (i=0;i<timers->count;i++) if (!timers->timers[i].allocated) { timer=&timers->timers[i];break; }
        if (!timer) { result=kErrorTimerNoTimerCreated;goto done; }
    }
    if (!now_ns(timers,&now) || delay>UINT64_MAX-now) { result=fault(timers,kErrorInvalidOperation);goto done; }
    new_handle=generation(timers,i);
    if (!new_handle) { result=kErrorTimerNoTimerCreated;goto done; }
    memset(timer,0,sizeof(*timer));timer->allocated=timer->active=1;timer->handle=new_handle;
    timer->due=now+delay;timer->period=period;timer->callback=callback;timer->argument=argument;
    if (user_argument) timer->user=*user_argument;
    *handle=new_handle;
    if (pthread_cond_signal(&timers->wake)) result=fault(timers,kErrorInvalidOperation);
done:
    pthread_mutex_unlock(&timers->mutex);return result;
}
static tOplkError erase(Timers* timers,tTimerHdl* handle)
{
    Timer* timer;tOplkError result=kErrorOk;
    if (!handle) return kErrorTimerInvalidHandle;
    if (!*handle) return kErrorOk;
    pthread_mutex_lock(&timers->mutex);
    timer=find(timers,*handle);
    if (!timer) result=kErrorTimerInvalidHandle;
    else { memset(timer,0,sizeof(*timer));*handle=0; }
    pthread_mutex_unlock(&timers->mutex);return result;
}
tOplkError hrestimer_init(void) { return init(&high,M7_CN_HRES); }
tOplkError timeru_init(void) { return init(&user,M7_CN_TIMERU); }
tOplkError hrestimer_exit(void) { return shutdown(&high); }
tOplkError timeru_exit(void) { return shutdown(&user); }
tOplkError timeru_process(void) { return kErrorOk; }
tOplkError hrestimer_modifyTimer(tTimerHdl* handle,ULONGLONG delay,tTimerkCallback cb,ULONG argument,BOOL repeat)
{
    UINT64 minimum=repeat?100000U:20000U;
    if (delay<minimum) delay=minimum;
    return set(&high,handle,delay,repeat?delay:0,cb,argument,NULL,1);
}
tOplkError hrestimer_deleteTimer(tTimerHdl* handle) { return erase(&high,handle); }
tOplkError timeru_setTimer(tTimerHdl* handle,ULONG ms,const tTimerArg* argument)
{
    if ((UINT64)ms>UINT64_MAX/1000000U) return kErrorTimerNoTimerCreated;
    return set(&user,handle,(UINT64)ms*1000000U,0,NULL,0,argument,0);
}
tOplkError timeru_modifyTimer(tTimerHdl* handle,ULONG ms,const tTimerArg* argument)
{
    if ((UINT64)ms>UINT64_MAX/1000000U) return kErrorTimerNoTimerCreated;
    return set(&user,handle,(UINT64)ms*1000000U,0,NULL,0,argument,1);
}
tOplkError timeru_deleteTimer(tTimerHdl* handle) { return erase(&user,handle); }
BOOL timeru_isActive(tTimerHdl handle)
{
    Timer* timer;BOOL active=FALSE;
    pthread_mutex_lock(&user.mutex);timer=find(&user,handle);if (timer) active=timer->active;
    pthread_mutex_unlock(&user.mutex);return active;
}
void hrestimer_controlExtSyncIrq(BOOL enable) { (void)enable; }
void hrestimer_setExtSyncIrqTime(tTimestamp time) { (void)time; }
tOplkError m7_cn_timers_fault(void)
{ tOplkError error=LOAD(high.fault);return error?error:LOAD(user.fault); }
BOOL m7_cn_timer_event_current(const tEvent* event)
{
    Timer* timer;BOOL current=FALSE;const tTimerEventArg* argument;
    if (event->eventType!=kEventTypeTimer) return TRUE;
    if (event->eventArgSize!=sizeof(tTimerEventArg) || !event->eventArg.pEventArg) return FALSE;
    argument=event->eventArg.pEventArg;
    pthread_mutex_lock(&user.mutex);timer=find(&user,argument->timerHdl.handle);
    if (timer && timer->fired && !timer->active) { current=TRUE;timer->fired=0; }
    pthread_mutex_unlock(&user.mutex);return current;
}
void m7_cn_timer_stats(int highres,M7CnTimerStats* stats)
{
    Timers* timers=highres?&high:&user;unsigned i;
    memset(stats,0,sizeof(*stats));pthread_mutex_lock(&timers->mutex);
    for (i=0;i<timers->count;i++) { stats->allocated+=timers->timers[i].allocated;stats->active+=timers->timers[i].active; }
    stats->callbacks=timers->callbacks;stats->skipped=timers->skipped;stats->fault=LOAD(timers->fault);
    pthread_mutex_unlock(&timers->mutex);
}
