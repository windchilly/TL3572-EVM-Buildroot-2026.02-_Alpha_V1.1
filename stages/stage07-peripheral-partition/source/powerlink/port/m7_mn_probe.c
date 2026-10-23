/* P3f: execute the REAL full MN stack lifecycle, permanently GsOff.
 * No reset/start/switch-off/API frame sends. Prepare DOES acquire ETH/CNTP.
 * Partial init or any failed proof is terminal: no automatic cleanup retry.
 */
#include <user/nmtu.h>
#include "m7_mn_probe.h"
#include "m7_edrv.h"
#include "m7_eth2_hw.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"
static int entered;
static void hardware(M7EthHardware* out)
{
    out->mac = m7_eth2_hw_read(0); out->tx = m7_eth2_hw_read(0x1104);
    out->rx = m7_eth2_hw_read(0x1108); out->dma = m7_eth2_hw_read(0x1000);
    out->macIrq = m7_eth2_hw_read(0xb4); out->dmaIrq = m7_eth2_hw_read(0x1134);
}
static int quietTimer(const M7TimerHardware* before, const M7TimerHardware* after)
{
    return !(after->cntp & 1U) && !((after->enabled | after->pending | after->active) & (1U << 30)) &&
        !((before->enabled ^ after->enabled) & (1U << 27)) && !((before->cntv ^ after->cntv) & 3U) &&
        before->priority27 == after->priority27 && before->priority30 == after->priority30 &&
        before->typer == after->typer && before->cpuControl == after->cpuControl &&
        !((before->group ^ after->group) & (1U << 30)) && !((before->config ^ after->config) & (1U << 29));
}
static int passive(M7MnProbeResult* out)
{
    const tM7EdrvStats* stats = m7_edrv_stats();
    M7PlkTimerStats timer = {0};
    unsigned i, word;
#ifdef M7_EDRV_NATIVE_TEST
    extern struct M7Eth2Dma m7_edrv_test_dma;
    struct M7Eth2Dma* dma = &m7_edrv_test_dma;
#else
    struct M7Eth2Dma* dma = (struct M7Eth2Dma*)M7_ETH2_DMA_ADDRESS;
#endif
    /* Completion=0 alone cannot prove no submission. This fixed backend
     * starts all TX words at zero and leaves metadata after consumption. */
    out->txDescriptors = 0; m7_eth2_dma_barrier();
    for (i = 0; i < M7_ETH2_RING; ++i) for (word = 0; word < 4; ++word)
        if (dma->tx[i].d[word]) ++out->txDescriptors;
    m7_hrestimer_stats(&timer);
    out->rx = stats->rxDelivered; out->tx = stats->txCompleted; out->dropped = stats->rxDropped;
    out->rxErrors = stats->rxErrors; out->txErrors = stats->txErrors; out->fatal = stats->dmaFatal;
    out->timerIrqs = timer.interrupts; out->timerCallbacks = timer.callbacks;
    if (m7_mn_status(&out->final)) return 0;
    return out->final.state == M7_MN_PREPARED && out->final.nmtState == kNmtGsOff &&
        nmtu_getNmtState() == kNmtGsOff && out->final.events == out->initialized.events &&
        !out->rx && !out->tx && !out->txDescriptors && !out->rxErrors && !out->txErrors && !out->fatal &&
        !stats->rxDeferredRejected && timer.leased && !timer.interrupts && !timer.callbacks;
}
uint32_t m7_mn_probe(M7MnProbeResult* out)
{
    uint32_t task, result = M7_MPROBE_OK;
    uint64_t start;
    if (!out) return M7_MPROBE_CONTEXT;
    *out = (M7MnProbeResult){0};
    out->leaseBefore = out->leaseAfter = m7_eth2_hw_lease();
    out->timerBefore = out->timerAfter = (uint32_t)m7_hrestimer_active();
    if (entered || out->leaseBefore || out->timerBefore || m7_plk_owner() || m7_plk_faulted() ||
        m7_plk_in_interrupt() || !m7_plk_irq_enabled() || !m7_plk_task_id(&task) ||
        !m7_timer_diag_snapshot(&out->timerInitial)) return out->result = M7_MPROBE_CONTEXT;
    entered = 1; out->stage = 1;
    out->stackError = m7_mn_initialize();
    if (out->stackError) { result = M7_MPROBE_INIT; goto unsafe; }
    if (m7_mn_status(&out->initialized) || out->initialized.state != M7_MN_IDLE) {
        result = M7_MPROBE_STATE; goto unsafe;
    }
    out->stage = 2; out->stackError = m7_mn_prepare();
    if (out->stackError) { result = M7_MPROBE_PREPARE; goto unsafe; }
    if (m7_mn_status(&out->prepared)) { result = M7_MPROBE_STATE; goto unsafe; }
    hardware(&out->active);
    if ((out->active.mac & 0x0030e003U) != 0xc003U || !(out->active.tx & 1U) ||
        !(out->active.rx & 1U) || (out->active.dma & 1U) || out->active.macIrq || out->active.dmaIrq ||
        !passive(out)) { result = M7_MPROBE_STATE; goto unsafe; }
    start = m7_plk_milliseconds(); out->stage = 3;
    while (out->loops < M7_MN_PROBE_LOOPS) {
        out->stackError = m7_mn_process();
        if (out->stackError) { result = M7_MPROBE_PROCESS; goto unsafe; }
        ++out->loops;
        if (!passive(out) || out->final.processes - out->initialized.processes != out->loops) {
            result = M7_MPROBE_STATE; goto unsafe;
        }
        if (m7_plk_milliseconds() - start >= 2000U) { result = M7_MPROBE_PROCESS; goto unsafe; }
        if (!m7_plk_sleep(1U)) { result = M7_MPROBE_SLEEP; goto unsafe; }
    }
    out->stage = 4; out->stackError = m7_mn_stop(); /* Never retry a failed stop. */
    if (out->stackError) { result = M7_MPROBE_STOP; goto unsafe; }
    hardware(&out->stopped);
    out->leaseAfter = m7_eth2_hw_lease(); out->timerAfter = (uint32_t)m7_hrestimer_active();
    if (out->leaseAfter || out->timerAfter || (out->stopped.mac & 3U) || (out->stopped.tx & 1U) ||
        (out->stopped.rx & 1U) || (out->stopped.dma & 1U) || out->stopped.macIrq || out->stopped.dmaIrq ||
        !m7_timer_diag_snapshot(&out->timerFinal) || !quietTimer(&out->timerInitial, &out->timerFinal)) {
        result = M7_MPROBE_CLEANUP; goto unsafe;
    }
    out->stage = 5; out->stackError = m7_mn_exit();
    if (out->stackError) { result = M7_MPROBE_EXIT; goto unsafe; }
    if (m7_mn_status(&out->final) || out->final.state != M7_MN_COLD ||
        m7_plk_owner() || m7_plk_faulted() || m7_eth2_hw_lease() || m7_hrestimer_active()) {
        result = M7_MPROBE_CLEANUP; goto unsafe;
    }
    out->clean = 1; entered = 0; return out->result = M7_MPROBE_OK;
unsafe:
    out->leaseAfter = m7_eth2_hw_lease(); out->timerAfter = (uint32_t)m7_hrestimer_active();
    (void)m7_mn_status(&out->final); m7_plk_fault(); return out->result = result;
}
