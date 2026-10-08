/*
 * RK3572 CAN1/CAN3 polling test for the M7.0 direct-peripheral bring-up.
 *
 * Linux prepares the board pinmux/clock once and unbinds the two controllers
 * before these test images start.  From CAN controller reset mode onward all
 * frame transmit, receive and validation is performed by UniProton.
 */

#include "prt_config.h"
#include "prt_task.h"
#include "prt_typedef.h"
#include "test.h"

#define CAN1_BASE                   0x2AB10000ULL
#define CAN3_BASE                   0x2AB30000ULL

#define CAN_MODE                    0x000U
#define CAN_CMD                     0x004U
#define CAN_STATE                   0x008U
#define CAN_INT                     0x00CU
#define CAN_INT_MASK                0x010U
#define CAN_NBTP                    0x100U
#define CAN_TXFIC                   0x200U
#define CAN_TXID                    0x204U
#define CAN_TXDAT0                  0x208U
#define CAN_RXFRD                   0x400U
#define CAN_STR_CTL                 0x600U
#define CAN_STR_STATE               0x604U
#define CAN_STR_WTM                 0x60CU
#define CAN_ATF0                    0x700U
#define CAN_ATFM0                   0x714U
#define CAN_ATF_DLC                 0x728U
#define CAN_ATF_CTL                 0x72CU
#define CAN_AUTO_RETX_CFG           0x808U
#define CAN_BUSOFFRCY_CFG           0x830U
#define CAN_BUSOFF_RCY_THR          0x834U
#define CAN_RXERRORCNT              0x910U
#define CAN_TXERRORCNT              0x914U
#define CAN_RTL_VERSION             0xF0CU

#define CAN_WORK_MODE               (1U << 0)
#define CAN_INTERRUPT_STATUS_ENABLE (1U << 0)
#define CAN_TX0_REQ                 (1U << 0)
#define CAN_TX0_REQ_MASK            (1U << 16)
#define CAN_TX_FINISH_INT           (1U << 1)
#define CAN_RX_INTERRUPTS            ((1U << 0) | (1U << 7) | (1U << 15) | (1U << 17))
#define CAN_BUS_OFF_STATE           (1U << 4)

#define CAN_NBTP_996K               0x1200256DU
#define CAN_FIXED_18_WORD_STORAGE   0x108U
#define CAN_STORAGE_WATERMARK       0x6CU
#define CAN_FIFO_WORDS_PER_FRAME    18U
#define CAN_FIFO_LEFT_SHIFT         8U
#define CAN_FIFO_LEFT_MASK          0x1FFU
#define CAN_RX_DLC_SHIFT            24U
#define CAN_RX_ID_MASK              0x7FFU

#define CAN_REQUEST_ID              0x321U
#define CAN_RESPONSE_ID             0x456U
#define CAN_TEST_FRAMES             1000U
#define CAN_INITIAL_WAIT_TICKS      30000U
#define CAN_RESPONSE_WAIT_TICKS     2000U

struct CanFrame {
    U32 id;
    U8 len;
    U8 data[8];
};

struct CanTestState {
    U64 base;
    U32 txCount;
    U32 rxCount;
};

static inline U32 CanRead(const struct CanTestState *state, U32 offset)
{
    return *(volatile U32 *)(uintptr_t)(state->base + offset);
}

static inline void CanWrite(const struct CanTestState *state, U32 offset, U32 value)
{
    *(volatile U32 *)(uintptr_t)(state->base + offset) = value;
    __asm__ volatile("dsb sy" ::: "memory");
}

static void CanFillPayload(struct CanFrame *frame, U32 id, U8 marker, U32 sequence)
{
    frame->id = id;
    frame->len = 8U;
    frame->data[0] = marker;
    frame->data[1] = (U8)(sequence >> 24);
    frame->data[2] = (U8)(sequence >> 16);
    frame->data[3] = (U8)(sequence >> 8);
    frame->data[4] = (U8)sequence;
    frame->data[5] = (U8)sequence;
    frame->data[6] = (U8)(sequence ^ 0x5AU);
    frame->data[7] = (U8)(sequence ^ 0xA5U);
}

static U32 CanPayloadMatches(const struct CanFrame *frame, U32 id, U8 marker, U32 sequence)
{
    struct CanFrame expected;
    U32 index;

    CanFillPayload(&expected, id, marker, sequence);
    if ((frame->id != expected.id) || (frame->len != expected.len)) {
        return 0U;
    }
    for (index = 0U; index < expected.len; index++) {
        if (frame->data[index] != expected.data[index]) {
            return 0U;
        }
    }
    return 1U;
}

