/* Actual four production worker loops + actual module init/exit, with private
 * fake IPC/POSIX timer boundaries. No named IPC, real timers or network IO. */
#include <common/m7_cn_lifecycle.h>
#include <common/m7_cn_edrv.h>
#include <kernel/hrestimer.h>
#include <kernel/eventkcal.h>
#include <kernel/eventkcalintf.h>
#include <user/timeru.h>
#include <user/eventucal.h>
#include <user/eventucalintf.h>
#include <user/eventu.h>
#include <assert.h>
#include <errno.h>
#include <fcntl.h>
#include <semaphore.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static sem_t user_sem,kernel_sem;
static M7CnEdrvStats transport={.armed=1};
static unsigned ready,entered,completed,freed,joins,timer_count,delivered[3],stop_count;
static unsigned sem_closes,queue_exits,timer_deletes;
static void* timer_pointer[3];
static int timer_signal[3];
static const char* scenario;
#define LOAD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define STORE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#define ADD(x,v) __atomic_add_fetch(&(x),(v),__ATOMIC_ACQ_REL)
static void blocked_callback(void)
{
    const struct timespec pause={0,1000000},tail={0,20000000};
    ADD(entered,1);
    while (!m7_cn_stopping()) nanosleep(&pause,NULL);
    nanosleep(&tail,NULL);assert(!LOAD(freed));ADD(completed,1);
}
static tOplkError hres_callback(const tTimerEventArg* argument) { assert(argument);blocked_callback();return kErrorOk; }
void __wrap_m7_cn_edrv_stats(M7CnEdrvStats* s) { *s=transport; }
tOplkError __wrap_edrv_exit(void)
{
    assert(++stop_count==1 && m7_cn_stopping());transport.closed=transport.joined=1;return kErrorOk;
}
sem_t* __wrap_sem_open(const char* name,int flags,...)
{
    (void)flags;
    if (!strcmp(name,"/semUserEvent")) return &user_sem;
    assert(!strcmp(name,"/semKernelEvent"));return &kernel_sem;
}
int __wrap_sem_unlink(const char* name)
{
    assert(!strcmp(name,"/semUserEvent") || !strcmp(name,"/semKernelEvent"));return 0;
}
int __wrap_sem_close(sem_t* semaphore)
{
    assert(semaphore==&user_sem || semaphore==&kernel_sem);
    assert(LOAD(completed)==4 && joins==4 && m7_cn_can_release());
    sem_closes++;
    if (!strcmp(scenario,"sem_close_failure") && sem_closes==1) return -1;
    ADD(freed,1);return 0;
}
int __wrap_timer_create(clockid_t clock,struct sigevent* event,timer_t* timer)
{
    assert(clock==CLOCK_MONOTONIC && timer_count<3);
    timer_pointer[timer_count]=event->sigev_value.sival_ptr;
    timer_signal[timer_count]=event->sigev_signo;
    *timer=(timer_t)(uintptr_t)(++timer_count);return 0;
}
int __wrap_timer_settime(timer_t timer,int flags,const struct itimerspec* value,struct itimerspec* previous)
{
    (void)flags;assert((uintptr_t)timer>=1 && (uintptr_t)timer<=3 && value);
    if (previous) memset(previous,0,sizeof(*previous));
    return 0;
}
int __wrap_timer_delete(timer_t timer)
{
    assert((uintptr_t)timer>=1 && (uintptr_t)timer<=3);
    assert(LOAD(completed)==4 && joins==4 && m7_cn_can_release());
    timer_deletes++;
    if (!strcmp(scenario,"timer_delete_failure") && timer_deletes==1) return -1;
    ADD(freed,1);return 0;
}
int __wrap_sigtimedwait(const sigset_t* set,siginfo_t* info,const struct timespec* timeout)
{
    unsigned i;const struct timespec pause={0,1000000};
    assert(timeout->tv_sec==0 && timeout->tv_nsec==10000000);
    if (LOAD(ready)) {
        for (i=0;i<timer_count;i++) {
            unsigned clear=0;
            /* First hres timer is armed; second remains unused. */
            if (i==1 || !sigismember(set,timer_signal[i])) continue;
            if (__atomic_compare_exchange_n(&delivered[i],&clear,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
                memset(info,0,sizeof(*info));info->si_value.sival_ptr=timer_pointer[i];return timer_signal[i];
            }
        }
    }
    nanosleep(&pause,NULL);errno=EAGAIN;return -1;
}
int __real_pthread_clockjoin_np(pthread_t,void**,clockid_t,const struct timespec*);
int __wrap_pthread_clockjoin_np(pthread_t thread,void** result,clockid_t clock,const struct timespec* deadline)
{
    int ret=__real_pthread_clockjoin_np(thread,result,clock,deadline);
    assert(ret==0 && !LOAD(freed));joins++;return ret;
}
tOplkError __wrap_eventkcal_initQueueCircbuf(tEventQueue queue) { (void)queue;return kErrorOk; }
tOplkError __wrap_eventucal_initQueueCircbuf(tEventQueue queue) { (void)queue;return kErrorOk; }
tOplkError __wrap_eventkcal_exitQueueCircbuf(tEventQueue queue)
{ (void)queue;assert(LOAD(completed)==4 && joins==4);queue_exits++;ADD(freed,1);return kErrorOk; }
tOplkError __wrap_eventucal_exitQueueCircbuf(tEventQueue queue)
{
    (void)queue;assert(LOAD(completed)==4 && joins==4);queue_exits++;
    if (!strcmp(scenario,"queue_exit_failure") && queue_exits==1) return kErrorNoResource;
    ADD(freed,1);return kErrorOk;
}
tOplkError __wrap_eventkcal_setSignalingCircbuf(tEventQueue queue,void (*callback)(void))
{ (void)queue;(void)callback;return kErrorOk; }
tOplkError __wrap_eventucal_setSignalingCircbuf(tEventQueue queue,void (*callback)(void))
{ (void)queue;(void)callback;return kErrorOk; }
UINT __wrap_eventkcal_getEventCountCircbuf(tEventQueue queue) { (void)queue;return 1; }
UINT __wrap_eventucal_getEventCountCircbuf(tEventQueue queue) { (void)queue;return 1; }
tOplkError __wrap_eventkcal_processEventCircbuf(tEventQueue queue) { (void)queue;blocked_callback();return kErrorOk; }
tOplkError __wrap_eventucal_processEventCircbuf(tEventQueue queue) { (void)queue;blocked_callback();return kErrorOk; }
tOplkError __wrap_eventu_postEvent(const tEvent* event) { assert(event->eventType==kEventTypeTimer);blocked_callback();return kErrorOk; }
int __wrap_socket(int domain,int type,int protocol) { (void)domain;(void)type;(void)protocol;assert(0);return -1; }
int main(int argc,char** argv)
{
    tTimerHdl hres=0,user=0;tTimerArg argument={0};unsigned waits=0;
    const struct timespec pause={0,1000000};M7CnLifecycleStats s={0};
    assert(argc==2);scenario=argv[1];
    assert(!sem_init(&user_sem,0,0) && !sem_init(&kernel_sem,0,0));
    assert(m7_cn_lifecycle_begin()==kErrorOk && m7_cn_create_begin()==kErrorOk);
    assert(eventkcal_init()==kErrorOk && hrestimer_init()==kErrorOk);
    assert(eventucal_init()==kErrorOk && timeru_init()==kErrorOk);
    assert(hrestimer_modifyTimer(&hres,1000000,hres_callback,0,FALSE)==kErrorOk);
    assert(timeru_setTimer(&user,1,&argument)==kErrorOk);
    transport.attempted=transport.active=1;assert(m7_cn_init_result(kErrorOk)==kErrorOk);
    STORE(ready,1);assert(!sem_post(&user_sem) && !sem_post(&kernel_sem));
    while (LOAD(entered)!=4 && waits++<2000) nanosleep(&pause,NULL);
    assert(LOAD(entered)==4 && !LOAD(freed));
    /* Exits cannot release even while all four callbacks are demonstrably live. */
    assert(eventucal_exit()==kErrorInvalidOperation && eventkcal_exit()==kErrorInvalidOperation);
    assert(hrestimer_exit()==kErrorInvalidOperation && timeru_exit()==kErrorInvalidOperation);
    assert(m7_cn_release_begin()==kErrorOk && LOAD(completed)==4 && joins==4 && !LOAD(freed));
    if (!strcmp(scenario,"timer_delete_failure")) {
        assert(hrestimer_exit()!=kErrorOk);assert(timer_deletes==1 && !LOAD(freed));
        assert(timeru_exit()==kErrorInvalidOperation && eventucal_exit()==kErrorInvalidOperation);
        assert(m7_cn_release_begin()!=kErrorOk);goto done;
    }
    if (!strcmp(scenario,"sem_close_failure")) {
        assert(eventucal_exit()!=kErrorOk);assert(sem_closes==1 && queue_exits==3);
        assert(eventkcal_exit()==kErrorInvalidOperation && timeru_exit()==kErrorInvalidOperation);
        assert(m7_cn_release_begin()!=kErrorOk);goto done;
    }
    if (!strcmp(scenario,"queue_exit_failure")) {
        assert(eventucal_exit()!=kErrorOk);assert(queue_exits==1 && !sem_closes && !LOAD(freed));
        assert(eventkcal_exit()==kErrorInvalidOperation && timeru_exit()==kErrorInvalidOperation);
        assert(m7_cn_release_begin()!=kErrorOk);goto done;
    }
    assert(m7_cn_kernel_release_begin()==kErrorOk);
    assert(eventucal_exit()==kErrorOk && eventkcal_exit()==kErrorOk);
    assert(hrestimer_exit()==kErrorOk && timeru_exit()==kErrorOk);
    assert(m7_cn_release_finish()==kErrorOk);
    assert(timer_deletes==3 && sem_closes==4 && queue_exits==6 && LOAD(freed)==13);
done:
    m7_cn_lifecycle_stats(&s);assert(s.quiet && s.joined==15 && s.created==15 && stop_count==1);
    assert(!sem_destroy(&user_sem) && !sem_destroy(&kernel_sem));
    printf("PASS workers %s entered=%u completed=%u joins=%u freed=%u fault=%u\n",scenario,LOAD(entered),LOAD(completed),joins,LOAD(freed),s.first_error);
    return 0;
}
