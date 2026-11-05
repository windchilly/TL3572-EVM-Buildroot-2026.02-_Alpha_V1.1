/* Production transport, fake ALL socket/sysfs IO; optional real pthread join.
 * Each scenario is a new process. No raw socket or board is ever opened. */
#include <assert.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include "../source/powerlink/linux-cn/transport/edrv-m7-cn.c"
static const char* scenario;
static unsigned sockets,closes,joins,sends,callbacks,receives,polls;
static int clock_error,receive_once;
static const unsigned char mac[6]={2,0x10,0x20,0x30,0x40,0x50};
extern int __real_pthread_create(pthread_t*,const pthread_attr_t*,void*(*)(void*),void*);
extern int __real_pthread_clockjoin_np(pthread_t,void**,clockid_t,const struct timespec*);
extern int __real_clock_gettime(clockid_t,struct timespec*);
#define IS(name) (!strcmp(scenario,(name)))
char* __wrap_realpath(const char* path,char* result)
{
    if (strstr(path,"/driver")) strcpy(result,IS("identity_driver")?"/sys/bus/platform/drivers/rk_gmac-dwmac":"/sys/bus/usb/drivers/sr9900");
    else strcpy(result,IS("identity_port")?"/sys/devices/usb/1-1.9/1-1.9:1.0":"/sys/devices/usb/1-1.4.1/1-1.4.1:1.0");
    return result;
}
int __wrap_socket(int domain,int type,int protocol)
{
    ++sockets;assert(domain==AF_PACKET && type==(SOCK_RAW|SOCK_NONBLOCK|SOCK_CLOEXEC) && protocol==htons(0x88ab));
    if (IS("socket_failure")) { errno=EACCES;return -1; }return 42;
}
int __wrap_ioctl(int fd,unsigned long request,...)
{
    va_list args;struct ifreq* value;assert(fd==42);
    va_start(args,request);value=va_arg(args,struct ifreq*);va_end(args);assert(!strcmp(value->ifr_name,"eth2"));
    if (request==SIOCGIFINDEX) { if (IS("index_failure")) return -1;value->ifr_ifindex=7; }
    else { assert(request==SIOCGIFHWADDR);if (IS("mac_failure")) return -1;value->ifr_hwaddr.sa_family=ARPHRD_ETHER;memcpy(value->ifr_hwaddr.sa_data,mac,6); }
    return 0; /* No global interface-writing ioctl is accepted. */
}
int __wrap_bind(int fd,const struct sockaddr* address,socklen_t length)
{
    const struct sockaddr_ll* a=(const struct sockaddr_ll*)address;
    assert(fd==42 && length==sizeof(*a) && a->sll_ifindex==7 && a->sll_protocol==htons(0x88ab));
    return IS("bind_failure")?-1:0;
}
int __wrap_setsockopt(int fd,int level,int option,const void* value,socklen_t length)
{
    const struct packet_mreq* m=value;
    assert(fd==42 && level==SOL_PACKET && option==PACKET_ADD_MEMBERSHIP && length==sizeof(*m));
    assert(m->mr_ifindex==7 && m->mr_type==PACKET_MR_PROMISC);
    return (IS("membership_failure") || IS("init_close_failure"))?-1:0;
}
int __wrap_close(int fd)
{
    assert(fd==42);++closes;
    if (IS("close_failure") || IS("init_close_failure")) { errno=EINTR;return -1; }return 0;
}
int __wrap_pthread_create(pthread_t* t,const pthread_attr_t* a,void*(*fn)(void*),void* p)
{
    assert(fn==worker);if (IS("thread_failure")) return EAGAIN;
    if (IS("real_thread")) return __real_pthread_create(t,a,fn,p);
    *t=(pthread_t)123;return 0;
}
int __wrap_pthread_clockjoin_np(pthread_t t,void** value,clockid_t clock,const struct timespec* end)
{
    ++joins;assert(clock==CLOCK_MONOTONIC);assert(closes==0 && !LOAD(g.stats.active));
    if (IS("join_failure")) return ETIMEDOUT;
    if (IS("real_thread")) return __real_pthread_clockjoin_np(t,value,clock,end);
    assert(t==(pthread_t)123);return 0;
}
int __wrap_clock_gettime(clockid_t clock,struct timespec* t)
{
    assert(clock==CLOCK_MONOTONIC);
    if (clock_error) { errno=EIO;return -1; }return __real_clock_gettime(clock,t);
}
int __wrap_poll(struct pollfd* fds,nfds_t count,int timeout)
{
    assert(count==1 && fds[0].fd==42 && timeout==10);++polls;
    if (IS("poll_failure")) { errno=EIO;return -1; }
    if (receive_once) { receive_once=0;fds[0].revents=POLLIN;return 1; }
    if (!IS("real_thread")) STORE(g.stop,1);
    usleep(1000);return 0;
}
ssize_t __wrap_recvfrom(int fd,void* data,size_t bytes,int flags,struct sockaddr* address,socklen_t* length)
{
    struct sockaddr_ll* a=(struct sockaddr_ll*)address;unsigned char* p=data;
    assert(fd==42 && bytes==1514 && flags==(MSG_DONTWAIT|MSG_TRUNC));
    memset(p,0,64);p[6]=2;p[7]=3;p[12]=0x88;p[13]=0xab;
    a->sll_ifindex=7;a->sll_family=AF_PACKET;a->sll_pkttype=PACKET_HOST;
    *length=IS("rx_bad_meta")?0:sizeof(*a);return IS("rx_oversize")?1515:64;
}
ssize_t __wrap_send(int fd,const void* data,size_t bytes,int flags)
{
    (void)data;++sends;assert(fd==42 && flags==(MSG_DONTWAIT|MSG_NOSIGNAL));
    if (IS("send_failure")) { errno=ENETDOWN;return -1; }
    return IS("short_send")?(ssize_t)bytes-1:(ssize_t)bytes;
}
static tEdrvReleaseRxBuffer received(tEdrvRxBuffer* frame)
{
    assert(frame->rxFrameSize==64 && frame->pRxTimeStamp==NULL);++receives;
    return IS("deferred")?kEdrvReleaseRxBufferLater:kEdrvReleaseRxBufferImmediately;
}
static void sent(tEdrvTxBuffer* frame)
{
    ++callbacks;if (IS("callback_free")) assert(edrv_freeTxBuffer(frame)==kErrorOk);
}
static void* wrong_owner(void* init)
{
    assert(edrv_init(init)!=kErrorOk);assert(edrv_exit()!=kErrorOk);return NULL;
}
static tEdrvTxBuffer tx_buffer(void)
{
    tEdrvTxBuffer frame={0};unsigned char* p;
    frame.maxBufferSize=64;frame.txFrameSize=64;frame.pfnTxHandler=sent;
    assert(edrv_allocTxBuffer(&frame)==kErrorOk);p=frame.pBuffer;memset(p,0,64);memcpy(p+6,mac,6);p[12]=0x88;p[13]=0xab;
    return frame;
}
int main(int argc,char** argv)
{
    tEdrvInitParam init={0};M7CnEdrvStats stats;
    assert(argc==2);scenario=argv[1];init.pDevName="eth2";init.pfnRxHandler=received;
    if (IS("unarmed")) { assert(edrv_init(&init)!=kErrorOk);assert(!sockets);goto passed; }
    if (IS("identity_driver") || IS("identity_port")) { assert(!m7_cn_edrv_arm());assert(!m7_cn_edrv_arm());assert(!sockets);goto passed; }
    assert(m7_cn_edrv_arm());assert(!m7_cn_edrv_arm());
    if (IS("wrong_interface")) { init.pDevName="eth0";assert(edrv_init(&init)!=kErrorOk);assert(!sockets);goto passed; }
    if (IS("init_clock_failure")) { clock_error=1;assert(edrv_init(&init)!=kErrorOk);assert(!sockets);goto passed; }
    if (IS("init_close_failure")) {
        assert(edrv_init(&init)!=kErrorOk);assert(closes==1);assert(edrv_exit()!=kErrorOk);assert(closes==1);goto passed;
    }
    if (IS("socket_failure") || IS("index_failure") || IS("bind_failure") || IS("membership_failure") || IS("mac_failure") || IS("thread_failure")) {
        assert(edrv_init(&init)!=kErrorOk);assert(edrv_init(&init)!=kErrorOk);assert(sockets==1);
        assert(closes==(IS("socket_failure")?0U:1U));goto passed;
    }
    assert(edrv_init(&init)==kErrorOk);
    if (IS("send_failure") || IS("short_send") || IS("tx_limit") || IS("deadline")) {
        tEdrvTxBuffer frame=tx_buffer();
        if (IS("tx_limit")) STORE(g.stats.tx_attempts,M7_CN_MAX_TX);
        if (IS("deadline")) g.deadline=now_ns();
        assert(edrv_sendTxBuffer(&frame)!=kErrorOk);assert(callbacks==0);
        assert(edrv_freeTxBuffer(&frame)==kErrorOk);
    } else if (IS("normal") || IS("callback_free")) {
        tEdrvTxBuffer frame=tx_buffer();assert(edrv_sendTxBuffer(&frame)==kErrorOk);assert(sends==1 && callbacks==1);
        if (!IS("callback_free")) assert(edrv_freeTxBuffer(&frame)==kErrorOk);
    } else if (IS("bad_tx") || IS("bad_tx_source") || IS("busy_tx")) {
        tEdrvTxBuffer frame=tx_buffer();
        if (IS("bad_tx")) ((unsigned char*)frame.pBuffer)[13]=0;
        if (IS("bad_tx_source")) ((unsigned char*)frame.pBuffer)[6]^=1;
        if (IS("busy_tx")) frame.txBufferNumber.pArg=(void*)1;
        assert(edrv_sendTxBuffer(&frame)!=kErrorOk);assert(!sends);
        if (IS("busy_tx")) { assert(edrv_freeTxBuffer(&frame)!=kErrorOk);frame.txBufferNumber.pArg=NULL; }
        assert(edrv_freeTxBuffer(&frame)==kErrorOk);
    } else if (IS("rx") || IS("deferred")) {
        receive_once=1;worker(NULL);assert(receives==1 && polls==(IS("deferred")?1U:2U));
        if (IS("deferred")) assert(g.rx_data[12]==0x88 && g.rx_data[13]==0xab && LOAD(g.stats.fault)==F_DEFERRED);
    }
    else if (IS("rx_limit")) {
        STORE(g.stats.rx_seen,M7_CN_MAX_RX);receive_once=1;worker(NULL);assert(!receives && LOAD(g.stats.rx_delivered)==0);
    } else if (IS("rx_filter")) {
        struct sockaddr_ll from={.sll_family=AF_PACKET,.sll_ifindex=7,.sll_pkttype=PACKET_OUTGOING};
        deliver(g.rx_data,64,&from);from.sll_pkttype=PACKET_HOST;deliver(g.rx_data,13,&from);deliver(g.rx_data,1515,&from);
        memset(g.rx_data,0,64);deliver(g.rx_data,64,&from);assert(!receives && LOAD(g.stats.rx_dropped)==4);
    } else if (IS("clock_after_fault")) { fault(F_IO);clock_error=1; }
    else if (IS("inflight_timeout")) STORE(g.stats.inflight,1);
    else if (IS("wrong_owner")) {
        pthread_t thread;assert(!__real_pthread_create(&thread,NULL,wrong_owner,&init));assert(!pthread_join(thread,NULL));
    } else if (IS("poll_failure") || IS("rx_oversize") || IS("rx_bad_meta")) {
        receive_once=1;worker(NULL);assert(!receives);
    }
    else if (IS("real_thread")) usleep(3000);
    assert(edrv_init(&init)!=kErrorOk);assert(sockets==1);
    if (IS("join_failure") || IS("close_failure") || IS("clock_after_fault") || IS("inflight_timeout")) {
        assert(edrv_exit()!=kErrorOk);assert(edrv_exit()!=kErrorOk);
        assert(closes==(IS("close_failure")?1U:0U));
        if (IS("clock_after_fault")) assert(LOAD(g.stats.fault)==F_IO && joins==0);
    } else {
        assert(edrv_exit()==kErrorOk);assert(edrv_exit()==kErrorOk);
        assert(joins==1 && closes==1);assert(edrv_init(&init)!=kErrorOk);
    }
passed:
    m7_cn_edrv_stats(&stats);
    printf("CN TRANSPORT PASS %s socket=%u close=%u join=%u send=%u rx=%u fault=%u; ALL NETWORK IO FAKE\n",
        argv[1],sockets,closes,joins,sends,receives,stats.fault);
    return 0;
}
