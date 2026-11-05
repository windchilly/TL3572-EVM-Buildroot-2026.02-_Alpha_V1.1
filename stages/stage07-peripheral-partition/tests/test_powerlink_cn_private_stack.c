/* Actual fixed CN modules + original CiA401 OD, passive init/process/exit.
 * Only EDRV/network boundaries are simulated; no reset/start/RX/TX occurs. */
#include <oplk/oplk.h>
#include <common/m7_cn_private.h>
#include <common/m7_cn_lifecycle.h>
#include <common/m7_cn_edrv.h>
#include <kernel/edrv.h>
#include <kernel/nmtk.h>
#include <user/nmtu.h>
#include <obdcreate/obdcreate.h>
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <stdio.h>
#include <string.h>
#include <sys/mman.h>
#include <time.h>
static const char* scenario;
static M7CnEdrvStats transport={.armed=1};
static UINT8 mac[6]={2,16,32,48,64,80};
static unsigned creates,joins,stops,sems_destroyed,conditions_destroyed,callbacks;
static unsigned expected[2]={1,2};
void __wrap_m7_cn_edrv_stats(M7CnEdrvStats* stats) { *stats=transport; }
tOplkError __wrap_edrv_init(const tEdrvInitParam* param)
{
    assert(!strcmp(param->pDevName,"eth2") && param->pfnRxHandler);
    transport.attempted=1;
    if (!strcmp(scenario,"partial_edrv")) return kErrorNoResource;
    transport.active=1;return kErrorOk;
}
const UINT8* __wrap_edrv_getMacAddr(void) { return mac; }
tOplkError __wrap_edrv_exit(void)
{
    assert(m7_cn_stopping() && ++stops==1);
    transport.active=0;transport.stop_attempted=transport.joined=transport.closed=1;return kErrorOk;
}
tOplkError __wrap_edrv_sendTxBuffer(tEdrvTxBuffer* buffer) { (void)buffer;assert(0);return kErrorInvalidOperation; }
int __real_pthread_create(pthread_t*,const pthread_attr_t*,void* (*)(void*),void*);
int __wrap_pthread_create(pthread_t* thread,const pthread_attr_t* attr,void* (*entry)(void*),void* argument)
{
    creates++;
    if (!strcmp(scenario,"partial_thread") && creates==4) return EAGAIN;
    return __real_pthread_create(thread,attr,entry,argument);
}
int __real_pthread_clockjoin_np(pthread_t,void**,clockid_t,const struct timespec*);
int __wrap_pthread_clockjoin_np(pthread_t thread,void** result,clockid_t clock,const struct timespec* deadline)
{
    assert(clock==CLOCK_MONOTONIC && m7_cn_stopping());joins++;
    return __real_pthread_clockjoin_np(thread,result,clock,deadline);
}
int __real_sem_destroy(sem_t*);
int __wrap_sem_destroy(sem_t* sem)
{
    assert(joins==4 && transport.closed);sems_destroyed++;
    if (!strcmp(scenario,"pdo_mutex_failure")) {
        assert(sem!=m7_cn_event_sem(0) && sem!=m7_cn_event_sem(1) && sems_destroyed==1);return -1;
    }
    return __real_sem_destroy(sem);
}
int __real_pthread_cond_destroy(pthread_cond_t*);
int __wrap_pthread_cond_destroy(pthread_cond_t* cond)
{
    assert(joins==4 && transport.closed);conditions_destroyed++;return __real_pthread_cond_destroy(cond);
}
int __wrap_socket(int a,int b,int c) { (void)a;(void)b;(void)c;assert(0);return -1; }
sem_t* __wrap_sem_open(const char* name,int flags,...) { (void)name;(void)flags;assert(0);return SEM_FAILED; }
int __wrap_sem_unlink(const char* name) { (void)name;assert(0);return -1; }
int __wrap_shm_open(const char* name,int flags,mode_t mode) { (void)name;(void)flags;(void)mode;assert(0);return -1; }
int __wrap_shm_unlink(const char* name) { (void)name;assert(0);return -1; }
int __wrap_timer_create(clockid_t clock,struct sigevent* ev,timer_t* timer)
{ (void)clock;(void)ev;(void)timer;assert(0);return -1; }
int __wrap_system(const char* command) { (void)command;assert(0);return -1; }
int __wrap_pthread_setschedparam(pthread_t thread,int policy,const struct sched_param* param)
{ (void)thread;(void)policy;(void)param;assert(0);return -1; }
tOplkError __wrap_oplk_execNmtCommand(tNmtEvent event) { (void)event;assert(0);return kErrorInvalidOperation; }
static tOplkError event(tOplkApiEventType type,const tOplkApiEventArg* argument,void* context)
{
    unsigned index=__atomic_load_n(&callbacks,__ATOMIC_ACQUIRE);(void)context;
    assert(type==kOplkApiEventUserDef && index<2);
    assert(argument->pUserArg==&expected[index] && *(unsigned*)argument->pUserArg==index+1);
    __atomic_store_n(&callbacks,index+1,__ATOMIC_RELEASE);return kErrorOk;
}
int main(int argc,char** argv)
{
    tOplkApiInitParam init={0};M7CnLifecycleStats stats={0};M7CnTimerStats timers;
    tOplkError result;unsigned i,buffers;const struct timespec pause={0,1000000};
    assert(argc==2);scenario=argv[1];
    init.sizeOfInitParam=sizeof(init);init.hwParam.pDevName="eth2";init.nodeId=1;init.cycleLen=1000;
    init.pfnCbEvent=event;init.featureFlags=UINT_MAX;init.asyncMtu=1500;init.sdoStackType=0; /* standard SDO */
    assert(obdcreate_initObd(&init.obdInitParam)==kErrorOk);
    assert(oplk_initialize()==kErrorOk);
    result=oplk_create(&init);buffers=m7_cn_private_buffers();assert(buffers>0);
    if (!strncmp(scenario,"partial_",8)) {
        assert(result==kErrorNoResource);
        assert(oplk_destroy()==kErrorNoResource);oplk_exit();assert(oplk_destroy()==kErrorNoResource);
        m7_cn_lifecycle_stats(&stats);
        assert(stats.quiet && !stats.initialized && !stats.released && stats.first_error==kErrorNoResource);
        assert(stats.created==stats.joined && !sems_destroyed && !conditions_destroyed && m7_cn_private_buffers()==buffers);
        assert(stops==1 && !callbacks);
    } else if (!strcmp(scenario,"pdo_mutex_failure")) {
        assert(result==kErrorOk && oplk_destroy()==kErrorInvalidOperation);
        m7_cn_lifecycle_stats(&stats);
        assert(stats.quiet && stats.initialized && !stats.released && stats.first_error==kErrorInvalidOperation);
        assert(sems_destroyed==1 && !conditions_destroyed && m7_cn_private_buffers()==buffers);
        assert(oplk_destroy()==kErrorInvalidOperation);oplk_exit();assert(sems_destroyed==1 && stops==1);
    } else {
        assert(result==kErrorOk && nmtu_getNmtState()==kNmtGsOff);
        assert(oplk_postUserEvent(&expected[0])==kErrorOk && oplk_postUserEvent(&expected[1])==kErrorOk);
        for (i=0;i<1000 && __atomic_load_n(&callbacks,__ATOMIC_ACQUIRE)!=2;i++) nanosleep(&pause,NULL);
        assert(callbacks==2);
        for (i=0;i<128;i++) assert(oplk_process()==kErrorOk);
        assert(nmtu_getNmtState()==kNmtGsOff);
        assert(oplk_destroy()==kErrorOk && m7_cn_private_buffers()==0);
        m7_cn_lifecycle_stats(&stats);
        assert(stats.initialized && stats.quiet && stats.released && stats.created==15 && stats.joined==15);
        fprintf(stderr,"STACK COUNTERS creates=%u joins=%u stops=%u semDestroy=%u condDestroy=%u\n",creates,joins,stops,sems_destroyed,conditions_destroyed);
        /* Two event semaphores plus upstream PDO's private target mutex. */
        assert(creates==4 && joins==4 && stops==1 && sems_destroyed==3 && conditions_destroyed==2);
        m7_cn_timer_stats(0,&timers);assert(!timers.allocated && !timers.active && !timers.fault);
        m7_cn_timer_stats(1,&timers);assert(!timers.allocated && !timers.active && !timers.fault);
        oplk_exit();oplk_exit();assert(oplk_destroy()==kErrorOk && joins==4 && stops==1);
    }
    printf("PASS stack %s creates=%u joins=%u stops=%u callbacks=%u semDestroy=%u condDestroy=%u buffers=%u\n",
           scenario,creates,joins,stops,callbacks,sems_destroyed,conditions_destroyed,m7_cn_private_buffers());
    return 0;
}
