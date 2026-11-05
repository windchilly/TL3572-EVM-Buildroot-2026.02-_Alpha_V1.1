/* Linux software-CN only. Not an execution grant or a realtime guarantee. */
#ifndef M7_CN_LIFECYCLE_H
#define M7_CN_LIFECYCLE_H
#include <common/oplkinc.h>
#include <pthread.h>
enum M7CnThread { M7_CN_EVENTK, M7_CN_HRES, M7_CN_EVENTU, M7_CN_TIMERU, M7_CN_THREADS };
typedef struct {
    unsigned begun, create_attempted, initialized, stop_attempted, quiet;
    unsigned release_started, kernel_release_started, released, environment_exit_attempted;
    unsigned created, joined;
    tOplkError first_error;
} M7CnLifecycleStats;
tOplkError m7_cn_lifecycle_begin(void);
tOplkError m7_cn_create_begin(void);
tOplkError m7_cn_init_result(tOplkError error);
tOplkError m7_cn_fail(tOplkError error);
int m7_cn_thread_create(enum M7CnThread slot, pthread_t* thread, void* (*entry)(void*), void* argument);
int m7_cn_stopping(void);
tOplkError m7_cn_quiesce(void);
tOplkError m7_cn_release_begin(void);
tOplkError m7_cn_kernel_release_begin(void);
tOplkError m7_cn_release_finish(void);
tOplkError m7_cn_environment_exit_begin(void);
int m7_cn_can_release(void);
int m7_cn_released(void);
void m7_cn_lifecycle_stats(M7CnLifecycleStats* stats);
#endif
