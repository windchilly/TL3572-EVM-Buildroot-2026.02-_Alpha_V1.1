/* No descriptors, EDRV, timer, MN, frame send or receive processing here. */
#include "m7_eth_probe.h"
#include "m7_eth2_hw.h"
#include "m7_plk_platform.h"
#include "m7_plk_rtos.h"

uint32_t m7_eth_probe(M7EthProbeResult* out)
{
    uint32_t task, result = M7_ETH_OK;
    int acquired;
    if (!out) return M7_ETH_CONTEXT;
    *out = (M7EthProbeResult){0};
    out->leaseBefore = out->leaseAfter = m7_eth2_hw_lease();
    out->clean = !out->leaseBefore;
    if (m7_plk_in_interrupt() || !m7_plk_irq_enabled() ||
        !m7_plk_task_id(&task) || m7_plk_owner() || m7_plk_faulted())
        return out->result = M7_ETH_CONTEXT;
    if (out->leaseBefore) return out->result = M7_ETH_BUSY;
    out->clean = 0;
    acquired = m7_eth2_hw_acquire();
    if (acquired != 1) {
        out->leaseAfter = m7_eth2_hw_lease();
        out->clean = acquired == 0 && !out->leaseAfter;
        return out->result = acquired < 0 ? M7_ETH_CLEANUP : M7_ETH_ACQUIRE;
    }
    if (!m7_eth2_hw_probe_mode(&out->configured) ||
        out->configured.phyHigh != 0x7b74U || out->configured.phyLow != 0x4412U ||
        (out->configured.bmcr & 0xffc0U) != 0x2000U ||
        (out->configured.bmsr & 0x2004U) != 0x2004U ||
        (out->configured.mac & 0x0030e003U) != 0x0000c000U ||
        (out->configured.tx & 1U) || (out->configured.rx & 1U) ||
        (out->configured.dma & 1U) || out->configured.macIrq || out->configured.dmaIrq)
        result = M7_ETH_MODE;
    /* One stop attempt only; unsafe stop retains lease and host power hold. */
    if (!m7_eth2_hw_probe_stop(&out->stopped)) result = M7_ETH_CLEANUP;
    else out->clean = 1;
    out->leaseAfter = m7_eth2_hw_lease();
    if (out->leaseAfter) { out->clean = 0; result = M7_ETH_CLEANUP; }
    return out->result = result;
}
