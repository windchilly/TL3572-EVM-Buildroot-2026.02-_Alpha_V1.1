/* Process-private resources for the fixed single-process Linux software CN. */
#ifndef M7_CN_PRIVATE_H
#define M7_CN_PRIVATE_H
#include <common/oplkinc.h>
#include <oplk/event.h>
#include <stdint.h>
#include <semaphore.h>
tOplkError m7_cn_event_sems_init(void);
tOplkError m7_cn_event_sems_attach(void);
sem_t* m7_cn_event_sem(int kernel);
tOplkError m7_cn_event_sems_detach(void);
tOplkError m7_cn_event_sems_exit(void);
unsigned m7_cn_private_buffers(void);
tOplkError m7_cn_timers_fault(void);
BOOL m7_cn_timer_event_current(const tEvent* event);
typedef struct { unsigned allocated, active; uint64_t callbacks, skipped; tOplkError fault; } M7CnTimerStats;
void m7_cn_timer_stats(int highres,M7CnTimerStats* stats);
#endif
