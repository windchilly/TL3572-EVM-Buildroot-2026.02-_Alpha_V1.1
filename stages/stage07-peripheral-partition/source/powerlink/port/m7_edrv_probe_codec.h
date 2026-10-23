/* Fixed experimental EtherType, per-run nonce, strict bounded stop-and-wait. */
#ifndef M7_EDRV_PROBE_CODEC_H
#define M7_EDRV_PROBE_CODEC_H
#include "rk3572_eth_codec.h"
#include "m7_edrv_probe.h"
static inline uint32_t M7ProbeLength(uint32_t sequence)
{ return sequence < M7_EDRV_PROBE_EACH ? 64U : 1514U; }
static inline void M7ProbeFrame(uint8_t* p, const uint8_t* dst, const uint8_t* src,
    uint32_t nonce, uint32_t sequence, uint32_t role)
{
    uint32_t i, length = M7ProbeLength(sequence);
    memcpy(p, dst, 6); memcpy(p + 6, src, 6); p[12] = 0x88; p[13] = 0xb5;
    memcpy(p + 14, "M7EDRV01", 8); EthPut32(p + 22, nonce); EthPut32(p + 26, role);
    EthPut32(p + 30, sequence); EthPut32(p + 34, length - 42U);
    for (i = 0; i < length - 42U; ++i) p[38U + i] = (uint8_t)(nonce + sequence + i);
    EthPut32(p + length - 4U, EthCrc(p + 14, length - 18U));
}
static inline int M7ProbeValid(const uint8_t* p, uint32_t length,
    uint32_t nonce, uint32_t sequence, uint32_t role)
{
    uint32_t i;
    if (sequence >= M7_EDRV_PROBE_TOTAL || length != M7ProbeLength(sequence) ||
        p[12] != 0x88 || p[13] != 0xb5 || memcmp(p + 14, "M7EDRV01", 8) ||
        EthGet32(p + 22) != nonce || EthGet32(p + 26) != role || EthGet32(p + 30) != sequence ||
        EthGet32(p + 34) != length - 42U ||
        EthGet32(p + length - 4U) != EthCrc(p + 14, length - 18U)) return 0;
    for (i = 0; i < length - 42U; ++i)
        if (p[38U + i] != (uint8_t)(nonce + sequence + i)) return 0;
    return 1;
}
#endif
