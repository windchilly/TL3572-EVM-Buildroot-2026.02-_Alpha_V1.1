/* Actual CN user/kernel/OD/PDO/NMT/SDO/event/timer AND EDRV. Only network OS
 * boundaries are fake. No raw socket, device, real peer or NMT reset/start.
 * Five real pthreads, private sem/cond/queues, all joined before destruction. */
#include <oplk/oplk.h>
#include <common/m7_cn_private.h>
#include <common/m7_cn_lifecycle.h>
#include <common/m7_cn_startup.h>
#include <common/m7_cn_edrv.h>
#include <kernel/edrv.h>
#include <kernel/hrestimer.h>
#include <kernel/eventk.h>
#include <kernel/ctrlk.h>
#include <user/eventu.h>
#include <user/timeru.h>
#include <user/nmtu.h>
#include <obdcreate/obdcreate.h>
#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <net/if_arp.h>
#include <poll.h>
#include <pthread.h>
#include <semaphore.h>
#include <signal.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/socket.h>
#include <time.h>
#define LOAD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define STORE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#define ADD(x,v) __atomic_fetch_add(&(x),(v),__ATOMIC_ACQ_REL)
enum { FD=4242,INDEX=17 };
static const char* scenario;
static const UINT8 mac[6]={2,16,32,48,64,80};
static unsigned creates,joins,closes,binds,sockets,sems_destroyed,conditions_destroyed;
static unsigned callbacks,hres_callbacks,timer_posts,polls,receives,sends,tx_callbacks,timeout_clock,injected,io_go;
static pthread_t owner;
static _Thread_local unsigned worker_slot;
static struct Entry { void* (*function)(void*);void* argument;unsigned slot; } entries[5];
static tTimerHdl hres,user;
static unsigned payload=42;
static void* user_pointer=&payload;
static const struct timespec pause_ms={0,1000000};
static int is(const char* name) { return !strcmp(scenario,name); }
static void wait_for(unsigned* flag,unsigned minimum)
{
    unsigned i;for(i=0;i<1000 && LOAD(*flag)<minimum;i++) nanosleep(&pause_ms,NULL);
    assert(LOAD(*flag)>=minimum);
}
static tOplkError high_callback(const tTimerEventArg* event)
{ assert((m7_cn_ready() || m7_cn_stopping()) && event->argument.value==77);ADD(hres_callbacks,1);return kErrorOk; }
static void tx_callback(tEdrvTxBuffer* buffer) { (void)buffer;ADD(tx_callbacks,1); }
static tOplkError tx(void)
{
    UINT8 data[64]={0};tEdrvTxBuffer buffer={0};
    memset(data,0xff,6);memcpy(data+6,mac,6);data[12]=0x88;data[13]=0xab;
    buffer.pBuffer=data;buffer.maxBufferSize=buffer.txFrameSize=sizeof(data);buffer.pfnTxHandler=tx_callback;
    return edrv_sendTxBuffer(&buffer);
}
static void before_ready(void)
{
    tEvent event={0};tTimerArg argument={0};unsigned i;
    assert(!m7_cn_ready() && !LOAD(polls) && !LOAD(receives) && !LOAD(sends));
    assert(m7_cn_edrv_activate()==kErrorInvalidOperation); /* premature call cannot consume its attempt */
    assert(tx()==kErrorInvalidOperation && !LOAD(tx_callbacks));
    assert(oplk_execNmtCommand(kNmtEventSwReset)==kErrorInvalidOperation);
    assert(oplk_process()==kErrorInvalidOperation && oplk_postUserEvent(&payload)==kErrorInvalidOperation);
    event.eventSink=kEventSinkApi;event.eventType=kEventTypeApiUserDef;
    event.eventArg.pEventArg=&user_pointer;event.eventArgSize=sizeof(user_pointer);
    assert(eventk_process(&event)==kErrorInvalidOperation && eventu_process(&event)==kErrorInvalidOperation);
    assert(eventu_postEvent(&event)==kErrorOk); /* internal pending event; not dispatched yet */
    argument.eventSink=kEventSinkNmtk;argument.argument.value=kNmtEventNoEvent;
    assert(timeru_setTimer(&user,0,&argument)==kErrorOk);
    assert(hrestimer_modifyTimer(&hres,20000,high_callback,77,FALSE)==kErrorOk);
    for(i=0;i<20;i++) nanosleep(&pause_ms,NULL);
    assert(!LOAD(callbacks) && !LOAD(hres_callbacks) && !LOAD(timer_posts) && !LOAD(polls) && !LOAD(receives) && !LOAD(sends));
    STORE(injected,1);
}
int __wrap_socket(int domain,int type,int protocol)
{
    assert(domain==AF_PACKET && type==(SOCK_RAW|SOCK_NONBLOCK|SOCK_CLOEXEC) && protocol==0);
    assert(!m7_cn_ready() && ++sockets==1);
    if(is("socket_failure")) { errno=EMFILE;return -1; }return FD;
}
char* __wrap_realpath(const char* path,char* out)
{
    if(!strcmp(path,"/sys/class/net/eth2/device/driver")) strcpy(out,"/sys/bus/usb/drivers/sr9900");
    else { assert(!strcmp(path,"/sys/class/net/eth2/device"));strcpy(out,"/sys/devices/fake/1-1.4.1/net/eth2"); }
    return out;
}
int __wrap_ioctl(int fd,unsigned long request,...)
{
    va_list ap;struct ifreq* data;assert(fd==FD);va_start(ap,request);data=va_arg(ap,struct ifreq*);va_end(ap);
    assert(!strcmp(data->ifr_name,"eth2"));
    if(request==SIOCGIFINDEX) data->ifr_ifindex=INDEX;
    else { assert(request==SIOCGIFHWADDR);data->ifr_hwaddr.sa_family=ARPHRD_ETHER;memcpy(data->ifr_hwaddr.sa_data,mac,6); }
    return 0;
}
int __wrap_setsockopt(int fd,int level,int option,const void* data,socklen_t bytes)
{
    const struct packet_mreq* membership=data;
    assert(fd==FD && level==SOL_PACKET && option==PACKET_ADD_MEMBERSHIP && bytes==sizeof(*membership));
    assert(membership->mr_ifindex==INDEX && membership->mr_type==PACKET_MR_PROMISC);return 0;
}
int __wrap_bind(int fd,const struct sockaddr* data,socklen_t bytes)
{
    const struct sockaddr_ll* addr=(const struct sockaddr_ll*)data;M7CnLifecycleStats stats={0};
    assert(fd==FD && bytes==sizeof(*addr) && addr->sll_family==AF_PACKET && addr->sll_ifindex==INDEX && addr->sll_protocol==htons(0x88ab));
    m7_cn_lifecycle_stats(&stats);
    assert(stats.initialized && stats.created==15 && m7_cn_activation_allowed() && !m7_cn_ready() && LOAD(injected));
    assert(++binds==1 && !LOAD(polls) && !LOAD(receives) && !LOAD(callbacks) && tx()==kErrorInvalidOperation);
    if(is("bind_failure")) { errno=EIO;return -1; }return 0;
}
int __wrap_poll(struct pollfd* fd,nfds_t count,int timeout)
{
    assert(count==1 && fd->fd==FD && timeout==10);ADD(polls,1);fd->revents=0;
    if(LOAD(io_go) && !LOAD(receives) && (is("rx_delivery") || is("rx_io_failure"))) { fd->revents=POLLIN;return 1; }
    nanosleep(&pause_ms,NULL);return 0;
}
ssize_t __wrap_recvfrom(int fd,void* buffer,size_t size,int flags,struct sockaddr* address,socklen_t* length)
{
    struct sockaddr_ll* from=(struct sockaddr_ll*)address;UINT8* data=buffer;
    assert(fd==FD && size==1514 && flags==(MSG_DONTWAIT|MSG_TRUNC) && binds==1);assert(ADD(receives,1)==0);
    if(is("rx_io_failure")) { errno=EIO;return -1; }
    memset(data,0,64);memset(data,0xff,6);data[6]=2;data[11]=99;data[12]=0x88;data[13]=0xab;
    data[14]=0xff; /* unrecognized PLK type in GsOff: no reset/start or response */
    memset(from,0,sizeof(*from));from->sll_family=AF_PACKET;from->sll_ifindex=INDEX;from->sll_protocol=htons(0x88ab);
    from->sll_pkttype=PACKET_HOST;*length=sizeof(*from);return 64;
}
ssize_t __wrap_send(int fd,const void* data,size_t length,int flags)
{
    (void)data;assert(fd==FD && length==64 && flags==(MSG_DONTWAIT|MSG_NOSIGNAL) && m7_cn_ready());
    ADD(sends,1);return is("tx_short")?63:64;
}
int __wrap_close(int fd) { assert(fd==FD && !m7_cn_ready() && ++closes==1);return 0; }
int __real_pthread_create(pthread_t*,const pthread_attr_t*,void* (*)(void*),void*);
static void* run_worker(void* argument)
{
    struct Entry* entry=argument;worker_slot=entry->slot;return entry->function(entry->argument);
}
int __wrap_pthread_create(pthread_t* thread,const pthread_attr_t* attr,void* (*entry)(void*),void* argument)
{
    int result;assert(!m7_cn_ready());creates++;
    if(creates==5) {
        before_ready();
        if(is("partial_thread")) return EAGAIN;
        if(is("startup_timeout")) STORE(timeout_clock,1);
    }
    assert(creates<=5);entries[creates-1]=(struct Entry){entry,argument,creates};
    result=__real_pthread_create(thread,attr,run_worker,&entries[creates-1]);
    if(creates==5 && !result && !is("startup_timeout")) {
        unsigned i;for(i=0;i<20;i++) nanosleep(&pause_ms,NULL);
        /* All five real threads now exist while full-stack init is still pending. */
        assert(!m7_cn_ready() && !LOAD(polls) && !LOAD(receives) && !LOAD(sends) &&
               !LOAD(callbacks) && !LOAD(hres_callbacks) && !LOAD(timer_posts));
    }
    if(creates==5 && is("stop_pending")) m7_cn_fail(kErrorNoResource);
    return result;
}
int __real_pthread_clockjoin_np(pthread_t,void**,clockid_t,const struct timespec*);
int __wrap_pthread_clockjoin_np(pthread_t thread,void** result,clockid_t clock,const struct timespec* deadline)
{
    int ret;assert(clock==CLOCK_MONOTONIC && m7_cn_stopping() && !m7_cn_ready());joins++;
    ret=__real_pthread_clockjoin_np(thread,result,clock,deadline);
    if(is("join_failure") && joins==1) { assert(!ret);return ETIMEDOUT; }return ret;
}
int __real_sem_destroy(sem_t*);
int __wrap_sem_destroy(sem_t* sem)
{ assert(joins==5 && closes==1 && !m7_cn_ready());sems_destroyed++;return __real_sem_destroy(sem); }
int __real_pthread_cond_destroy(pthread_cond_t*);
int __wrap_pthread_cond_destroy(pthread_cond_t* cond)
{ assert(joins==5 && closes==1 && !m7_cn_ready());conditions_destroyed++;return __real_pthread_cond_destroy(cond); }
int __real_sem_clockwait(sem_t*,clockid_t,const struct timespec*);
int __wrap_sem_clockwait(sem_t* sem,clockid_t clock,const struct timespec* deadline)
{
    if(is("sem_wait_failure")) { errno=EINVAL;return -1; }
    return __real_sem_clockwait(sem,clock,deadline);
}
int __real_sem_post(sem_t*);
int __wrap_sem_post(sem_t* sem)
{
    if(is("sem_post_failure") && LOAD(io_go)) { errno=EOVERFLOW;return -1; }
    return __real_sem_post(sem);
}
int __real_clock_gettime(clockid_t,struct timespec*);
int __wrap_clock_gettime(clockid_t clock,struct timespec* value)
{
    int result=__real_clock_gettime(clock,value);
    if(LOAD(timeout_clock)) value->tv_sec+=9;
    if(is("event_clock_failure") && LOAD(io_go) && (worker_slot==1 || worker_slot==4) && clock==CLOCK_MONOTONIC) {
        /* Only event workers: identify them through the test trampoline. */
        errno=EIO;return -1;
    }
    return result;
}
tOplkError __real_eventu_postEvent(const tEvent*);
tOplkError __wrap_eventu_postEvent(const tEvent* event)
{
    if(event->eventType==kEventTypeTimer) {
        assert(m7_cn_ready() || m7_cn_stopping());ADD(timer_posts,1);
        if(is("timer_post_failure")) return kErrorNoResource;
    }
    return __real_eventu_postEvent(event);
}
sem_t* __wrap_sem_open(const char* n,int f,...) { (void)n;(void)f;assert(0);return SEM_FAILED; }
int __wrap_sem_unlink(const char* n) { (void)n;assert(0);return -1; }
int __wrap_shm_open(const char* n,int f,mode_t m) { (void)n;(void)f;(void)m;assert(0);return -1; }
int __wrap_shm_unlink(const char* n) { (void)n;assert(0);return -1; }
int __wrap_timer_create(clockid_t c,struct sigevent* e,timer_t* t) { (void)c;(void)e;(void)t;assert(0);return -1; }
int __wrap_system(const char* c) { (void)c;assert(0);return -1; }
int __wrap_pthread_setschedparam(pthread_t t,int p,const struct sched_param* s) { (void)t;(void)p;(void)s;assert(0);return -1; }
static tOplkError app_event(tOplkApiEventType type,const tOplkApiEventArg* argument,void* context)
{
    (void)context;assert((m7_cn_ready() || m7_cn_stopping()) && type==kOplkApiEventUserDef && argument->pUserArg==&payload);
    ADD(callbacks,1);return is("dispatch_failure")?kErrorNoResource:kErrorOk;
}
int main(int argc,char** argv)
{
    tOplkApiInitParam init={0};M7CnLifecycleStats stats={0};M7CnEdrvStats transport={0};
    tOplkError result,first;unsigned i,buffers,oldjoins,oldcloses;
    assert(argc==2);scenario=argv[1];owner=pthread_self();assert(!m7_cn_ready());
    assert(m7_cn_edrv_arm());assert(oplk_initialize()==kErrorOk);
    init.sizeOfInitParam=sizeof(init);init.hwParam.pDevName="eth2";init.nodeId=1;init.cycleLen=1000;
    init.pfnCbEvent=app_event;init.featureFlags=UINT_MAX;init.asyncMtu=1500;init.sdoStackType=0;
    assert(obdcreate_initObd(&init.obdInitParam)==kErrorOk);result=oplk_create(&init);buffers=m7_cn_private_buffers();
    if(is("partial_thread") || is("socket_failure") || is("bind_failure") || is("startup_timeout") || is("stop_pending")) {
        assert(result!=kErrorOk && !m7_cn_ready() && m7_cn_stopping());
        assert(!LOAD(polls) && !LOAD(receives) && !LOAD(sends) && !LOAD(callbacks) && !LOAD(hres_callbacks));
        assert(binds==(unsigned)is("bind_failure"));
    } else {
        assert(result==kErrorOk);
        if(!is("sem_wait_failure") && !is("timer_post_failure") && !is("dispatch_failure")) {
            wait_for(&callbacks,1);wait_for(&hres_callbacks,1);wait_for(&timer_posts,1);
            assert(nmtu_getNmtState()==kNmtGsOff);
        }
        assert(m7_cn_edrv_activate()==kErrorInvalidOperation && binds==1);
        STORE(io_go,1);
        if(is("tx_acceptance") || is("tx_short")) {
            assert(tx()==(is("tx_short")?kErrorInvalidOperation:kErrorOk));
            assert(LOAD(sends)==1 && LOAD(tx_callbacks)==(unsigned)is("tx_acceptance"));
        }
        if(is("rx_delivery") || is("rx_io_failure")) wait_for(&receives,1);
        if(is("rx_delivery")) {
            for(i=0;i<1000;i++) { m7_cn_edrv_stats(&transport);if(transport.rx_delivered && !transport.inflight) break;nanosleep(&pause_ms,NULL); }
            assert(transport.rx_delivered==1 && !transport.inflight);
        }
        if(is("sem_post_failure")) assert(oplk_postUserEvent(&payload)==kErrorOk);
        if(is("early_kernel_cleanup")) {
            UINT16 error=0;tCtrlKernelStatus status=kCtrlStatusUnchanged;BOOL exit_flag=TRUE;
            assert(ctrlk_executeCmd(kCtrlCleanupStack,&error,&status,&exit_flag)==kErrorOk);
            assert(error==kErrorInvalidOperation && status==kCtrlStatusUnchanged && !exit_flag);
        }
        if(is("rx_io_failure") || is("sem_wait_failure") || is("event_clock_failure") ||
           is("sem_post_failure") || is("timer_post_failure") || is("dispatch_failure")) {
            for(i=0;i<1000 && !m7_cn_stopping();i++) nanosleep(&pause_ms,NULL);
            assert(m7_cn_stopping() && !m7_cn_ready());
        }
    }
    result=oplk_destroy();m7_cn_lifecycle_stats(&stats);m7_cn_edrv_stats(&transport);
    assert(!m7_cn_ready() && m7_cn_stopping() && !transport.inflight);
    assert(LOAD(sends)==(unsigned)(is("tx_acceptance") || is("tx_short")));
    if(is("normal") || is("rx_delivery") || is("tx_acceptance")) {
        assert(result==kErrorOk && stats.quiet && stats.released && !stats.first_error && stats.created==15 && stats.joined==15);
        assert(creates==5 && joins==5 && closes==1 && sems_destroyed==3 && conditions_destroyed==2 && !m7_cn_private_buffers());
        assert(transport.rx_delivered==(uint64_t)is("rx_delivery") && transport.tx_accepted==(uint64_t)is("tx_acceptance"));
    } else {
        assert(result!=kErrorOk && stats.first_error && !stats.released && !sems_destroyed && !conditions_destroyed);
        assert(m7_cn_private_buffers()==buffers);
        if(is("stop_pending") || is("timer_post_failure") || is("dispatch_failure")) assert(stats.first_error==kErrorNoResource);
        if(is("socket_failure")) assert(stats.first_error==kErrorEdrvInit && !closes && creates==2 && joins==2);
    }
    first=stats.first_error;oldjoins=joins;oldcloses=closes;
    assert(oplk_process()==kErrorInvalidOperation && tx()==kErrorInvalidOperation);
    oplk_exit();oplk_exit();assert(oplk_destroy()==result && joins==oldjoins && closes==oldcloses);
    m7_cn_lifecycle_stats(&stats);assert(stats.first_error==first);
    printf("PASS startup %s creates=%u joins=%u binds=%u closes=%u callbacks=%u hres=%u timer=%u rx=%llu tx=%llu released=%u first=%u\n",
        scenario,creates,joins,binds,closes,LOAD(callbacks),LOAD(hres_callbacks),LOAD(timer_posts),
        (unsigned long long)transport.rx_delivered,(unsigned long long)transport.tx_accepted,stats.released,(unsigned)first);
    return 0;
}
