/* Pure frame/timing helpers, also compiled by the native codec test. */
#ifndef RK3572_CAN_FD_CODEC_H
#define RK3572_CAN_FD_CODEC_H
#include <stdint.h>

#define RK_CAN_FD_NBTP 0x0C020C54U
#define RK_CAN_FD_DBTP2 0x0D90031AU
#define RK_CAN_FD_DBTP4 0x0D90011AU
#define RK_CAN_FD_TDCR4 0x35U
#define RK_CAN_FD_BRS_CFG 0x7U

static inline uint8_t RkCanFdDlcToLength(uint8_t dlc)
{
    static const uint8_t lengths[16] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 12, 16, 20, 24, 32, 48, 64};
    return dlc < 16 ? lengths[dlc] : 0xFFU;
}
static inline uint8_t RkCanFdLengthToDlc(uint8_t length)
{
    uint8_t dlc;
    for (dlc = 0; dlc < 16; dlc++) {
        if (RkCanFdDlcToLength(dlc) == length) { return dlc; }
    }
    return 0xFFU; /* Test payloads must have an exact DLC, never silently round up. */
}
static inline uint32_t RkCanFdTxInfo(uint8_t length, uint8_t brs)
{
    uint8_t dlc = RkCanFdLengthToDlc(length);
    return dlc == 0xFFU ? 0xFFFFFFFFU : (uint32_t)dlc | (1U << 5) | (brs ? (1U << 4) : 0U);
}
static inline uint8_t RkCanFdMatchesRxFlags(uint32_t info, uint8_t brs)
{
    /* Standard data frame only: reject EFF/RTR, require FDF and exact BRS. */
    return (info & (0xFU << 20)) == ((1U << 21) | (brs ? (1U << 20) : 0U));
}
static inline uint32_t RkCanFdPackWord(const uint8_t *data)
{
    return (uint32_t)data[0] | ((uint32_t)data[1] << 8) |
           ((uint32_t)data[2] << 16) | ((uint32_t)data[3] << 24);
}
static inline void RkCanFdUnpackWord(uint32_t word, uint8_t *data)
{
    data[0] = (uint8_t)word; data[1] = (uint8_t)(word >> 8);
    data[2] = (uint8_t)(word >> 16); data[3] = (uint8_t)(word >> 24);
}
#endif
