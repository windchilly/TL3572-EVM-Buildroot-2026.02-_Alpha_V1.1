/* P3b RTOS boundary: pure types, no upstream/RTOS macro collisions. */
#ifndef RK3572_POWERLINK_APP_H
#define RK3572_POWERLINK_APP_H
#include <stddef.h>
#include <stdint.h>
#include "m7_mn.h"
#ifdef M7_POWERLINK_TIMER_PROBE
#include "m7_timer_probe.h"
#endif
#ifdef M7_POWERLINK_ETH_PROBE
#include "m7_eth_probe.h"
#endif
typedef struct {
    uint32_t ready, pending, running, submitted, completed, command;
    uint32_t result, runtimeError, owner;
    M7MnStatus mn;
#ifdef M7_POWERLINK_TIMER_PROBE
    M7TimerProbeResult timer;
#endif
#ifdef M7_POWERLINK_ETH_PROBE
    M7EthProbeResult eth;
#endif
} M7PowerlinkSnapshot;
uint32_t Rk3572PowerlinkInit(void);
int Rk3572PowerlinkInput(const char* data, size_t length);
int Rk3572PowerlinkSnapshot(M7PowerlinkSnapshot* out);
#endif
