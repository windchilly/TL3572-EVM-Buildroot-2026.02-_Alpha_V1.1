/* openPOWERLINK MN EDRV for UP2 GMAC1; no Linux data-plane proxy.
 * The hardware backend is supplied by the cumulative UniProton BSP, not by P0.
 */
#include "m7_edrv.h"
#include "m7_eth2_hw.h"
#if CONFIG_EDRV_AUTO_RESPONSE || EDRV_FILTER_WITH_RX_HANDLER || EDRV_USE_TTTX || \
    CONFIG_DLL_DEFERRED_RXFRAME_RELEASE_SYNC || CONFIG_DLL_DEFERRED_RXFRAME_RELEASE_ASYNC
#error "P1 EDRV does not support auto response, per-filter callbacks, launch-time or deferred RX"
#endif
#define MULTICASTS 8U
#define FILTERS 32U
enum DriverState { DOWN, RUNNING, FAULT };
static struct {
    enum DriverState state;
    BOOL polling;
    struct M7Eth2Dma* dma;
    tEdrvInitParam init;
    tEdrvTxBuffer* buffers[M7_ETH2_TX_BUFFERS];
    BOOL busy[M7_ETH2_TX_BUFFERS];
    tEdrvTxBuffer* queued[M7_ETH2_RING];
    UINT txHead, txTail, txCount, rxNext;
    UINT8 multicast[MULTICASTS][6];
    tEdrvFilter filters[FILTERS];
    UINT filterCount;
    tM7EdrvStats stats;
} instance;

