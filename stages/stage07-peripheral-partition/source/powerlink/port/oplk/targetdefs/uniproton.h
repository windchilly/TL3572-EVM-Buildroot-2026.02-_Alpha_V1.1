/* Target ABI only. P0 does not implement the RTOS or Ethernet HAL. */
#ifndef M7_POWERLINK_TARGETDEFS_H
#define M7_POWERLINK_TARGETDEFS_H
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <oplk/basictypes.h>

#define OPLKDLLEXPORT
#define INLINE
#define OPLK_FILE_HANDLE int
#define UNUSED_PARAMETER(p) ((void)(p))
#define PRINTF(...) printf(__VA_ARGS__)
#define OPLK_MUTEX_T void*
#define OPLK_LOCK_T UINT8
#define OPLK_ATOMIC_T UINT8
#define OPLK_ATOMIC_EXCHANGE(address, newval, oldval) \
    do { (oldval) = __atomic_exchange_n((address), (newval), __ATOMIC_ACQ_REL); } while (0)

/* AArch64 inline LL/SC, not Linux atomics or a libatomic runtime. */
#if defined(__aarch64__)
#define OPLK_MEMBAR() __asm__ volatile("dmb ish" ::: "memory")
#else
#define OPLK_MEMBAR() __atomic_thread_fence(__ATOMIC_SEQ_CST)
#endif

#define OPLK_IO_WR8(addr, val) (*(volatile UINT8*)(uintptr_t)(addr) = (val))
#define OPLK_IO_WR16(addr, val) (*(volatile UINT16*)(uintptr_t)(addr) = (val))
#define OPLK_IO_WR32(addr, val) (*(volatile UINT32*)(uintptr_t)(addr) = (val))
#define OPLK_IO_RD8(addr) (*(volatile UINT8*)(uintptr_t)(addr))
#define OPLK_IO_RD16(addr) (*(volatile UINT16*)(uintptr_t)(addr))
#define OPLK_IO_RD32(addr) (*(volatile UINT32*)(uintptr_t)(addr))

/* Deliberately unresolved: do not silently treat cached buffers as coherent. */
void m7_powerlink_cache_flush(const void* address, size_t length);
void m7_powerlink_cache_invalidate(const void* address, size_t length);
#define OPLK_DCACHE_FLUSH(addr, len) m7_powerlink_cache_flush((addr), (len))
#define OPLK_DCACHE_INVALIDATE(addr, len) m7_powerlink_cache_invalidate((addr), (len))
#endif
