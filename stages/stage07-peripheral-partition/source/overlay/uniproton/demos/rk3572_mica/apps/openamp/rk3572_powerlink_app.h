/* P3b RTOS boundary: pure types, no upstream/RTOS macro collisions. */
#ifndef RK3572_POWERLINK_APP_H
#define RK3572_POWERLINK_APP_H
#include <stddef.h>
#include <stdint.h>
#include "m7_mn.h"
typedef struct {
    uint32_t ready, pending, running, submitted, completed, command;
    uint32_t result, runtimeError, owner;
    M7MnStatus mn;
} M7PowerlinkSnapshot;
uint32_t Rk3572PowerlinkInit(void);
int Rk3572PowerlinkInput(const char* data, size_t length);
int Rk3572PowerlinkSnapshot(M7PowerlinkSnapshot* out);
#endif
