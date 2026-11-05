/* New isolated Linux ETH3 CN test transport, not the UP2 GMAC1 EDRV.
 * Default unarmed; one owner/grant/init/stop attempt. Socket-scoped membership,
 * nonblocking IO, bounded worker checks and monotonic timed join. No cancel,
 * global interface writes, fake link-down completions or post-failure retries.
 * Budget checks cannot preempt a stuck callback. Unknown join/close retains
 * state/FD; full stack/frontend lifetime still needs independent integration.
 */
#include <common/oplkinc.h>
#include <kernel/edrv.h>
#include "m7_cn_edrv.h"
#include <arpa/inet.h>
#include <errno.h>
#include <limits.h>
#include <linux/if_packet.h>
#include <net/if.h>
#include <net/if_arp.h>
#include <poll.h>
#include <pthread.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#define LOAD(x) __atomic_load_n(&(x),__ATOMIC_ACQUIRE)
#define STORE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_RELEASE)
#define ADD(x,v) __atomic_fetch_add(&(x),(v),__ATOMIC_ACQ_REL)
enum { F_IDENTITY=1,F_CLOCK,F_SOCKET,F_BIND,F_MEMBERSHIP,F_THREAD,F_IO,F_BUDGET,F_DEFERRED,F_JOIN,F_CLOSE };
static struct {
    M7CnEdrvStats stats;
    tEdrvInitParam init;
    pthread_t owner,worker;
    int fd,ifindex,thread_created,stop;
    uint32_t arm_claimed;
    uint64_t deadline;
    unsigned char rx_data[1514]; /* Retained if a broken callback requests deferred release. */
} g={.fd=-1};