static int bufferIndex(const tEdrvTxBuffer* buffer)
{
    UINT i;
    if (!buffer) return -1;
    for (i = 0; i < M7_ETH2_TX_BUFFERS; i++) {
        if (instance.buffers[i] == buffer &&
            buffer->pBuffer == instance.dma->txbuf[i] && buffer->txBufferNumber.value == i)
            return (int)i;
    }
    return -1;
}
static UINT32 dmaAddress(const void* address)
{
    /* Native tests model descriptors without dereferencing physical addresses. */
    return (UINT32)(uintptr_t)address;
}
static void rearmRx(UINT index)
{
    struct M7Eth2Desc* desc = &instance.dma->rx[index];
    desc->d[0] = dmaAddress(instance.dma->rxbuf[index]);
    desc->d[1] = 0; desc->d[2] = 0;
    m7_eth2_dma_barrier();
    desc->d[3] = M7_ETH2_OWN | (1U << 24);
    m7_eth2_dma_barrier();
}
static BOOL acceptFrame(const UINT8* packet)
{
    static const UINT8 broadcast[6] = {255,255,255,255,255,255};
    UINT i, byte;
    BOOL addressMatch = !memcmp(packet, instance.init.aMacAddr, 6) || !memcmp(packet, broadcast, 6);
    if (!addressMatch && (packet[0] & 1U)) {
        for (i = 0; i < MULTICASTS; i++) {
            if (!memcmp(packet, instance.multicast[i], 6)) { addressMatch = TRUE; break; }
        }
    }
    if (!addressMatch) return FALSE;
    for (i = 0; i < instance.filterCount; i++) {
        if (!instance.filters[i].fEnable) continue;
        for (byte = 0; byte < 22; byte++) {
            if (((packet[byte] ^ instance.filters[i].aFilterValue[byte]) &
                instance.filters[i].aFilterMask[byte]) != 0) break;
        }
        if (byte == 22) return TRUE;
    }
    return FALSE;
}
tOplkError edrv_init(const tEdrvInitParam* param)
{
    UINT i;
    int acquired;
    static const UINT8 zero[6] = {0};
    if (instance.state != DOWN || instance.polling) return kErrorInvalidOperation;
    if (!param || !param->pfnRxHandler || (param->aMacAddr[0] & 1U) ||
        !memcmp(param->aMacAddr, zero, 6)) return kErrorEdrvInvalidParam;
    acquired = m7_eth2_hw_acquire();
    if (acquired != 1) {
        if (acquired < 0) instance.state = FAULT;
        return kErrorEdrvInit;
    }
    memset(&instance, 0, sizeof(instance));
#ifdef M7_EDRV_NATIVE_TEST
    extern struct M7Eth2Dma m7_edrv_test_dma;
    instance.dma = &m7_edrv_test_dma;
#else
    instance.dma = (struct M7Eth2Dma*)M7_ETH2_DMA_ADDRESS;
#endif
    instance.init = *param;
    memset(instance.dma, 0, sizeof(*instance.dma));
    for (i = 0; i < M7_ETH2_RING; i++) rearmRx(i);
    instance.state = RUNNING;
    if (!m7_eth2_hw_start(instance.dma, instance.init.aMacAddr)) {
        instance.state = FAULT;
        if (m7_eth2_hw_stop()) instance.state = DOWN;
        return kErrorEdrvInit;
    }
    return kErrorOk;
}
tOplkError edrv_exit(void)
{
    UINT i;
    if (instance.polling) return kErrorInvalidOperation;
    if (instance.state == DOWN) return kErrorOk;
    instance.state = FAULT; /* Block submissions before stopping DMA. */
    if (!m7_eth2_hw_stop()) return kErrorInvalidOperation;
    /* Pending frames were cancelled, NOT successfully transmitted. No callbacks.
     * Buffer owners must remain alive through exit, including a failed exit. */
    for (i = 0; i < M7_ETH2_TX_BUFFERS; i++) {
        if (instance.buffers[i]) {
            instance.buffers[i]->pBuffer = NULL;
            instance.buffers[i]->maxBufferSize = 0;
        }
    }
    memset(instance.buffers, 0, sizeof(instance.buffers));
    memset(instance.busy, 0, sizeof(instance.busy));
    memset(instance.queued, 0, sizeof(instance.queued));
    instance.state = DOWN;
    return kErrorOk;
}
const UINT8* edrv_getMacAddr(void) { return instance.init.aMacAddr; }
const tM7EdrvStats* m7_edrv_stats(void) { return &instance.stats; }
tOplkError edrv_allocTxBuffer(tEdrvTxBuffer* buffer)
{
    UINT i;
    if (instance.state != RUNNING) return kErrorInvalidOperation;
    if (!buffer || !buffer->maxBufferSize || buffer->maxBufferSize > EDRV_MAX_ETH_SIZE)
        return kErrorEdrvInvalidParam;
    /* Repeated allocation of the same descriptor must not orphan its old slot. */
    for (i = 0; i < M7_ETH2_TX_BUFFERS; i++)
        if (instance.buffers[i] == buffer) return kErrorInvalidOperation;
    for (i = 0; i < M7_ETH2_TX_BUFFERS; i++) {
        if (!instance.buffers[i]) {
            instance.buffers[i] = buffer;
            buffer->pBuffer = instance.dma->txbuf[i];
            buffer->txBufferNumber.value = i;
            buffer->maxBufferSize = EDRV_MAX_ETH_SIZE;
            return kErrorOk;
        }
    }
    return kErrorEdrvNoFreeBufEntry;
}
tOplkError edrv_freeTxBuffer(tEdrvTxBuffer* buffer)
{
    int index;
    if (instance.state != RUNNING) return kErrorInvalidOperation;
    index = bufferIndex(buffer);
    if (index < 0) return kErrorEdrvBufNotExisting;
    if (instance.busy[index]) return kErrorInvalidOperation;
    instance.buffers[index] = NULL;
    buffer->pBuffer = NULL; buffer->maxBufferSize = 0;
    return kErrorOk;
}
tOplkError edrv_sendTxBuffer(tEdrvTxBuffer* buffer)
{
    struct M7Eth2Desc* desc;
    int index;
    if (instance.state != RUNNING) return kErrorInvalidOperation;
    index = bufferIndex(buffer);
    if (index < 0) return kErrorEdrvBufNotExisting;
    if (buffer->fLaunchTimeValid) return kErrorInvalidOperation;
    if (buffer->txFrameSize < EDRV_ETH_HDR_SIZE || buffer->txFrameSize > EDRV_MAX_ETH_SIZE)
        return kErrorEdrvInvalidParam;
    /* Keep one descriptor vacant, like stmmac: tail==head must not ambiguously
     * advertise a full ring as an empty one while DMA is stopped at its tail. */
    if (instance.busy[index] || instance.txCount == M7_ETH2_RING - 1U)
        return kErrorEdrvNoFreeTxDesc;
    desc = &instance.dma->tx[instance.txHead];
    if (desc->d[3] & M7_ETH2_OWN) { instance.state = FAULT; return kErrorInvalidOperation; }
    instance.busy[index] = TRUE;
    instance.queued[instance.txHead] = buffer;
    desc->d[0] = dmaAddress(buffer->pBuffer); desc->d[1] = 0;
    desc->d[2] = (UINT32)buffer->txFrameSize;
    m7_eth2_dma_barrier();
    /* Hardware supplies minimum-frame padding and FCS (CPC=0). */
    desc->d[3] = M7_ETH2_OWN | M7_ETH2_FIRST_LAST | (UINT32)buffer->txFrameSize;
    m7_eth2_dma_barrier();
    instance.txHead = (instance.txHead + 1U) % M7_ETH2_RING;
    instance.txCount++;
    m7_eth2_hw_write(0x1160U, 1U << 2); /* clear TX buffer unavailable */
    m7_eth2_hw_write(0x1120U, dmaAddress(&instance.dma->tx[instance.txHead]));
    return kErrorOk;
}
tOplkError edrv_setRxMulticastMacAddr(const UINT8* mac)
{
    UINT i;
    if (instance.state != RUNNING) return kErrorInvalidOperation;
    if (!mac || !(mac[0] & 1U)) return kErrorEdrvInvalidParam;
    for (i = 0; i < MULTICASTS; i++)
        if (!memcmp(instance.multicast[i], mac, 6)) return kErrorOk;
    for (i = 0; i < MULTICASTS; i++) {
        if (!instance.multicast[i][0]) { memcpy(instance.multicast[i], mac, 6); return kErrorOk; }
    }
    return kErrorEdrvNoFreeBufEntry;
}
tOplkError edrv_clearRxMulticastMacAddr(const UINT8* mac)
{
    UINT i;
    if (instance.state != RUNNING) return kErrorInvalidOperation;
    if (!mac || !(mac[0] & 1U)) return kErrorEdrvInvalidParam;
    for (i = 0; i < MULTICASTS; i++) {
        if (!memcmp(instance.multicast[i], mac, 6)) {
            memset(instance.multicast[i], 0, 6); return kErrorOk;
        }
    }
    return kErrorEdrvBufNotExisting;
}
tOplkError edrv_changeRxFilter(tEdrvFilter* filters, UINT count, UINT changed, UINT flags)
{
    if (instance.state != RUNNING) return kErrorInvalidOperation;
    if (count > FILTERS || (count && !filters) || (flags & ~EDRV_FILTER_CHANGE_ALL))
        return kErrorEdrvInvalidParam;
    if (changed >= count) {
        /* Upstream passes flags=0 for full replacement. Auto-response is disabled
         * in oplkcfg; pTxBuffer metadata is not used to send any automatic frame. */
        if (count) memcpy(instance.filters, filters, count * sizeof(*filters));
        instance.filterCount = count;
    } else {
        if (count != instance.filterCount) return kErrorEdrvInvalidParam;
        if (flags & EDRV_FILTER_CHANGE_AUTO_RESPONSE) return kErrorInvalidOperation;
        if (flags & EDRV_FILTER_CHANGE_VALUE)
            memcpy(instance.filters[changed].aFilterValue, filters[changed].aFilterValue, 22);
        if (flags & EDRV_FILTER_CHANGE_MASK)
            memcpy(instance.filters[changed].aFilterMask, filters[changed].aFilterMask, 22);
        if (flags & EDRV_FILTER_CHANGE_STATE)
            instance.filters[changed].fEnable = filters[changed].fEnable;
    }
    return kErrorOk;
}
tOplkError m7_edrv_poll(UINT budget)
{
    UINT done;
    tOplkError result = kErrorOk;
    if (instance.state != RUNNING || instance.polling) return kErrorInvalidOperation;
    if (!budget || budget > M7_ETH2_RING) return kErrorEdrvInvalidParam;
    instance.polling = TRUE;
    if (m7_eth2_hw_read(0x1160U) & (1U << 12)) {
        instance.stats.dmaFatal++; instance.state = FAULT; result = kErrorInvalidOperation;
        goto out;
    }
    /* Fixed work limit: a callback may resubmit, never spin without a bound. */
    for (done = 0; done < M7_ETH2_RING && instance.txCount; done++) {
        struct M7Eth2Desc* desc = &instance.dma->tx[instance.txTail];
        UINT32 status = desc->d[3];
        tEdrvTxBuffer* buffer;
        int index;
        if (status & M7_ETH2_OWN) break;
        m7_eth2_dma_barrier();
        if (status & M7_ETH2_ERROR) {
            instance.stats.txErrors++; instance.state = FAULT; result = kErrorInvalidOperation;
            goto out; /* No false-success completion callback. Reset required. */
        }
        buffer = instance.queued[instance.txTail]; index = bufferIndex(buffer);
        if (index < 0) { instance.state = FAULT; result = kErrorInvalidOperation; goto out; }
        instance.queued[instance.txTail] = NULL; instance.busy[index] = FALSE;
        instance.txTail = (instance.txTail + 1U) % M7_ETH2_RING; instance.txCount--;
        instance.stats.txCompleted++;
        if (buffer->pfnTxHandler) buffer->pfnTxHandler(buffer);
    }
    for (done = 0; done < budget; done++) {
        UINT index = instance.rxNext;
        UINT32 status = instance.dma->rx[index].d[3], size;
        if (status & M7_ETH2_OWN) break;
        m7_eth2_dma_barrier();
        size = status & 0x7fffU; /* ACS/CST off: descriptor length includes FCS. */
        if ((status & (M7_ETH2_ERROR | (1U << 30))) ||
            (status & M7_ETH2_FIRST_LAST) != M7_ETH2_FIRST_LAST ||
            size < EDRV_MIN_ETH_SIZE + EDRV_ETH_CRC_SIZE || size > EDRV_MAX_ETH_SIZE + EDRV_ETH_CRC_SIZE) {
            instance.stats.rxErrors++;
        } else if (acceptFrame(instance.dma->rxbuf[index])) {
            tEdrvRxBuffer rx;
            rx.bufferInFrame = kEdrvBufferLastInFrame; rx.rxFrameSize = size - EDRV_ETH_CRC_SIZE;
            rx.pBuffer = instance.dma->rxbuf[index]; rx.pRxTimeStamp = NULL;
            if (instance.init.pfnRxHandler(&rx) != kEdrvReleaseRxBufferImmediately) {
                instance.stats.rxDeferredRejected++; instance.state = FAULT;
                result = kErrorEdrvInvalidRxBuf; goto out; /* Do not overwrite held data. */
            }
            instance.stats.rxDelivered++;
        } else { instance.stats.rxDropped++; }
        rearmRx(index);
        m7_eth2_hw_write(0x1160U, 1U << 7); /* clear RX buffer unavailable */
        m7_eth2_hw_write(0x1128U, dmaAddress(&instance.dma->rx[index]));
        instance.rxNext = (index + 1U) % M7_ETH2_RING;
    }
out:
    instance.polling = FALSE;
    return result;
}
