/* Actual RTOS headers/config, compile only. NO replacement TCB definition. */
#include <stddef.h>
#include "prt_task_external.h"
const U32 m7_tcb_layout[] __attribute__((section(".m7_tcb_layout"),used))={
    sizeof(struct TagTskCb),offsetof(struct TagTskCb,stackSize),offsetof(struct TagTskCb,taskPid),
    offsetof(struct TagTskCb,topOfStack),offsetof(struct TagTskCb,taskEntry),offsetof(struct TagTskCb,args)};
