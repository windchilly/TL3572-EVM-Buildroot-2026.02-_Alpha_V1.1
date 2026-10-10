/* Executes the real EDRV C implementation; only BSP/MMIO/DMA completion are fake.
 * Never touches a board, never proves Ethernet electrical operation or latency. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "m7_edrv.h"
#include "m7_eth2_hw.h"
struct M7Eth2Dma m7_edrv_test_dma;
static int acquireResult = 1, startResult = 1, stopResult = 1, acquires, starts, stops, writes;
static UINT32 dmaStatus;
static UINT txCallbacks, rxCallbacks, expectedRxSize = 60U;
static BOOL deferRx, resendTx;
static const UINT8 ownMac[6] = {2,0x55,0x50,0x32,0,2};
static const UINT8 groupMac[6] = {1,0x11,0x1e,0,0,1};
static tEdrvTxBuffer tx[M7_ETH2_TX_BUFFERS + 1];
int m7_eth2_hw_acquire(void) { acquires++; return acquireResult; }
int m7_eth2_hw_start(struct M7Eth2Dma* dma, const uint8_t mac[6])
{
    UINT i;
    assert(dma == &m7_edrv_test_dma && !memcmp(mac, ownMac, 6));
    for (i = 0; i < M7_ETH2_RING; i++) {
        assert(dma->rx[i].d[3] == (M7_ETH2_OWN | (1U << 24)));
        assert(dma->tx[i].d[3] == 0);
    }
    starts++;
    return startResult;
}
int m7_eth2_hw_stop(void) { stops++; return stopResult; }
uint32_t m7_eth2_hw_read(uint32_t offset) { assert(offset == 0x1160); return dmaStatus; }
void m7_eth2_hw_write(uint32_t offset, uint32_t value)
{
    assert(offset == 0x1160 || offset == 0x1120 || offset == 0x1128);
    if (offset == 0x1160) dmaStatus &= ~value;
    writes++;
}
static void completed(tEdrvTxBuffer* buffer)
{
    txCallbacks++;
    assert(edrv_exit() == kErrorInvalidOperation);
    assert(m7_edrv_poll(1) == kErrorInvalidOperation);
    if (resendTx) {
        resendTx = FALSE;
        assert(edrv_sendTxBuffer(buffer) == kErrorOk);
    } else { assert(edrv_freeTxBuffer(buffer) == kErrorOk); }
}
static tEdrvReleaseRxBuffer received(tEdrvRxBuffer* buffer)
{
    rxCallbacks++;
    assert(buffer->rxFrameSize == expectedRxSize && buffer->pRxTimeStamp == NULL);
    assert(buffer->bufferInFrame == kEdrvBufferLastInFrame);
    assert(edrv_exit() == kErrorInvalidOperation);
    assert(m7_edrv_poll(1) == kErrorInvalidOperation);
    return deferRx ? kEdrvReleaseRxBufferLater : kEdrvReleaseRxBufferImmediately;
}
static tEdrvInitParam parameters(void)
{
    tEdrvInitParam param;
    memset(&param, 0, sizeof(param)); memcpy(param.aMacAddr, ownMac, 6);
    param.pfnRxHandler = received;
    return param;
}
static void begin(void)
{
    tEdrvInitParam param = parameters();
    tEdrvFilter filter;
    assert(sizeof(m7_edrv_test_dma) == 61696U);
    assert(edrv_init(&param) == kErrorOk);
    assert(!memcmp(edrv_getMacAddr(), ownMac, 6));
    memset(&filter, 0, sizeof(filter)); filter.fEnable = TRUE;
    assert(edrv_changeRxFilter(&filter, 1, 1, 0) == kErrorOk);
}
static void alloc(UINT index)
{
    tx[index].maxBufferSize = 1514;
    assert(edrv_allocTxBuffer(&tx[index]) == kErrorOk);
    assert(tx[index].pBuffer == m7_edrv_test_dma.txbuf[index]);
    tx[index].txFrameSize = 60;
    memset(tx[index].pBuffer, (int)index, 60);
}
static void complete(UINT index) { m7_edrv_test_dma.tx[index].d[3] = 0; }
static void rxFrame(UINT slot, const UINT8* dest, UINT length)
{
    memset(m7_edrv_test_dma.rxbuf[slot], 0, M7_ETH2_BUFFER_SIZE);
    memcpy(m7_edrv_test_dma.rxbuf[slot], dest, 6);
    m7_edrv_test_dma.rxbuf[slot][12] = 0x88; m7_edrv_test_dma.rxbuf[slot][13] = 0xab;
    m7_edrv_test_dma.rx[slot].d[3] = M7_ETH2_FIRST_LAST | length;
}
static void test_init(void)
{
    tEdrvInitParam param = parameters();
    assert(edrv_init(NULL) == kErrorEdrvInvalidParam);
    param.aMacAddr[0] = 1; assert(edrv_init(&param) == kErrorEdrvInvalidParam);
    param = parameters(); param.pfnRxHandler = NULL;
    assert(edrv_init(&param) == kErrorEdrvInvalidParam);
    assert(!acquires && !starts && !writes);
    param = parameters(); acquireResult = 0;
    memset(&m7_edrv_test_dma, 0xa5, sizeof(m7_edrv_test_dma));
    assert(edrv_init(&param) == kErrorEdrvInit);
    assert(m7_edrv_test_dma.tx[0].d[0] == 0xa5a5a5a5U && !starts && !writes);
    acquireResult = -1; stopResult = 0;
    assert(edrv_init(&param) == kErrorEdrvInit);
    assert(edrv_init(&param) == kErrorInvalidOperation);
    assert(edrv_exit() == kErrorInvalidOperation);
    stopResult = 1; assert(edrv_exit() == kErrorOk);
    acquireResult = 1; startResult = 0;
    assert(edrv_init(&param) == kErrorEdrvInit);
    stopResult = 0; assert(edrv_init(&param) == kErrorEdrvInit);
    assert(edrv_init(&param) == kErrorInvalidOperation);
    stopResult = 1; assert(edrv_exit() == kErrorOk);
    startResult = 1; begin();
    assert(edrv_init(&param) == kErrorInvalidOperation);
    assert(edrv_exit() == kErrorOk && edrv_exit() == kErrorOk);
}
static void test_buffers(void)
{
    UINT i;
    tEdrvTxBuffer forged;
    begin(); assert(edrv_allocTxBuffer(NULL) == kErrorEdrvInvalidParam);
    tx[32].maxBufferSize = 1515;
    assert(edrv_allocTxBuffer(&tx[32]) == kErrorEdrvInvalidParam);
    for (i = 0; i < M7_ETH2_TX_BUFFERS; i++) alloc(i);
    tx[32].maxBufferSize = 1514;
    assert(edrv_allocTxBuffer(&tx[32]) == kErrorEdrvNoFreeBufEntry);
    assert(edrv_allocTxBuffer(&tx[0]) == kErrorInvalidOperation);
    forged = tx[0]; assert(edrv_sendTxBuffer(&forged) == kErrorEdrvBufNotExisting);
    assert(edrv_freeTxBuffer(&forged) == kErrorEdrvBufNotExisting);
    tx[0].pBuffer = m7_edrv_test_dma.txbuf[1];
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorEdrvBufNotExisting);
    tx[0].pBuffer = m7_edrv_test_dma.txbuf[0];
    tx[0].fLaunchTimeValid = TRUE;
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorInvalidOperation);
    tx[0].fLaunchTimeValid = FALSE; tx[0].txFrameSize = 1515;
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorEdrvInvalidParam);
    tx[0].txFrameSize = 13; assert(edrv_sendTxBuffer(&tx[0]) == kErrorEdrvInvalidParam);
    assert(edrv_freeTxBuffer(&tx[0]) == kErrorOk);
    assert(edrv_freeTxBuffer(&tx[0]) == kErrorEdrvBufNotExisting);
    alloc(0); assert(edrv_exit() == kErrorOk);
    for (i = 0; i < M7_ETH2_TX_BUFFERS; i++) assert(!tx[i].pBuffer);
}
static void test_tx_wrap(void)
{
    UINT i, round, slot = 0;
    begin(); for (i = 0; i < 9; i++) alloc(i);
    for (round = 0; round < 5; round++) {
        for (i = 0; i < 7; i++) {
            assert(edrv_sendTxBuffer(&tx[i]) == kErrorOk);
            assert(m7_edrv_test_dma.tx[(slot+i)%8].d[0] == (UINT32)(uintptr_t)tx[i].pBuffer);
            assert(m7_edrv_test_dma.tx[(slot+i)%8].d[3] == (M7_ETH2_OWN | M7_ETH2_FIRST_LAST | 60U));
            assert(edrv_freeTxBuffer(&tx[i]) == kErrorInvalidOperation);
        }
        assert(edrv_sendTxBuffer(&tx[8]) == kErrorEdrvNoFreeTxDesc);
        assert(edrv_sendTxBuffer(&tx[0]) == kErrorEdrvNoFreeTxDesc);
        assert(m7_edrv_poll(8) == kErrorOk && m7_edrv_stats()->txCompleted == round * 7);
        for (i = 0; i < 7; i++) complete((slot+i)%8);
        assert(m7_edrv_poll(8) == kErrorOk && m7_edrv_stats()->txCompleted == (round + 1) * 7);
        slot = (slot + 7U) % 8U;
    }
    assert(edrv_exit() == kErrorOk);
}
static void test_tx_callback(void)
{
    begin(); alloc(0); tx[0].pfnTxHandler = completed; resendTx = TRUE;
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorOk); complete(0);
    assert(m7_edrv_poll(8) == kErrorOk && txCallbacks == 1);
    assert(m7_edrv_test_dma.tx[1].d[3] & M7_ETH2_OWN);
    complete(1); assert(m7_edrv_poll(8) == kErrorOk && txCallbacks == 2 && !tx[0].pBuffer);
    assert(edrv_exit() == kErrorOk);
}
static void test_tx_error(void)
{
    begin(); alloc(0); tx[0].pfnTxHandler = completed;
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorOk);
    m7_edrv_test_dma.tx[0].d[3] = M7_ETH2_ERROR;
    assert(m7_edrv_poll(8) == kErrorInvalidOperation && !txCallbacks && m7_edrv_stats()->txErrors == 1);
    assert(edrv_freeTxBuffer(&tx[0]) == kErrorInvalidOperation);
    assert(edrv_exit() == kErrorOk);
    begin(); alloc(0); assert(edrv_sendTxBuffer(&tx[0]) == kErrorOk);
    dmaStatus = 1U << 12;
    assert(m7_edrv_poll(1) == kErrorInvalidOperation && m7_edrv_stats()->dmaFatal == 1);
    assert(edrv_exit() == kErrorOk);
}
static void test_stop(void)
{
    tEdrvInitParam param = parameters();
    begin(); alloc(0); tx[0].pfnTxHandler = completed;
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorOk); stopResult = 0;
    assert(edrv_exit() == kErrorInvalidOperation && tx[0].pBuffer && !txCallbacks);
    assert(edrv_init(&param) == kErrorInvalidOperation);
    assert(edrv_sendTxBuffer(&tx[0]) == kErrorInvalidOperation);
    assert(edrv_freeTxBuffer(&tx[0]) == kErrorInvalidOperation);
    stopResult = 1; assert(edrv_exit() == kErrorOk && !tx[0].pBuffer && !txCallbacks);
    begin(); assert(edrv_exit() == kErrorOk);
}
static void test_rx_filters(void)
{
    UINT i;
    UINT8 extraGroup[6] = {1,0x11,0x1e,0,0,0x10};
    static const UINT8 broadcast[6] = {255,255,255,255,255,255};
    tEdrvFilter filters[2];
    begin(); rxFrame(0, groupMac, 64);
    assert(m7_edrv_poll(1) == kErrorOk && !rxCallbacks && m7_edrv_stats()->rxDropped == 1);
    assert(edrv_setRxMulticastMacAddr(groupMac) == kErrorOk);
    assert(edrv_setRxMulticastMacAddr(groupMac) == kErrorOk);
    rxFrame(1, groupMac, 64); assert(m7_edrv_poll(1) == kErrorOk && rxCallbacks == 1);
    assert(edrv_clearRxMulticastMacAddr(groupMac) == kErrorOk);
    assert(edrv_clearRxMulticastMacAddr(groupMac) == kErrorEdrvBufNotExisting);
    assert(edrv_setRxMulticastMacAddr(NULL) == kErrorEdrvInvalidParam);
    assert(edrv_setRxMulticastMacAddr(ownMac) == kErrorEdrvInvalidParam);
    for (i = 0; i < 8; i++) { extraGroup[5] = (UINT8)(0x10 + i); assert(edrv_setRxMulticastMacAddr(extraGroup) == kErrorOk); }
    extraGroup[5] = 0x20; assert(edrv_setRxMulticastMacAddr(extraGroup) == kErrorEdrvNoFreeBufEntry);
    extraGroup[5] = 0x10; assert(edrv_clearRxMulticastMacAddr(extraGroup) == kErrorOk);
    extraGroup[5] = 0x20; assert(edrv_setRxMulticastMacAddr(extraGroup) == kErrorOk);
    memset(filters, 0, sizeof(filters)); filters[0].fEnable = TRUE;
    filters[0].aFilterValue[12] = 0x88; filters[0].aFilterValue[13] = 0xab;
    filters[0].aFilterMask[12] = filters[0].aFilterMask[13] = 255;
    assert(edrv_changeRxFilter(filters, 2, 2, 0) == kErrorOk);
    for (i = 2; i < 8; i++) rxFrame(i, ownMac, 64);
    m7_edrv_test_dma.rxbuf[2][13] = 0xb5;
    assert(m7_edrv_poll(2) == kErrorOk && rxCallbacks == 2);
    assert(m7_edrv_test_dma.rx[4].d[3] == (M7_ETH2_FIRST_LAST | 64U)); /* budget respected */
    filters[0].fEnable = FALSE;
    assert(edrv_changeRxFilter(filters, 2, 0, EDRV_FILTER_CHANGE_STATE) == kErrorOk);
    assert(m7_edrv_poll(8) == kErrorOk && rxCallbacks == 2);
    assert(edrv_changeRxFilter(filters, 2, 0, EDRV_FILTER_CHANGE_AUTO_RESPONSE) == kErrorInvalidOperation);
    assert(edrv_changeRxFilter(NULL, 1, 1, 0) == kErrorEdrvInvalidParam);
    assert(edrv_changeRxFilter(filters, 33, 33, 0) == kErrorEdrvInvalidParam);
    assert(edrv_changeRxFilter(NULL, 0, 0, 0) == kErrorOk);
    rxFrame(0, ownMac, 64); assert(m7_edrv_poll(1) == kErrorOk && rxCallbacks == 2);
    filters[0].fEnable = TRUE; filters[0].aFilterValue[13] = 0xb5;
    assert(edrv_changeRxFilter(filters, 2, 2, 0) == kErrorOk);
    filters[0].aFilterValue[13] = 0xab;
    assert(edrv_changeRxFilter(filters, 2, 0, EDRV_FILTER_CHANGE_VALUE) == kErrorOk);
    rxFrame(1, broadcast, 64); assert(m7_edrv_poll(1) == kErrorOk && rxCallbacks == 3);
    rxFrame(2, ownMac, 64); m7_edrv_test_dma.rxbuf[2][5] = 3; /* foreign unicast */
    assert(m7_edrv_poll(1) == kErrorOk && rxCallbacks == 3);
    filters[0].aFilterMask[13] = 0;
    assert(edrv_changeRxFilter(filters, 2, 0, EDRV_FILTER_CHANGE_MASK) == kErrorOk);
    rxFrame(3, ownMac, 64); m7_edrv_test_dma.rxbuf[3][13] = 0xb5;
    assert(m7_edrv_poll(1) == kErrorOk && rxCallbacks == 4);
    assert(edrv_exit() == kErrorOk);
}
static void test_rx_invalid(void)
{
    UINT i;
    begin(); assert(m7_edrv_poll(0) == kErrorEdrvInvalidParam);
    assert(m7_edrv_poll(9) == kErrorEdrvInvalidParam);
    rxFrame(0, ownMac, 63); rxFrame(1, ownMac, 1519);
    rxFrame(2, ownMac, 64); m7_edrv_test_dma.rx[2].d[3] |= M7_ETH2_ERROR;
    rxFrame(3, ownMac, 64); m7_edrv_test_dma.rx[3].d[3] &= ~(1U << 29);
    rxFrame(4, ownMac, 64); m7_edrv_test_dma.rx[4].d[3] |= 1U << 30;
    rxFrame(5, ownMac, 1518); expectedRxSize = 1514;
    assert(m7_edrv_poll(8) == kErrorOk && rxCallbacks == 1 && m7_edrv_stats()->rxErrors == 5);
    for (i = 0; i < 6; i++) assert(m7_edrv_test_dma.rx[i].d[3] & M7_ETH2_OWN);
    assert(edrv_exit() == kErrorOk);
}
static void test_rx_deferred(void)
{
    begin(); rxFrame(0, ownMac, 64); deferRx = TRUE;
    assert(m7_edrv_poll(8) == kErrorEdrvInvalidRxBuf && rxCallbacks == 1);
    assert(!(m7_edrv_test_dma.rx[0].d[3] & M7_ETH2_OWN));
    assert(m7_edrv_stats()->rxDeferredRejected == 1 && m7_edrv_stats()->rxDelivered == 0);
    assert(m7_edrv_poll(1) == kErrorInvalidOperation);
    assert(edrv_exit() == kErrorOk);
}
int main(int argc, char** argv)
{
    assert(argc == 2);
#define RUN(name) if (!strcmp(argv[1], #name)) { test_##name(); puts("PASS " #name); return 0; }
    RUN(init) RUN(buffers) RUN(tx_wrap) RUN(tx_callback) RUN(tx_error) RUN(stop)
    RUN(rx_filters) RUN(rx_invalid) RUN(rx_deferred)
    return 1;
}
