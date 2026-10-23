/* Explicit P3e only: real EDRV, one owner, 64 bounded request/reply frames.
 * Target environment only: NO oplk_initialize/create/NMT/timer acquisition.
 * Static TX metadata survives every failed stop; no freeing live DMA storage.
 */
#include <common/target.h>
#include "m7_edrv.h"
#include "m7_eth2_hw.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
#include "m7_edrv_probe.h"
#include "m7_edrv_probe_codec.h"
extern int PRT_Printf(const char*, ...);
static const uint8_t ownMac[6] = {2,0x55,0x50,0x32,0,2};
static struct {
    M7EdrvProbeResult result;
    tEdrvTxBuffer tx;
    uint8_t pending[1514], peer[6];
    uint32_t pendingLength, inFlight, error;
    int entered;
} probe;

static void txComplete(tEdrvTxBuffer* tx)
{
    if (!m7_plk_ready() || !m7_plk_irq_enabled() || tx != &probe.tx || !probe.inFlight)
        probe.error = M7_EPROBE_CALLBACK;
    else { probe.inFlight = 0; ++probe.result.completed; }
}
static tEdrvReleaseRxBuffer rxFrame(tEdrvRxBuffer* rx)
{
    uint32_t i, length;
    const uint8_t* packet;
    struct M7Eth2Dma* dma;
#ifdef M7_EDRV_NATIVE_TEST
    extern struct M7Eth2Dma m7_edrv_test_dma;
    dma = &m7_edrv_test_dma;
#else
    dma = (struct M7Eth2Dma*)M7_ETH2_DMA_ADDRESS;
#endif
    if (!m7_plk_ready() || !m7_plk_irq_enabled() || !rx || !rx->pBuffer ||
        rx->bufferInFrame != kEdrvBufferLastInFrame) { probe.error = M7_EPROBE_CALLBACK; goto done; }
    length = rx->rxFrameSize; packet = rx->pBuffer;
    for (i = 0; i < M7_ETH2_RING; ++i) if (packet == dma->rxbuf[i]) break;
    /* This is our fixed backend's DMA buffer, NOT a generic EDRV/FCS promise. */
    if (i == M7_ETH2_RING || length > M7_ETH2_BUFFER_SIZE - 4U ||
        !M7ProbeValid(packet, length, probe.result.nonce, probe.result.received, 1) ||
        memcmp(packet, ownMac, 6) || (packet[6] & 1U) ||
        !memcmp(packet + 6, (const uint8_t[6]){0}, 6) ||
        (probe.result.received && memcmp(packet + 6, probe.peer, 6)) || probe.pendingLength) {
        probe.error = M7_EPROBE_FRAME; goto done;
    }
    if (EthCrc(packet, length) != ((uint32_t)packet[length] | ((uint32_t)packet[length+1] << 8) |
        ((uint32_t)packet[length+2] << 16) | ((uint32_t)packet[length+3] << 24))) {
        probe.error = M7_EPROBE_FCS; goto done;
    }
    memcpy(probe.peer, packet + 6, 6); memcpy(probe.pending, packet, length);
    probe.pendingLength = length; ++probe.result.received; ++probe.result.fcs;
done:
    return kEdrvReleaseRxBufferImmediately;
}
static void hardware(M7EthHardware* out)
{
    out->mac = m7_eth2_hw_read(0U); out->tx = m7_eth2_hw_read(0x1104U);
    out->rx = m7_eth2_hw_read(0x1108U); out->dma = m7_eth2_hw_read(0x1000U);
    out->macIrq = m7_eth2_hw_read(0xb4U); out->dmaIrq = m7_eth2_hw_read(0x1134U);
}
uint32_t m7_edrv_probe(M7EdrvProbeResult* out)
{
    tEdrvInitParam init = {0}; tEdrvFilter filter = {0};
    const tM7EdrvStats* stats;
    uint64_t start; uint32_t spins = 0, task, result = M7_EPROBE_OK;
    if (!out) return M7_EPROBE_CONTEXT;
    *out = (M7EdrvProbeResult){0}; out->leaseBefore = out->leaseAfter = m7_eth2_hw_lease();
    if (probe.entered || out->leaseBefore || m7_plk_owner() || m7_plk_faulted() ||
        m7_hrestimer_active() || m7_plk_in_interrupt() || !m7_plk_irq_enabled() || !m7_plk_task_id(&task))
        return out->result = M7_EPROBE_CONTEXT;
    memset(&probe, 0, sizeof(probe)); probe.entered = 1;
    if (target_init() != kErrorOk) return out->result = M7_EPROBE_CONTEXT;
    memcpy(init.aMacAddr, ownMac, 6); init.pfnRxHandler = rxFrame;
    if (edrv_init(&init) != kErrorOk) {
        /* init already attempted any required rollback; NEVER retry its stop. */
        if (m7_eth2_hw_lease()) goto unsafe;
        result = M7_EPROBE_INIT; goto target_cleanup;
    }
    hardware(&probe.result.active);
    if ((probe.result.active.mac & 0x0030e003U) != 0xc003U ||
        !(probe.result.active.tx & 1U) || !(probe.result.active.rx & 1U) ||
        (probe.result.active.dma & 1U) || probe.result.active.macIrq || probe.result.active.dmaIrq) {
        result = M7_EPROBE_MODE; goto stop;
    }
    probe.result.nonce = (uint32_t)m7_plk_timer_now();
    memcpy(filter.aFilterValue, ownMac, 6); memset(filter.aFilterMask, 255, 6);
    filter.aFilterValue[12] = 0x88; filter.aFilterValue[13] = 0xb5;
    filter.aFilterMask[12] = filter.aFilterMask[13] = 255;
    memcpy(filter.aFilterValue + 14, "M7EDRV01", 8); memset(filter.aFilterMask + 14, 255, 8);
    filter.fEnable = TRUE;
    if (edrv_changeRxFilter(&filter, 1, 1, 0) != kErrorOk) { result = M7_EPROBE_INIT; goto stop; }
    probe.tx.maxBufferSize = 1514; probe.tx.pfnTxHandler = txComplete;
    if (edrv_allocTxBuffer(&probe.tx) != kErrorOk) { result = M7_EPROBE_BUFFER; goto stop; }
    PRT_Printf("[plk-edrv-probe] READY nonce=0x%x each=32 profiles=64/1514; EDRV ONLY, no MN\n", probe.result.nonce);
    start = m7_plk_milliseconds();
    while (probe.result.completed < M7_EDRV_PROBE_TOTAL) {
        if (m7_edrv_poll(8) != kErrorOk) { result = M7_EPROBE_POLL; break; }
        if (probe.error) { result = probe.error; break; }
        if (probe.pendingLength && !probe.inFlight) {
            uint32_t length = probe.pendingLength;
            memcpy(probe.tx.pBuffer, probe.pending, length);
            memcpy(probe.tx.pBuffer, probe.peer, 6); memcpy(probe.tx.pBuffer + 6, ownMac, 6);
            EthPut32(probe.tx.pBuffer + 26, 2);
            EthPut32(probe.tx.pBuffer + length - 4U, EthCrc(probe.tx.pBuffer + 14, length - 18U));
            probe.tx.txFrameSize = length; probe.inFlight = 1;
            if (edrv_sendTxBuffer(&probe.tx) != kErrorOk) { result = M7_EPROBE_BUFFER; break; }
            probe.pendingLength = 0; ++probe.result.submitted;
        }
        if (m7_plk_milliseconds() - start >= 20000U || ++spins >= 40000U) { result = M7_EPROBE_TIMEOUT; break; }
        if (!m7_plk_sleep(1) || !m7_plk_ready()) { result = M7_EPROBE_CONTEXT; break; }
    }
    stats = m7_edrv_stats(); probe.result.rxErrors = stats->rxErrors;
    probe.result.txErrors = stats->txErrors; probe.result.dmaFatal = stats->dmaFatal;
    probe.result.dropped = stats->rxDropped;
    if (!result && (probe.result.received != M7_EDRV_PROBE_TOTAL || probe.result.fcs != M7_EDRV_PROBE_TOTAL ||
        probe.result.submitted != M7_EDRV_PROBE_TOTAL || stats->rxDelivered != M7_EDRV_PROBE_TOTAL ||
        stats->txCompleted != M7_EDRV_PROBE_TOTAL || stats->rxErrors || stats->txErrors || stats->dmaFatal || stats->rxDeferredRejected))
        result = M7_EPROBE_CALLBACK;
stop:
    if (edrv_exit() != kErrorOk) goto unsafe; /* Exactly one explicit stop. */
    hardware(&probe.result.stopped);
    if ((probe.result.stopped.mac & 3U) || (probe.result.stopped.tx & 1U) ||
        (probe.result.stopped.rx & 1U) || (probe.result.stopped.dma & 1U) ||
        probe.result.stopped.macIrq || probe.result.stopped.dmaIrq) goto unsafe;
target_cleanup:
    if (target_cleanup() != kErrorOk || m7_plk_owner() || m7_plk_faulted() || m7_eth2_hw_lease()) goto unsafe;
    probe.result.clean = 1; probe.entered = 0;
    probe.result.result = result; *out = probe.result; return result;
unsafe:
    probe.result.result = M7_EPROBE_CLEANUP; probe.result.leaseAfter = m7_eth2_hw_lease();
    m7_plk_fault(); *out = probe.result; return M7_EPROBE_CLEANUP;
}
