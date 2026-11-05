/* Link actual private queues/timers. Real threads/unnamed semaphores/condvars;
 * all named IPC, signals, POSIX timers and network socket entry points abort. */
#include <common/m7_cn_private.h>
#include <common/m7_cn_lifecycle.h>
#include <common/circbuffer.h>
#include <kernel/hrestimer.h>
#include <user/timeru.h>
#include <user/eventu.h>
#include <user/eventucalintf.h>
#include <kernel/eventkcalintf.h>
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <sched.h>
#include <spawn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/wait.h>
#include <time.h>
#define LOAD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define STORE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
static const char* scenario;
static unsigned stop,allow,created,records,entered,unblock,sem_inits,sem_destroys,cond_destroys,fail_alloc;
static tTimerEventArg captured[256];
static pthread_t threads[2];
static tOplkError lifecycle_fault;
static int is(const char* s) { return !strcmp(scenario,s); }
int __wrap_m7_cn_stopping(void) { return LOAD(stop); }
int __wrap_m7_cn_can_release(void) { return allow; }
tOplkError __wrap_m7_cn_fail(tOplkError error) { if (!lifecycle_fault) lifecycle_fault=error;return lifecycle_fault; }
int __wrap_m7_cn_thread_create(enum M7CnThread slot,pthread_t* thread,void* (*entry)(void*),void* argument)
{
    assert(slot==M7_CN_HRES || slot==M7_CN_TIMERU);assert(created<2);
    if (is("thread_failure")) return EAGAIN;
    if (pthread_create(thread,NULL,entry,argument)) return EAGAIN;
    threads[created++]=*thread;return 0;
}
static void record(const tTimerEventArg* argument)
{
    unsigned index=LOAD(records);if (index>=256) return;
    captured[index]=*argument;STORE(records,index+1);
}
tOplkError __wrap_eventu_postEvent(const tEvent* event)
{
    const struct timespec pause={0,1000000};
    assert(event->eventType==kEventTypeTimer && event->eventArgSize==sizeof(tTimerEventArg));
    if (is("inflight_delete")) { STORE(entered,1);while (!LOAD(unblock)) nanosleep(&pause,NULL); }
    if (is("post_failure")) return kErrorNoResource;
    record(event->eventArg.pEventArg);return kErrorOk;
}
static tOplkError callback(const tTimerEventArg* argument) { record(argument);return kErrorOk; }
int __real_sem_init(sem_t*,int,unsigned);
int __wrap_sem_init(sem_t* sem,int shared,unsigned initial)
{
    assert(shared==0);sem_inits++;
    if ((is("sem_init_first") && sem_inits==1) || (is("sem_init_second") && sem_inits==2)) return -1;
    return __real_sem_init(sem,shared,initial);
}
int __real_sem_destroy(sem_t*);
int __wrap_sem_destroy(sem_t* sem)
{
    sem_destroys++;
    if (is("sem_destroy_failure")) return -1;
    return __real_sem_destroy(sem);
}
int __real_pthread_condattr_setclock(pthread_condattr_t*,clockid_t);
int __wrap_pthread_condattr_setclock(pthread_condattr_t* attr,clockid_t clock)
{
    assert(clock==CLOCK_MONOTONIC);
    if (is("cond_clock_failure")) return EINVAL;
    return __real_pthread_condattr_setclock(attr,clock);
}
int __real_pthread_cond_destroy(pthread_cond_t*);
int __wrap_pthread_cond_destroy(pthread_cond_t* condition)
{
    cond_destroys++;
    if (is("cond_destroy_failure")) return EBUSY;
    return __real_pthread_cond_destroy(condition);
}
int __real_clock_gettime(clockid_t,struct timespec*);
int __wrap_clock_gettime(clockid_t clock,struct timespec* value)
{
    assert(clock==CLOCK_MONOTONIC);
    if (is("clock_failure")) return -1;
    return __real_clock_gettime(clock,value);
}
void* __real_calloc(size_t,size_t);
void* __wrap_calloc(size_t count,size_t size)
{
    if (fail_alloc) { fail_alloc=0;return NULL; }
    return __real_calloc(count,size);
}
int __wrap_socket(int a,int b,int c) { (void)a;(void)b;(void)c;assert(0);return -1; }
sem_t* __wrap_sem_open(const char* name,int flags,...) { (void)name;(void)flags;assert(0);return SEM_FAILED; }
int __wrap_sem_unlink(const char* name) { (void)name;assert(0);return -1; }
int __wrap_shm_open(const char* name,int flags,mode_t mode) { (void)name;(void)flags;(void)mode;assert(0);return -1; }
int __wrap_shm_unlink(const char* name) { (void)name;assert(0);return -1; }
int __wrap_timer_create(clockid_t clock,struct sigevent* ev,timer_t* timer)
{ (void)clock;(void)ev;(void)timer;assert(0);return -1; }
static void wait_for(unsigned* flag,unsigned count)
{
    const struct timespec pause={0,1000000};unsigned attempts=0;
    while (LOAD(*flag)<count && attempts++<1000) nanosleep(&pause,NULL);
    assert(LOAD(*flag)>=count);
}
static void join_workers(void)
{
    struct timespec end;unsigned i;STORE(stop,1);
    assert(!__real_clock_gettime(CLOCK_MONOTONIC,&end));end.tv_sec++;
    for (i=0;i<created;i++) assert(!pthread_clockjoin_np(threads[i],NULL,CLOCK_MONOTONIC,&end));
    allow=1;
}
static BOOL current(unsigned index)
{
    tEvent event={0};event.eventType=kEventTypeTimer;event.eventArgSize=sizeof(tTimerEventArg);event.eventArg.pEventArg=&captured[index];
    return m7_cn_timer_event_current(&event);
}
static tCircBufInstance* queue;
static void* producer(void* arg)
{
    unsigned i;(void)arg;
    for (i=0;i<5000;i++) while (circbuf_writeData(queue,&i,sizeof(i))!=kCircBufOk) sched_yield();
    return NULL;
}
static void* consumer(void* arg)
{
    unsigned i,value;size_t size;(void)arg;
    for (i=0;i<5000;i++) {
        while (circbuf_readData(queue,&value,sizeof(value),&size)!=kCircBufOk) sched_yield();
        assert(size==sizeof(value) && value==i);
    }
    return NULL;
}
int main(int argc,char** argv)
{
    tCircBufInstance *peer=NULL,*extra=NULL;tTimerHdl handle=0,old=0,other=0;M7CnTimerStats stats;
    tTimerArg argument={0};unsigned i,value=123,output=0;size_t size=0;
    assert(argc==2);scenario=argv[1];argument.eventSink=kEventSinkNmtk;argument.argument.value=42;
    if (!strncmp(scenario,"queue_",6)) {
        if (is("queue_child")) { assert(circbuf_connect(0,&peer)!=kCircBufOk);goto done; }
        if (is("queue_alloc_failure")) {
            fail_alloc=1;assert(circbuf_alloc(0,128,&queue)!=kCircBufOk);assert(!m7_cn_private_buffers());goto done;
        }
        if (is("queue_bounds")) {
            assert(circbuf_alloc(NR_OF_CIRC_BUFFERS,128,&queue)!=kCircBufOk);
            assert(circbuf_alloc(0,SIZE_MAX,&queue)!=kCircBufOk);
            assert(eventucal_initQueueCircbuf(kEventQueueNum)!=kErrorOk && eventkcal_initQueueCircbuf((tEventQueue)-1)!=kErrorOk);
            assert(circbuf_alloc(0,1048580,&queue)!=kCircBufOk);assert(!m7_cn_private_buffers());goto done;
        }
        assert(circbuf_alloc(0,128,&queue)==kCircBufOk && m7_cn_private_buffers()==1);
        assert(circbuf_alloc(0,128,&extra)!=kCircBufOk);
        assert(circbuf_connect(0,&peer)==kCircBufOk && peer==queue);
        assert(circbuf_connect(0,&extra)!=kCircBufOk);
        if (is("queue_process_isolation")) {
            extern char** environ;pid_t pid;int status;char* args[]={argv[0],"queue_child",NULL};
            assert(!posix_spawn(&pid,argv[0],NULL,NULL,args,environ));assert(waitpid(pid,&status,0)==pid);
            assert(WIFEXITED(status) && WEXITSTATUS(status)==0);
        }
        if (is("queue_threads")) {
            pthread_t a,b;assert(!pthread_create(&a,NULL,producer,NULL) && !pthread_create(&b,NULL,consumer,NULL));
            assert(!pthread_join(a,NULL) && !pthread_join(b,NULL));assert(!circbuf_getDataCount(queue));
        } else {
            assert(circbuf_writeData(queue,&value,sizeof(value))==kCircBufOk);
            assert(circbuf_readData(peer,&output,sizeof(output),&size)==kCircBufOk && output==value && size==sizeof(value));
        }
        if (is("queue_owner_first")) {
            assert(circbuf_free(queue)==kCircBufOk && m7_cn_private_buffers()==1);
            assert(circbuf_connect(0,&extra)!=kCircBufOk);
            assert(circbuf_writeData(peer,&value,sizeof(value))==kCircBufOk);
            assert(circbuf_disconnect(peer)==kCircBufOk);
        } else { assert(circbuf_disconnect(peer)==kCircBufOk);assert(circbuf_free(queue)==kCircBufOk); }
        assert(!m7_cn_private_buffers());goto done;
    }
    if (!strncmp(scenario,"sem_",4)) {
        tOplkError result=m7_cn_event_sems_init();
        if (is("sem_init_first") || is("sem_init_second")) {
            assert(result==kErrorNoResource && !m7_cn_event_sem(0));allow=1;
            assert(m7_cn_event_sems_exit()!=kErrorOk && !sem_destroys);goto done;
        }
        assert(result==kErrorOk && m7_cn_event_sems_attach()==kErrorOk);
        assert(m7_cn_event_sem(0)!=m7_cn_event_sem(1));
        assert(m7_cn_event_sems_detach()!=kErrorOk && m7_cn_event_sems_exit()!=kErrorOk);
        allow=1;assert(m7_cn_event_sems_detach()==kErrorOk);result=m7_cn_event_sems_exit();
        if (is("sem_destroy_failure")) { assert(result!=kErrorOk && sem_destroys==1); }
        else assert(result==kErrorOk && sem_destroys==2 && !m7_cn_event_sem(0));
        i=sem_destroys;assert(m7_cn_event_sems_exit()!=kErrorOk && sem_destroys==i);goto done;
    }
    if (is("cond_clock_failure") || is("thread_failure")) {
        assert(timeru_init()==kErrorNoResource && timeru_init()!=kErrorOk && !created);goto done;
    }
    if (is("clock_failure")) {
        assert(timeru_init()==kErrorOk);i=0;
        do { m7_cn_timer_stats(0,&stats);if (!stats.fault) { const struct timespec pause={0,1000000};nanosleep(&pause,NULL); } } while (!stats.fault && ++i<1000);
        assert(m7_cn_timers_fault()!=kErrorOk);join_workers();assert(timeru_exit()!=kErrorOk && !cond_destroys);goto done;
    }
    if (!strncmp(scenario,"hres_",5)) {
        assert(hrestimer_init()==kErrorOk);
        assert(hrestimer_modifyTimer(&handle,1000000,callback,7,is("hres_repeat"))==kErrorOk);
        if (is("hres_capacity")) {
            tTimerHdl third=0;assert(hrestimer_modifyTimer(&other,1000000000,callback,8,FALSE)==kErrorOk);
            assert(hrestimer_modifyTimer(&third,1000000000,callback,9,FALSE)!=kErrorOk);
        }
        wait_for(&records,is("hres_repeat")?4:1);assert(captured[0].argument.value==7);
        old=handle;assert(hrestimer_modifyTimer(&handle,1000000000,callback,9,FALSE)==kErrorOk && handle!=old);
        assert(hrestimer_deleteTimer(&old)!=kErrorOk);assert(hrestimer_deleteTimer(&handle)==kErrorOk);
        assert(hrestimer_exit()!=kErrorOk);join_workers();assert(hrestimer_exit()==kErrorOk);goto done;
    }
    assert(timeru_init()==kErrorOk);
    if (is("timer_capacity")) {
        tTimerHdl handles[64]={0};
        for (i=0;i<64;i++) assert(timeru_setTimer(&handles[i],60000,&argument)==kErrorOk);
        assert(timeru_setTimer(&handle,60000,&argument)!=kErrorOk);
        old=handles[0];assert(timeru_deleteTimer(&handles[0])==kErrorOk);
        assert(timeru_setTimer(&handle,60000,&argument)==kErrorOk && handle!=old);
        assert(timeru_deleteTimer(&old)!=kErrorOk);goto stop_timer;
    }
    if (is("timer_bad_handle")) {
        handle=UINT64_MAX;assert(timeru_modifyTimer(&handle,1,&argument)!=kErrorOk);
        assert(timeru_deleteTimer(&handle)!=kErrorOk && !timeru_isActive(handle));
        assert(timeru_setTimer(NULL,1,&argument)!=kErrorOk);assert(timeru_setTimer(&other,ULONG_MAX,&argument)!=kErrorOk);goto stop_timer;
    }
    assert(timeru_setTimer(&handle,is("timer_zero")?0:1,&argument)==kErrorOk);old=handle;
    if (is("inflight_delete")) {
        wait_for(&entered,1);assert(timeru_deleteTimer(&handle)==kErrorOk);
        argument.argument.value=77;assert(timeru_setTimer(&handle,1,&argument)==kErrorOk && handle!=old);STORE(unblock,1);
        wait_for(&records,2);assert(!current(0) && current(1));assert(captured[0].argument.value==42 && captured[1].argument.value==77);
    } else if (is("post_failure")) {
        i=0;while (!m7_cn_timers_fault() && i++<1000) { const struct timespec pause={0,1000000};nanosleep(&pause,NULL); }
        assert(m7_cn_timers_fault()==kErrorNoResource);join_workers();assert(timeru_exit()!=kErrorOk);goto done;
    } else {
        wait_for(&records,1);assert(captured[0].timerHdl.handle==handle && captured[0].argument.value==42 && !timeru_isActive(handle));
        if (is("timer_modify")) {
            assert(timeru_modifyTimer(&handle,1,&argument)==kErrorOk && handle!=old);
            wait_for(&records,2);assert(!current(0) && current(1));
        } else if (is("timer_delete_reuse")) {
            assert(timeru_deleteTimer(&handle)==kErrorOk && !current(0));
            assert(timeru_setTimer(&handle,1,&argument)==kErrorOk && handle!=old);wait_for(&records,2);
            assert(timeru_deleteTimer(&old)!=kErrorOk && current(1));
        } else assert(current(0) && !current(0));
    }
stop_timer:
    assert(timeru_exit()!=kErrorOk);join_workers();
    if (is("cond_destroy_failure")) {
        assert(timeru_exit()!=kErrorOk && cond_destroys==1);assert(timeru_exit()!=kErrorOk && cond_destroys==1);
    } else {
        assert(timeru_exit()==kErrorOk);m7_cn_timer_stats(0,&stats);assert(!stats.allocated && !stats.active);
        assert(timeru_setTimer(&other,1,&argument)!=kErrorOk);
    }
done:
    printf("PASS private %s records=%u threads=%u semInit=%u semDestroy=%u condDestroy=%u buffers=%u\n",scenario,LOAD(records),created,sem_inits,sem_destroys,cond_destroys,m7_cn_private_buffers());
    return 0;
}
