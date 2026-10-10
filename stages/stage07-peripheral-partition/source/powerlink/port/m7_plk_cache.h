#ifndef M7_PLK_CACHE_H
#define M7_PLK_CACHE_H
#include <stddef.h>
#include <stdint.h>
/* 1=owned cacheable image; 2=owned Normal-NC DMA; 0=not permitted. */
static inline int m7_plk_cache_range(uintptr_t begin, size_t length)
{
    uintptr_t end;
    if (!length || length > UINTPTR_MAX - begin) return 0;
    end = begin + length;
    if (begin >= 0x7c200000ULL && end <= 0x7ca00000ULL) return 1;
    if (begin >= 0x7ca10000ULL && end <= 0x7ca20000ULL) return 2;
    return 0;
}
#endif
