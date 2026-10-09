#include "prt_typedef.h"
typedef U32 TskHandle;
typedef void (*TskEntryFunc)(uintptr_t, uintptr_t, uintptr_t, uintptr_t);
struct TskInitParam {
    uintptr_t stackAddr;
    U32 stackSize, taskPrio;
    TskEntryFunc taskEntry;
    const char *name;
    uintptr_t args[4];
};
U32 PRT_TaskCreate(TskHandle *task, struct TskInitParam *param);
U32 PRT_TaskResume(TskHandle task);
U32 PRT_TaskDelete(TskHandle task);
U32 PRT_TaskDelay(U32 ticks);
