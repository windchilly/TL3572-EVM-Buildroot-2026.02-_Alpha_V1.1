/* P3g bounded reset-to-NotActive/SwitchOff diagnostic; never a run API. */
#ifndef M7_NMT_PROBE_H
#define M7_NMT_PROBE_H
#include "m7_mn_probe.h"
#define M7_NMT_PROBE_LIMIT 32U
typedef struct {
    M7MnProbeResult lifecycle;
    uint32_t resetSubmitted, offSubmitted, resetLoops, offLoops, reached;
} M7NmtProbeResult;
enum { M7_NPROBE_COMMAND = 10, M7_NPROBE_TIMEOUT, M7_NPROBE_STATE };
uint32_t m7_nmt_probe(M7NmtProbeResult* out);
#endif
