/* Production generic/ctrlu/ctrlk/lifecycle are linked from the built CN library.
 * Stack init/modules/EDRV/OS IO are mocked. No CN executable or raw socket runs.
 * real_threads additionally proves four real callbacks return before release. */
#include <common/m7_cn_lifecycle.h>
#include <common/m7_cn_edrv.h>
#include <common/ctrl.h>
#include <common/memmap.h>
#include <kernel/ctrlk.h>
#include <kernel/hrestimer.h>
#include <kernel/eventkcal.h>
#include <user/timeru.h>
#include <user/eventucal.h>
#include <oplk/oplk.h>
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <time.h>

static const char* scenario;
static M7CnEdrvStats transport;
static unsigned creates, joins, edrv_stops, releases, environment, target_inits;
static unsigned callbacks_done, real_threads, release_failed;
static const char* release_log[64];
static int is(const char* name) { return !strcmp(scenario,name); }
static M7CnLifecycleStats stats(void) { M7CnLifecycleStats s={0};m7_cn_lifecycle_stats(&s);return s; }
void __wrap_m7_cn_edrv_stats(M7CnEdrvStats* s) { *s=transport; }
tOplkError __wrap_edrv_exit(void)
{
    assert(m7_cn_stopping());assert(releases==0);assert(++edrv_stops==1);
    if (is("edrv_failure")) return kErrorInvalidOperation;
    transport.joined=1;transport.closed=!is("transport_unclosed");
    transport.inflight=is("transport_inflight");transport.fault=is("transport_fault");
    return kErrorOk;
}
int __real_pthread_create(pthread_t*,const pthread_attr_t*,void* (*)(void*),void*);
int __real_pthread_clockjoin_np(pthread_t,void**,clockid_t,const struct timespec*);
int __real_clock_gettime(clockid_t,struct timespec*);
int __wrap_pthread_create(pthread_t* thread,const pthread_attr_t* attr,void* (*entry)(void*),void* arg)
{
    creates++;
    if (is("thread_failure") && creates==3) return EAGAIN;
    if (real_threads) return __real_pthread_create(thread,attr,entry,arg);
    *thread=(pthread_t)creates;return 0;
}
int __wrap_pthread_clockjoin_np(pthread_t thread,void** result,clockid_t clock,const struct timespec* deadline)
{
    static const char* failures[]={"join_eventk","join_hres","join_eventu","join_timeru"};
    assert(m7_cn_stopping());assert(releases==0);assert(clock==CLOCK_MONOTONIC);
    joins++;
    if (is(failures[joins-1])) return ETIMEDOUT;
    if (real_threads) return __real_pthread_clockjoin_np(thread,result,clock,deadline);
    return 0;
}
int __wrap_clock_gettime(clockid_t clock,struct timespec* value)
{
    if (is("clock_failure")) return -1;
    return __real_clock_gettime(clock,value);
}
static void* callback(void* argument)
{
    const struct timespec pause={0,1000000},inflight={0,20000000};
    (void)argument;
    while (!m7_cn_stopping()) nanosleep(&pause,NULL);
    nanosleep(&inflight,NULL); /* already in flight when owner requested stop */
    assert(releases==0);
    __atomic_add_fetch(&callbacks_done,1,__ATOMIC_RELEASE);
    return NULL;
}
tOplkError __wrap_target_init(void) { target_inits++;return is("target_failure")?kErrorNoResource:kErrorOk; }
tOplkError __wrap_ctrlucal_init(void) { return kErrorOk; }
tOplkError __wrap_ctrlucal_checkKernelStack(void) { return kErrorOk; }
tMemMapReturn __wrap_memmap_init(void) { return kMemMapOk; }
tOplkError __wrap_ctrlu_checkKernelStackInfo(void) { return is("kernel_info_failure")?kErrorFeatureMismatch:kErrorOk; }
tOplkError __wrap_ctrlu_initStack(const tOplkApiInitParam* init)
{
    pthread_t thread;unsigned i;
    (void)init;
    transport.attempted=!is("no_transport");
    transport.active=transport.attempted;
    for (i=0;i<M7_CN_THREADS;i++) {
        if (is("partial_init") && i==2) return kErrorApiInvalidParam;
        if (is("missing_worker") && i==3) return kErrorOk;
        if (m7_cn_thread_create((enum M7CnThread)i,&thread,callback,NULL)) return kErrorNoResource;
    }
    return kErrorOk;
}
static tOplkError release(const char* name)
{
    M7CnLifecycleStats s=stats();
    assert(s.quiet && s.joined==s.created && s.initialized && m7_cn_can_release());
    assert(!release_failed);assert(releases<64);
    if (real_threads) assert(__atomic_load_n(&callbacks_done,__ATOMIC_ACQUIRE)==4);
    release_log[releases++]=name;
    if ((is("user_release_failure") && !strcmp(name,"sdocom_exit")) ||
        (is("kernel_release_failure") && !strcmp(name,"pdok_exit"))) {
        release_failed=1;return kErrorNoResource;
    }
    return kErrorOk;
}
#define EXIT(name) tOplkError __wrap_##name(void) { return release(#name); }
EXIT(sdocom_exit) EXIT(nmtcnu_exit) EXIT(nmtu_exit) EXIT(pdou_exit) EXIT(eventu_exit)
EXIT(dllucal_exit) EXIT(errhndu_exit)
EXIT(pdok_exit) EXIT(nmtk_exit) EXIT(dllk_exit) EXIT(dllkcal_exit) EXIT(eventk_exit) EXIT(errhndk_exit)
EXIT(obdal_exit) EXIT(obdu_exit)
/* Wrap internal references but retain __real versions for the pre-release gate. */
tOplkError __real_timeru_exit(void);
tOplkError __real_hrestimer_exit(void);
tOplkError __wrap_timeru_exit(void) { return release("timeru_exit"); }
tOplkError __wrap_hrestimer_exit(void) { return release("hrestimer_exit"); }
void __wrap_timesyncu_exit(void) { assert(release("timesyncu_exit")==kErrorOk); }
void __wrap_timesynck_exit(void) { assert(release("timesynck_exit")==kErrorOk); }
tOplkError __real_ctrlucal_executeCmd(tCtrlCmdType,UINT16*);
tOplkError __wrap_ctrlucal_executeCmd(tCtrlCmdType command,UINT16* result)
{
    assert(command==kCtrlCleanupStack);assert(m7_cn_can_release());
    if (is("kernel_retval_failure")) { *result=kErrorNoResource;return kErrorOk; }
    return __real_ctrlucal_executeCmd(command,result);
}
void __wrap_ctrlu_exit(void) { assert(m7_cn_released());environment++; }
tMemMapReturn __wrap_memmap_shutdown(void) { assert(m7_cn_released());environment++;return kMemMapOk; }
tOplkError __wrap_target_cleanup(void) { assert(m7_cn_released());environment++;return is("environment_failure")?kErrorNoResource:kErrorOk; }
/* Any accidental real transport init is a test failure, never a network action. */
int __wrap_socket(int domain,int type,int protocol) { (void)domain;(void)type;(void)protocol;assert(0);return -1; }
static void* wrong_owner(void* argument)
{
    (void)argument;assert(m7_cn_quiesce()==kErrorInvalidOperation);return NULL;
}
int main(int argc,char** argv)
{
    tOplkError result,initial;M7CnLifecycleStats s;unsigned old_joins,old_stops,old_releases;
    assert(argc==2);scenario=argv[1];transport.armed=!is("unarmed");real_threads=is("real_threads");
    /* Direct module exits also reject before the global quiescence proof. */
    assert(__real_timeru_exit()==kErrorInvalidOperation);
    assert(__real_hrestimer_exit()==kErrorInvalidOperation);
    assert(eventkcal_exit()==kErrorInvalidOperation);assert(eventucal_exit()==kErrorInvalidOperation);
    initial=oplk_initialize();
    if (is("unarmed")) { assert(initial==kErrorInvalidOperation);assert(!target_inits && !creates);goto done; }
    if (is("target_failure")) {
        assert(initial==kErrorNoResource);oplk_exit();oplk_exit();assert(!environment && !creates && !releases);goto done;
    }
    assert(initial==kErrorOk);
    initial=oplk_create(NULL);
    if (is("partial_init")) assert(initial==kErrorApiInvalidParam);
    else if (is("thread_failure")) assert(initial==kErrorNoResource);
    else if (is("kernel_info_failure")) assert(initial==kErrorFeatureMismatch);
    else if (is("no_transport") || is("missing_worker")) assert(initial==kErrorInvalidOperation);
    else assert(initial==kErrorOk);
    if (is("wrong_owner")) {
        pthread_t other;assert(!__real_pthread_create(&other,NULL,wrong_owner,NULL));assert(!pthread_join(other,NULL));
        assert(!m7_cn_stopping() && !joins && !edrv_stops && !releases);
    }
    if (is("double_create")) assert(oplk_create(NULL)==kErrorInvalidOperation);
    if (is("duplicate_slot")) {
        pthread_t duplicate;assert(m7_cn_thread_create(M7_CN_EVENTK,&duplicate,callback,NULL)==EPERM);assert(creates==4);
    }
    if (is("early_kernel_cleanup")) {
        UINT16 error=0;tCtrlKernelStatus status=kCtrlStatusUnchanged;BOOL exit_flag=TRUE;
        assert(ctrlk_executeCmd(kCtrlCleanupStack,&error,&status,&exit_flag)==kErrorOk);
        assert(error==kErrorInvalidOperation && status==kCtrlStatusUnchanged && !exit_flag);
        assert(!joins && !releases && !m7_cn_stopping());
    }
    result=oplk_destroy();s=stats();
    old_joins=joins;old_stops=edrv_stops;old_releases=releases;
    if (initial!=kErrorOk || is("clock_failure") || !strncmp(scenario,"join_",5) ||
        !strncmp(scenario,"transport_",10) || is("edrv_failure") || strstr(scenario,"release_failure") || is("kernel_retval_failure") || is("early_kernel_cleanup")) {
        assert(result!=kErrorOk);assert(!s.released);
        if (initial!=kErrorOk) assert(s.first_error==initial);
        if (strstr(scenario,"release_failure")) assert(release_failed);
        else if (!is("kernel_retval_failure")) assert(releases==0);
        assert(oplk_destroy()!=kErrorOk);oplk_exit();oplk_exit();assert(!environment);
        assert(__real_timeru_exit()==kErrorInvalidOperation);assert(__real_hrestimer_exit()==kErrorInvalidOperation);
    } else {
        assert(result==kErrorOk && s.released && s.quiet);
        assert(s.created==15 && s.joined==15 && joins==4);
        assert(releases==19 && !strcmp(release_log[0],"sdocom_exit") && !strcmp(release_log[18],"obdu_exit"));
        assert(oplk_destroy()==kErrorOk);oplk_exit();oplk_exit();assert(environment==3);
        if (is("environment_failure")) assert(stats().first_error==kErrorNoResource);
    }
    assert(joins==old_joins && edrv_stops==old_stops && releases==old_releases);
    { pthread_t extra;assert(m7_cn_thread_create(M7_CN_EVENTK,&extra,callback,NULL)==EPERM); }
    assert(oplk_initialize()==kErrorInvalidOperation);assert(oplk_create(NULL)==kErrorInvalidOperation);
done:
    printf("PASS lifecycle %s created=%u joined=%u stop=%u releases=%u env=%u\n",scenario,creates,joins,edrv_stops,releases,environment);
    return 0;
}