static U32 CanInitialize(struct CanTestState *state)
{
    U32 index;

    CanWrite(state, CAN_MODE, 0U);
    /* Match the vendor driver's running value so polling can see completion. */
    CanWrite(state, CAN_INT_MASK, CAN_INTERRUPT_STATUS_ENABLE);
    CanWrite(state, CAN_INT, 0xFFFFFFFFU);

    for (index = 0U; index < 5U; index++) {
        CanWrite(state, CAN_ATF0 + index * sizeof(U32), 0U);
        CanWrite(state, CAN_ATFM0 + index * sizeof(U32), 0x7FFFU);
    }
    CanWrite(state, CAN_ATF_DLC, 0U);
    CanWrite(state, CAN_ATF_CTL, 0U);
    CanWrite(state, CAN_STR_CTL, CAN_FIXED_18_WORD_STORAGE);
    CanWrite(state, CAN_STR_WTM, CAN_STORAGE_WATERMARK);
    CanWrite(state, CAN_AUTO_RETX_CFG, 1U);
    CanWrite(state, CAN_BUSOFFRCY_CFG, (1U << 8) | 4U);
    CanWrite(state, CAN_BUSOFF_RCY_THR, 0x3D0900U);
    CanWrite(state, CAN_NBTP, CAN_NBTP_996K);
    CanWrite(state, CAN_MODE, CAN_WORK_MODE);

    if ((CanRead(state, CAN_MODE) & CAN_WORK_MODE) == 0U) {
        return 1U;
    }
    return 0U;
}

static U32 CanTransmit(struct CanTestState *state, const struct CanFrame *frame)
{
    U32 data0;
    U32 data1;
    U32 ticks;
    U32 status;

    if ((frame->len != 8U) || (frame->id > CAN_RX_ID_MASK)) {
        return 1U;
    }
    data0 = (U32)frame->data[0] | ((U32)frame->data[1] << 8) |
            ((U32)frame->data[2] << 16) | ((U32)frame->data[3] << 24);
    data1 = (U32)frame->data[4] | ((U32)frame->data[5] << 8) |
            ((U32)frame->data[6] << 16) | ((U32)frame->data[7] << 24);

    CanWrite(state, CAN_CMD, 0U);
    CanWrite(state, CAN_INT, CAN_TX_FINISH_INT);
    CanWrite(state, CAN_TXID, frame->id);
    CanWrite(state, CAN_TXFIC, frame->len);
    CanWrite(state, CAN_TXDAT0, data0);
    CanWrite(state, CAN_TXDAT0 + sizeof(U32), data1);
    CanWrite(state, CAN_CMD, CAN_TX0_REQ | CAN_TX0_REQ_MASK);

    for (ticks = 0U; ticks < CAN_RESPONSE_WAIT_TICKS; ticks++) {
        status = CanRead(state, CAN_INT);
        if ((status & CAN_TX_FINISH_INT) != 0U) {
            CanWrite(state, CAN_CMD, 0U);
            CanWrite(state, CAN_INT, CAN_TX_FINISH_INT);
            state->txCount++;
            return 0U;
        }
        if ((CanRead(state, CAN_STATE) & CAN_BUS_OFF_STATE) != 0U) {
            return 2U;
        }
        (void)PRT_TaskDelay(1U);
    }
    return 3U;
}

static U32 CanReceive(struct CanTestState *state, struct CanFrame *frame, U32 timeoutTicks)
{
    U32 words[16];
    U32 fifoInfo;
    U32 leftWords;
    U32 ticks;
    U32 index;
    U32 word;

    for (ticks = 0U; ticks < timeoutTicks; ticks++) {
        leftWords = (CanRead(state, CAN_STR_STATE) >> CAN_FIFO_LEFT_SHIFT) & CAN_FIFO_LEFT_MASK;
        if (leftWords >= CAN_FIFO_WORDS_PER_FRAME) {
            fifoInfo = CanRead(state, CAN_RXFRD);
            frame->id = CanRead(state, CAN_RXFRD) & CAN_RX_ID_MASK;
            for (index = 0U; index < 16U; index++) {
                words[index] = CanRead(state, CAN_RXFRD);
            }
            frame->len = (U8)((fifoInfo >> CAN_RX_DLC_SHIFT) & 0xFU);
            if (frame->len > 8U) {
                return 2U;
            }
            for (index = 0U; index < frame->len; index++) {
                word = words[index / 4U];
                frame->data[index] = (U8)(word >> ((index % 4U) * 8U));
            }
            CanWrite(state, CAN_INT, CanRead(state, CAN_INT) & CAN_RX_INTERRUPTS);
            state->rxCount++;
            return 0U;
        }
        if ((CanRead(state, CAN_STATE) & CAN_BUS_OFF_STATE) != 0U) {
            return 3U;
        }
        (void)PRT_TaskDelay(1U);
    }
    return 1U;
}

