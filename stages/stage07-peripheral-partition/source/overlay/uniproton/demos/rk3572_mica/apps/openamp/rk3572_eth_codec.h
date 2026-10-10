/* Experimental raw L2 test only; no IP stack or industrial protocol. */
#ifndef RK3572_ETH_CODEC_H
#define RK3572_ETH_CODEC_H
#include <stdint.h>
#include <stddef.h>
#include <string.h>
static inline uint32_t EthGet32(const uint8_t *p)
{ return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) | ((uint32_t)p[2] << 8) | p[3]; }
static inline void EthPut32(uint8_t *p, uint32_t v)
{ p[0] = v >> 24; p[1] = v >> 16; p[2] = v >> 8; p[3] = v; }
static inline uint32_t EthCrc(const uint8_t *p, size_t n)
{
    uint32_t crc = ~0U;
    size_t i; unsigned b;
    for (i = 0; i < n; i++) {
        crc ^= p[i];
        for (b = 0; b < 8; b++) { crc = (crc >> 1) ^ (0xedb88320U & (0U - (crc & 1U))); }
    }
    return ~crc;
}
static inline int EthValidate(const uint8_t *p, uint32_t length, uint32_t seq, uint32_t role)
{
    uint32_t i;
    if (length != 64U && length != 1514U) { return 0; }
    if (p[12] != 0x88U || p[13] != 0xb5U || memcmp(p + 14, "M7ETH3L2", 8) ||
        EthGet32(p + 22) != role || EthGet32(p + 26) != seq ||
        EthGet32(p + 30) != length - 38U || EthCrc(p + 14, length - 18U) != EthGet32(p + length - 4U)) { return 0; }
    for (i = 0U; i < length - 38U; i++) { if (p[34U + i] != (uint8_t)(seq + i)) { return 0; } }
    return 1;
}
#endif