static void fault(uint32_t reason)
{
    uint32_t empty=0;
    (void)__atomic_compare_exchange_n(&g.stats.fault,&empty,reason,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE);
    STORE(g.stop,1);
}
static uint64_t now_ns(void)
{
    struct timespec t;
    if (clock_gettime(CLOCK_MONOTONIC,&t)) { STORE(g.stats.clock_failed,1);fault(F_CLOCK); return 0; }
    return (uint64_t)t.tv_sec*UINT64_C(1000000000)+(uint64_t)t.tv_nsec;
}
int m7_cn_edrv_arm(void)
{
    char driver[PATH_MAX],device[PATH_MAX];
    uint32_t empty=0;
    if (!__atomic_compare_exchange_n(&g.arm_claimed,&empty,1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) return 0;
    if (!realpath("/sys/class/net/eth2/device/driver",driver) ||
        strcmp(driver,"/sys/bus/usb/drivers/sr9900") ||
        !realpath("/sys/class/net/eth2/device",device) || !strstr(device,"/1-1.4.1/")) {
        fault(F_IDENTITY);return 0;
    }
    g.owner=pthread_self();STORE(g.stats.armed,1);return 1;
}
void m7_cn_edrv_stats(M7CnEdrvStats* out)
{
    if (!out) return;
#define COPY(name) out->name=LOAD(g.stats.name)
    COPY(armed);COPY(attempted);COPY(active);COPY(stop_attempted);COPY(joined);COPY(closed);COPY(fault);COPY(inflight);
    COPY(clock_failed);COPY(close_attempted);
    COPY(tx_attempts);COPY(tx_accepted);COPY(rx_seen);COPY(rx_delivered);COPY(rx_dropped);
#undef COPY
}
static int entering(void)
{
    uint64_t now;
    if (!LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault)) return 0;
    ADD(g.stats.inflight,1);
    now=now_ns();
    if (!LOAD(g.stats.active) || LOAD(g.stop) || LOAD(g.stats.fault) || now>=g.deadline) {
        if (now>=g.deadline) fault(F_BUDGET);
        ADD(g.stats.inflight,-1);return 0;
    }
    return 1;
}
static void deliver(void* data,size_t bytes,const struct sockaddr_ll* from)
{
    unsigned char* p=data;
    tEdrvRxBuffer rx={0};
    if (from->sll_family!=AF_PACKET || from->sll_ifindex!=g.ifindex || from->sll_pkttype==PACKET_OUTGOING || bytes<14 || bytes>1514 || p[12]!=0x88 || p[13]!=0xab ||
        !memcmp(p+6,g.init.aMacAddr,6)) { ADD(g.stats.rx_dropped,1);return; }
    if (!entering()) return;
    if (ADD(g.stats.rx_seen,1)>=M7_CN_MAX_RX) { fault(F_BUDGET);ADD(g.stats.inflight,-1);return; }
    ADD(g.stats.rx_delivered,1);
    rx.bufferInFrame=kEdrvBufferLastInFrame;rx.rxFrameSize=bytes;rx.pBuffer=data;
    if (g.init.pfnRxHandler(&rx)!=kEdrvReleaseRxBufferImmediately) fault(F_DEFERRED);
    ADD(g.stats.inflight,-1);
}
static void* worker(void* unused)
{
    (void)unused;
    while (!LOAD(g.stop)) {
        struct pollfd p={.fd=g.fd,.events=POLLIN};
        int result;
        if (now_ns()>=g.deadline) { fault(F_BUDGET);break; }
        if (LOAD(g.stats.clock_failed)) break;
        result=poll(&p,1,10);
        if (result<0) { if (errno==EINTR) continue;fault(F_IO);break; }
        if (p.revents&(POLLERR|POLLHUP|POLLNVAL)) { fault(F_IO);break; }
        if (result>0 && (p.revents&POLLIN) && !LOAD(g.stop)) {
            struct sockaddr_ll from={0};socklen_t length=sizeof(from);
            ssize_t bytes=recvfrom(g.fd,g.rx_data,sizeof(g.rx_data),MSG_DONTWAIT|MSG_TRUNC,(struct sockaddr*)&from,&length);
            if (bytes<0) { if (errno==EINTR || errno==EAGAIN || errno==EWOULDBLOCK) continue;fault(F_IO);break; }
            if (length!=sizeof(from) || from.sll_family!=AF_PACKET) { fault(F_IO);break; }
            deliver(g.rx_data,(size_t)bytes,&from);
        }
    }
    return NULL;
}
static int close_owned(void)
{
    if (g.fd<0) { STORE(g.stats.closed,1);return 1; }
    if (__atomic_exchange_n(&g.stats.close_attempted,1,__ATOMIC_ACQ_REL)) return 0;
    if (close(g.fd)) { fault(F_CLOSE);return 0; } /* Never retry ambiguous close. */
    g.fd=-1;STORE(g.stats.closed,1);return 1;
}
static tOplkError init_failed(uint32_t reason)
{
    fault(reason);
    (void)close_owned();
    return kErrorEdrvInit;
}
tOplkError edrv_init(const tEdrvInitParam* init)
{
    struct sockaddr_ll addr={0};struct packet_mreq membership={0};struct ifreq request={0};
    if (!init || !init->pDevName || strcmp(init->pDevName,"eth2") || !init->pfnRxHandler ||
        !LOAD(g.stats.armed) || !pthread_equal(g.owner,pthread_self()) || LOAD(g.stats.attempted) || LOAD(g.stats.fault))
        return kErrorEdrvInit;
    STORE(g.stats.attempted,1);g.init=*init;g.init.pDevName="eth2";
    g.deadline=now_ns();
    if (LOAD(g.stats.fault) || g.deadline>UINT64_MAX-M7_CN_ACTIVE_NS) return init_failed(F_CLOCK);
    g.deadline+=M7_CN_ACTIVE_NS;
    g.fd=socket(AF_PACKET,SOCK_RAW|SOCK_NONBLOCK|SOCK_CLOEXEC,htons(0x88ab));
    if (g.fd<0) return init_failed(F_SOCKET);
    memcpy(request.ifr_name,"eth2",5);
    if (ioctl(g.fd,SIOCGIFINDEX,&request) || request.ifr_ifindex<=0) return init_failed(F_IDENTITY);
    addr.sll_family=AF_PACKET;addr.sll_protocol=htons(0x88ab);addr.sll_ifindex=request.ifr_ifindex;
    g.ifindex=addr.sll_ifindex;
    if (bind(g.fd,(struct sockaddr*)&addr,sizeof(addr))) return init_failed(F_BIND);
    membership.mr_ifindex=addr.sll_ifindex;membership.mr_type=PACKET_MR_PROMISC;
    if (setsockopt(g.fd,SOL_PACKET,PACKET_ADD_MEMBERSHIP,&membership,sizeof(membership))) return init_failed(F_MEMBERSHIP);
    memset(&request,0,sizeof(request));memcpy(request.ifr_name,"eth2",5);
    if (ioctl(g.fd,SIOCGIFHWADDR,&request) || request.ifr_hwaddr.sa_family!=ARPHRD_ETHER) return init_failed(F_IDENTITY);
    memcpy(g.init.aMacAddr,request.ifr_hwaddr.sa_data,6);
    if ((g.init.aMacAddr[0]&1) || !memcmp(g.init.aMacAddr,"\0\0\0\0\0\0",6)) return init_failed(F_IDENTITY);
    STORE(g.stats.active,1);
    if (pthread_create(&g.worker,NULL,worker,NULL)) { STORE(g.stats.active,0);return init_failed(F_THREAD); }
    g.thread_created=1;return kErrorOk;
}
tOplkError edrv_exit(void)
{
    struct timespec end;uint64_t deadline;
    if (!LOAD(g.stats.attempted) || !LOAD(g.stats.armed) || !pthread_equal(g.owner,pthread_self())) return kErrorInvalidOperation;
    if (LOAD(g.stats.closed) && !LOAD(g.stats.active)) return kErrorOk;
    if (LOAD(g.stats.stop_attempted)) return kErrorInvalidOperation;
    STORE(g.stats.stop_attempted,1);STORE(g.stop,1);STORE(g.stats.active,0);
    deadline=now_ns()+M7_CN_JOIN_NS;
    end.tv_sec=(time_t)(deadline/UINT64_C(1000000000));end.tv_nsec=(long)(deadline%UINT64_C(1000000000));
    if (LOAD(g.stats.clock_failed)) return kErrorInvalidOperation;
    if (g.thread_created && pthread_clockjoin_np(g.worker,NULL,CLOCK_MONOTONIC,&end)) {
        fault(F_JOIN);return kErrorInvalidOperation;
    }
    STORE(g.stats.joined,1);
    while (LOAD(g.stats.inflight)) {
        struct timespec pause={.tv_nsec=1000000};
        if (now_ns()>=deadline || LOAD(g.stats.clock_failed)) { fault(F_JOIN);return kErrorInvalidOperation; }
        nanosleep(&pause,NULL);
    }
    return close_owned()?kErrorOk:kErrorInvalidOperation;
}
const UINT8* edrv_getMacAddr(void) { return g.init.aMacAddr; }
tOplkError edrv_allocTxBuffer(tEdrvTxBuffer* buffer)
{
    if (!buffer || buffer->maxBufferSize<14 || buffer->maxBufferSize>1514) return kErrorEdrvInvalidParam;
    buffer->pBuffer=malloc(buffer->maxBufferSize);buffer->txBufferNumber.pArg=NULL;
    return buffer->pBuffer?kErrorOk:kErrorEdrvNoFreeBufEntry;
}
tOplkError edrv_freeTxBuffer(tEdrvTxBuffer* buffer)
{
    if (!buffer || !buffer->pBuffer || LOAD(buffer->txBufferNumber.pArg)) return kErrorEdrvInvalidParam;
    free(buffer->pBuffer);buffer->pBuffer=NULL;return kErrorOk;
}
tOplkError edrv_sendTxBuffer(tEdrvTxBuffer* buffer)
{
    ssize_t bytes;unsigned char* data;void* clear=NULL;tEdrvTxHandler callback;
    if (!buffer || !buffer->pBuffer || buffer->txFrameSize<14 || buffer->txFrameSize>buffer->maxBufferSize ||
        buffer->txFrameSize>1514) return kErrorEdrvInvalidParam;
    data=buffer->pBuffer;
    if (data[12]!=0x88 || data[13]!=0xab || memcmp(data+6,g.init.aMacAddr,6)) return kErrorEdrvInvalidParam;
    if (!entering()) return kErrorInvalidOperation;
    if (!__atomic_compare_exchange_n(&buffer->txBufferNumber.pArg,&clear,(void*)1,0,__ATOMIC_ACQ_REL,__ATOMIC_ACQUIRE)) {
        ADD(g.stats.inflight,-1);return kErrorInvalidOperation;
    }
    if (ADD(g.stats.tx_attempts,1)>=M7_CN_MAX_TX) {
        fault(F_BUDGET);STORE(buffer->txBufferNumber.pArg,NULL);ADD(g.stats.inflight,-1);return kErrorInvalidOperation;
    }
    bytes=send(g.fd,data,buffer->txFrameSize,MSG_DONTWAIT|MSG_NOSIGNAL);
    callback=buffer->pfnTxHandler;STORE(buffer->txBufferNumber.pArg,NULL);
    if (bytes!=(ssize_t)buffer->txFrameSize) {
        fault(F_IO);ADD(g.stats.inflight,-1);return kErrorInvalidOperation;
    }
    ADD(g.stats.tx_accepted,1);
    if (callback) callback(buffer); /* Socket acceptance, NOT physical/CN delivery. */
    ADD(g.stats.inflight,-1);return kErrorOk;
}
tOplkError edrv_changeRxFilter(tEdrvFilter* filters,UINT count,UINT changed,UINT flags)
{ (void)filters;(void)count;(void)changed;(void)flags;return kErrorOk; }
tOplkError edrv_setRxMulticastMacAddr(const UINT8* mac) { return mac?kErrorOk:kErrorEdrvInvalidParam; }
tOplkError edrv_clearRxMulticastMacAddr(const UINT8* mac) { return mac?kErrorOk:kErrorEdrvInvalidParam; }
