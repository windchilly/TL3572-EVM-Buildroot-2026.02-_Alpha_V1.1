/* Real probe control flow; explicit RTOS/BSP mocks, NOT hardware proof. */
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "m7_eth_probe.h"
#include "m7_plk_platform.h"
static uint32_t lease;
static unsigned acquireCalls, modeCalls, stopCalls;
static int acquire = 1, stop = 1, mode = 1, isr, irq = 1, owner, faulted, taskOk = 1;
static M7EthHardware hardware = {0x7b74,0x4412,0x2000,0x2004,0xc000,0,0,0,0,0};
int m7_plk_task_id(uint32_t* id) { *id = 3; return taskOk; }
int m7_plk_in_interrupt(void) { return isr; }
int m7_plk_irq_enabled(void) { return irq; }
int m7_plk_owner(void) { return owner; }
int m7_plk_faulted(void) { return faulted; }
uint32_t m7_eth2_hw_lease(void) { return lease; }
int m7_eth2_hw_acquire(void) { ++acquireCalls; assert(!lease); lease = acquire ? 2 : 0; return acquire; }
int m7_eth2_hw_probe_mode(M7EthHardware* out) { ++modeCalls; assert(lease == 2); *out = hardware; return mode; }
int m7_eth2_hw_probe_stop(M7EthHardware* out) {
    ++stopCalls; assert(lease == 2); *out = (M7EthHardware){0}; if (stop) lease = 0; return stop;
}
int main(int argc, char** argv)
{
    M7EthProbeResult out;
    unsigned i;
    assert(argc == 2);
    if (!strcmp(argv[1], "normal")) {
        assert(m7_eth_probe(NULL) == M7_ETH_CONTEXT);
        for (i = 0; i < 100; ++i) {
            assert(m7_eth_probe(&out) == M7_ETH_OK && out.clean && !lease);
            assert(out.configured.mac == 0xc000 && !out.stopped.mac && !out.leaseBefore && !out.leaseAfter);
        }
        assert(acquireCalls == 100 && modeCalls == 100 && stopCalls == 100);
    } else if (!strcmp(argv[1], "context")) {
        for (i = 0; i < 5; ++i) {
            isr = i == 0; irq = i != 1; taskOk = i != 2; owner = i == 3; faulted = i == 4;
            assert(m7_eth_probe(&out) == M7_ETH_CONTEXT && out.clean);
        }
        assert(!acquireCalls && !modeCalls && !stopCalls);
    } else if (!strcmp(argv[1], "busy")) {
        for (lease = 1; lease <= 2; ++lease) assert(m7_eth_probe(&out) == M7_ETH_BUSY && !out.clean);
        assert(!acquireCalls && !stopCalls);
    } else if (!strcmp(argv[1], "acquire")) {
        acquire = 0; assert(m7_eth_probe(&out) == M7_ETH_ACQUIRE && out.clean && !stopCalls);
    } else if (!strcmp(argv[1], "unsafe_acquire")) {
        acquire = -1; assert(m7_eth_probe(&out) == M7_ETH_CLEANUP && !out.clean && lease == 2 && !stopCalls);
    } else if (!strcmp(argv[1], "unsafe_stop")) {
        stop = 0; assert(m7_eth_probe(&out) == M7_ETH_CLEANUP && !out.clean && lease == 2 && stopCalls == 1);
    } else if (!strcmp(argv[1], "mode")) {
        mode = 0; assert(m7_eth_probe(&out) == M7_ETH_MODE && out.clean && stopCalls == 1);
    } else if (!strcmp(argv[1], "readbacks")) {
        for (i = 0; i < 13; ++i) {
            hardware = (M7EthHardware){0x7b74,0x4412,0x2000,0x2004,0xc000,0,0,0,0,0};
            switch (i) {
                case 0: hardware.phyHigh ^= 1; break; case 1: hardware.phyLow ^= 1; break;
                case 2: hardware.bmcr |= 0x1000; break; case 3: hardware.bmcr |= 0x100; break;
                case 4: hardware.bmcr ^= 0x2000; break; case 5: hardware.bmsr &= ~4U; break;
                case 6: hardware.bmsr &= ~0x2000U; break; case 7: hardware.mac |= 0x2000; break;
                case 8: hardware.tx |= 1; break; case 9: hardware.rx |= 1; break;
                case 10: hardware.dma |= 1; break; case 11: hardware.macIrq = 1; break;
                case 12: hardware.dmaIrq = 1; break;
            }
            assert(m7_eth_probe(&out) == M7_ETH_MODE && out.clean && !lease);
        }
        assert(stopCalls == 13);
    } else assert(0);
    puts("P3d no-frame probe native PASS"); return 0;
}