#if (MCS_CLIENT_CPU_ID == 4)
static U32 CanRunInitiator(struct CanTestState *state)
{
    struct CanFrame request;
    struct CanFrame response;
    U32 sequence;
    U32 ret;

    (void)PRT_TaskDelay(500U);
    for (sequence = 0U; sequence < CAN_TEST_FRAMES; sequence++) {
        CanFillPayload(&request, CAN_REQUEST_ID, (U8)'A', sequence);
        ret = CanTransmit(state, &request);
        if (ret != 0U) {
            PRT_Printf("[can] UP1 TX fail seq=%u rc=%u\n", sequence, ret);
            return ret;
        }
        ret = CanReceive(state, &response, CAN_RESPONSE_WAIT_TICKS);
        if ((ret != 0U) || (CanPayloadMatches(&response, CAN_RESPONSE_ID, (U8)'B', sequence) == 0U)) {
            PRT_Printf("[can] UP1 RX fail seq=%u rc=%u id=0x%x len=%u\n",
                       sequence, ret, response.id, response.len);
            return (ret == 0U) ? 4U : ret;
        }
    }
    return 0U;
}

#else
static U32 CanRunResponder(struct CanTestState *state)
{
    struct CanFrame request;
    struct CanFrame response;
    U32 sequence;
    U32 ret;

    for (sequence = 0U; sequence < CAN_TEST_FRAMES; sequence++) {
        ret = CanReceive(state, &request,
                         (sequence == 0U) ? CAN_INITIAL_WAIT_TICKS : CAN_RESPONSE_WAIT_TICKS);
        if ((ret != 0U) || (CanPayloadMatches(&request, CAN_REQUEST_ID, (U8)'A', sequence) == 0U)) {
            PRT_Printf("[can] UP2 RX fail seq=%u rc=%u id=0x%x len=%u\n",
                       sequence, ret, request.id, request.len);
            return (ret == 0U) ? 4U : ret;
        }
        CanFillPayload(&response, CAN_RESPONSE_ID, (U8)'B', sequence);
        ret = CanTransmit(state, &response);
        if (ret != 0U) {
            PRT_Printf("[can] UP2 TX fail seq=%u rc=%u\n", sequence, ret);
            return ret;
        }
    }
    return 0U;
}
#endif

U32 Rk3572CanDirectTest(void)
{
    struct CanTestState state = {0};
    U32 ret;

#if (MCS_CLIENT_CPU_ID == 4)
    state.base = CAN1_BASE;
#elif (MCS_CLIENT_CPU_ID == 5)
    state.base = CAN3_BASE;
#else
#error "M7 CAN direct test supports only CPU4 and CPU5"
#endif

    ret = CanInitialize(&state);
    PRT_Printf("[can] UP%u direct controller ready base=0x%x rtl=0x%x nbtp=0x%x\n",
               MCS_CLIENT_CPU_ID - 3U, (U32)state.base,
               CanRead(&state, CAN_RTL_VERSION), CanRead(&state, CAN_NBTP));
    if (ret == 0U) {
#if (MCS_CLIENT_CPU_ID == 4)
        ret = CanRunInitiator(&state);
#else
        ret = CanRunResponder(&state);
#endif
    }

    PRT_Printf("[can] UP%u direct %s tx=%u rx=%u txerr=%u rxerr=%u state=0x%x rc=%u\n",
               MCS_CLIENT_CPU_ID - 3U, (ret == 0U) ? "PASS" : "FAIL",
               state.txCount, state.rxCount, CanRead(&state, CAN_TXERRORCNT),
               CanRead(&state, CAN_RXERRORCNT), CanRead(&state, CAN_STATE), ret);
    return ret;
}
