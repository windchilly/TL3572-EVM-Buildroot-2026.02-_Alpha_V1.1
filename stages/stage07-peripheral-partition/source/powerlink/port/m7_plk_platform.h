/* P2 hardware/RTOS boundary. All calls except timer ISR run in one UP2 task. */
#ifndef M7_PLK_PLATFORM_H
#define M7_PLK_PLATFORM_H
#include <stdint.h>
#include <stddef.h>
int m7_plk_task_id(uint32_t* id);
int m7_plk_in_interrupt(void);
int m7_plk_irq_enabled(void);
uintptr_t m7_plk_irq_save(void);
void m7_plk_irq_restore(uintptr_t state);
uint64_t m7_plk_milliseconds(void);
int m7_plk_sleep(uint32_t ms);
int m7_plk_sem_create(uint16_t* handle);
int m7_plk_sem_take(uint16_t handle);
int m7_plk_sem_give(uint16_t handle);
int m7_plk_sem_delete(uint16_t handle);
int m7_plk_cache(const void* address, size_t length, int invalidate);
int m7_plk_timer_acquire(uint32_t* frequency);
int m7_plk_timer_release(void);
uint64_t m7_plk_timer_now(void);
void m7_plk_timer_arm(uint64_t deadline);
void m7_plk_timer_mask(void);
/* BSP ISR entry; intentionally no openPOWERLINK header in the RTOS BSP. */
void m7_hrestimer_interrupt(void);
#endif
