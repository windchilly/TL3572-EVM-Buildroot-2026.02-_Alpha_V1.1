/* P3g: explicit, bounded REAL NMT reset then immediate SwitchOff at MN
 * NotActive. No CN plan, StartNode, continuous loop or arbitrary NMT API.
 * This is NOT read-only or a no-wire-traffic authorization. Never deploy or
 * call without a separately approved ETH2/CNTP isolated hardware window.
 * Any failed proof retains resources/terminal fault, without cleanup retry.
 */
#include <oplk/oplk.h>
#include <user/nmtu.h>
#include "m7_nmt_probe.h"
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
static int state(M7MnProbeResult* out)
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
    m7_eth2_dma_barrier(); out->txDescriptors = 0;
    for (i = 0; i < M7_ETH2_RING; ++i) for (word = 0; word < 4; ++word)
        if (dma->tx[i].d[word]) ++out->txDescriptors;
    m7_hrestimer_stats(&timer);
    out->rx = stats->rxDelivered; out->tx = stats->txCompleted; out->dropped = stats->rxDropped;
    out->rxErrors = stats->rxErrors; out->txErrors = stats->txErrors; out->fatal = stats->dmaFatal;
    out->timerIrqs = timer.interrupts; out->timerCallbacks = timer.callbacks;
    if (m7_mn_status(&out->final)) return 0;
    return out->final.state == M7_MN_PREPARED && out->final.nmtState == (uint32_t)nmtu_getNmtState() &&
        !out->rx && !out->tx && !out->txDescriptors && !out->rxErrors && !out->txErrors && !out->fatal &&
        !stats->rxDeferredRejected && timer.leased && !timer.interrupts && !timer.callbacks;
}
static int resetState(uint32_t nmt)
{
    return nmt == kNmtGsOff || nmt == kNmtGsInitialising || nmt == kNmtGsResetApplication ||
        nmt == kNmtGsResetCommunication || nmt == kNmtGsResetConfiguration || nmt == kNmtMsNotActive;
}
uint32_t m7_nmt_probe(M7NmtProbeResult* out)
{
    uint32_t task, result;
    uint64_t start;
    M7MnProbeResult* life;
    if (!out) return M7_MPROBE_CONTEXT;
    *out = (M7NmtProbeResult){0}; life = &out->lifecycle;
    life->leaseBefore = life->leaseAfter = m7_eth2_hw_lease();
    life->timerBefore = life->timerAfter = (uint32_t)m7_hrestimer_active();
    if (entered || life->leaseBefore || life->timerBefore || m7_plk_owner() || m7_plk_faulted() ||
        m7_plk_in_interrupt() || !m7_plk_irq_enabled() || !m7_plk_task_id(&task) ||
        !m7_timer_diag_snapshot(&life->timerInitial)) return life->result = M7_MPROBE_CONTEXT;
    entered = 1; life->stage = 1;
    life->stackError = m7_mn_initialize();
    if (life->stackError) { result = M7_MPROBE_INIT; goto unsafe; }
    if (m7_mn_status(&life->initialized) || life->initialized.state != M7_MN_IDLE) {
        result = M7_NPROBE_STATE; goto unsafe;
    }
    life->stage = 2; life->stackError = m7_mn_prepare();
    if (life->stackError) { result = M7_MPROBE_PREPARE; goto unsafe; }
    if (m7_mn_status(&life->prepared)) { result = M7_NPROBE_STATE; goto unsafe; }
    hardware(&life->active);
    if ((life->active.mac & 0x0030e003U) != 0xc003U || !(life->active.tx & 1U) ||
        !(life->active.rx & 1U) || (life->active.dma & 1U) || life->active.macIrq || life->active.dmaIrq ||
        !state(life) || life->final.nmtState != kNmtGsOff) { result = M7_NPROBE_STATE; goto unsafe; }
    life->stage = 3;
    life->stackError = oplk_execNmtCommand(kNmtEventSwReset);
    if (life->stackError) { result = M7_NPROBE_COMMAND; goto unsafe; }
    out->resetSubmitted = 1; start = m7_plk_milliseconds();
    while (out->resetLoops < M7_NMT_PROBE_LIMIT) {
        life->stackError = m7_mn_process(); ++out->resetLoops; ++life->loops;
        if (life->stackError) { result = M7_MPROBE_PROCESS; goto unsafe; }
        if (!state(life) || !resetState(life->final.nmtState)) { result = M7_NPROBE_STATE; goto unsafe; }
        if (m7_plk_milliseconds() - start >= 1000U) { result = M7_NPROBE_TIMEOUT; goto unsafe; }
        if (life->final.nmtState == kNmtMsNotActive) { out->reached = kNmtMsNotActive; break; }
        if (!m7_plk_sleep(1U)) { result = M7_MPROBE_SLEEP; goto unsafe; }
    }
    if (!out->reached) { result = M7_NPROBE_TIMEOUT; goto unsafe; }
    life->stage = 4;
    life->stackError = oplk_execNmtCommand(kNmtEventSwitchOff);
    if (life->stackError) { result = M7_NPROBE_COMMAND; goto unsafe; }
    out->offSubmitted = 1; start = m7_plk_milliseconds();
    while (out->offLoops < M7_NMT_PROBE_LIMIT) {
        life->stackError = m7_mn_process(); ++out->offLoops; ++life->loops;
        if (life->stackError) { result = M7_MPROBE_PROCESS; goto unsafe; }
        if (!state(life) || (life->final.nmtState != kNmtMsNotActive && life->final.nmtState != kNmtGsOff)) {
            result = M7_NPROBE_STATE; goto unsafe;
        }
        if (m7_plk_milliseconds() - start >= 1000U) { result = M7_NPROBE_TIMEOUT; goto unsafe; }
        if (life->final.nmtState == kNmtGsOff) break;
        if (!m7_plk_sleep(1U)) { result = M7_MPROBE_SLEEP; goto unsafe; }
    }
    if (life->final.nmtState != kNmtGsOff) { result = M7_NPROBE_TIMEOUT; goto unsafe; }
    if (life->final.events <= life->initialized.events ||
        life->final.processes - life->initialized.processes != life->loops) { result = M7_NPROBE_STATE; goto unsafe; }
    life->stage = 5; life->stackError = m7_mn_stop(); /* Exactly once, only after actual GsOff. */
    if (life->stackError) { result = M7_MPROBE_STOP; goto unsafe; }
    hardware(&life->stopped);
    life->leaseAfter = m7_eth2_hw_lease(); life->timerAfter = (uint32_t)m7_hrestimer_active();
    if (life->leaseAfter || life->timerAfter || (life->stopped.mac & 3U) || (life->stopped.tx & 1U) ||
        (life->stopped.rx & 1U) || (life->stopped.dma & 1U) || life->stopped.macIrq || life->stopped.dmaIrq ||
        !m7_timer_diag_snapshot(&life->timerFinal) || !quietTimer(&life->timerInitial, &life->timerFinal)) {
        result = M7_MPROBE_CLEANUP; goto unsafe;
    }
    life->stage = 6; life->stackError = m7_mn_exit();
    if (life->stackError) { result = M7_MPROBE_EXIT; goto unsafe; }
    if (m7_mn_status(&life->final) || life->final.state != M7_MN_COLD ||
        m7_plk_owner() || m7_plk_faulted() || m7_eth2_hw_lease() || m7_hrestimer_active()) {
        result = M7_MPROBE_CLEANUP; goto unsafe;
    }
    life->clean = 1; entered = 0; return life->result = M7_MPROBE_OK;
unsafe:
    life->leaseAfter = m7_eth2_hw_lease(); life->timerAfter = (uint32_t)m7_hrestimer_active();
    (void)m7_mn_status(&life->final); m7_plk_fault(); return life->result = result;
}
