/* P3e explicit bounded EDRV test, NOT MN or industrial protocol traffic. */
#ifndef M7_EDRV_PROBE_H
#define M7_EDRV_PROBE_H
#include <stdint.h>
#include "m7_eth_probe.h"
#define M7_EDRV_PROBE_EACH 32U
#define M7_EDRV_PROBE_TOTAL (2U * M7_EDRV_PROBE_EACH)
typedef struct {
    uint32_t result, clean, nonce, received, submitted, completed, fcs;
    uint32_t rxErrors, txErrors, dmaFatal, dropped, leaseBefore, leaseAfter;
    M7EthHardware active, stopped;
} M7EdrvProbeResult;
enum { M7_EPROBE_OK, M7_EPROBE_CONTEXT, M7_EPROBE_INIT, M7_EPROBE_BUFFER,
       M7_EPROBE_POLL, M7_EPROBE_FRAME, M7_EPROBE_FCS, M7_EPROBE_TIMEOUT,
       M7_EPROBE_CALLBACK, M7_EPROBE_CLEANUP, M7_EPROBE_MODE };
uint32_t m7_edrv_probe(M7EdrvProbeResult* out);
#endif
