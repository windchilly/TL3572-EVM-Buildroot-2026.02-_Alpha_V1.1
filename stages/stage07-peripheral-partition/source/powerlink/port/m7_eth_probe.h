/* P3d explicit no-DMA/no-frame PHY/MAC diagnostic, not MN startup. */
#ifndef M7_ETH_PROBE_H
#define M7_ETH_PROBE_H
#include <stdint.h>
typedef struct {
    uint32_t phyHigh, phyLow, bmcr, bmsr, mac, tx, rx, dma, macIrq, dmaIrq;
} M7EthHardware;
typedef struct {
    M7EthHardware configured, stopped;
    uint32_t result, clean, leaseBefore, leaseAfter;
} M7EthProbeResult;
enum { M7_ETH_OK, M7_ETH_CONTEXT, M7_ETH_BUSY, M7_ETH_ACQUIRE,
       M7_ETH_MODE, M7_ETH_CLEANUP };
/* These BSP calls are only used by the explicitly gated candidate. */
uint32_t m7_eth2_hw_lease(void);
int m7_eth2_hw_probe_mode(M7EthHardware* out);
int m7_eth2_hw_probe_stop(M7EthHardware* out);
uint32_t m7_eth_probe(M7EthProbeResult* out);
#endif
