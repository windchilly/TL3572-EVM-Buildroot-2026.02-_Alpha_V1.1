/* Bounded control-plane parser. No UART/CAN MMIO or payload forwarding. */
#ifndef RK3572_INTEGRATED_COMMAND_H
#define RK3572_INTEGRATED_COMMAND_H
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define M7_MODULES 4U
#define M7_CAN_MASK 1U
#define M7_RS232_MASK 2U
#define M7_RS485_MASK 4U
#define M7_ETH_MASK 8U
/* Preserve 'all' as the three industrial tests; Ethernet requires explicit selection. */
#define M7_ALL_MASK 7U
#define M7_COMMAND_LIMIT 63U
struct M7Command { uint32_t mask, value[M7_MODULES]; };
static inline int M7BaudValid(uint32_t value)
{ return value == 9600U || value == 38400U || value == 115200U; }
/* 1 = classic CAN, 0/2/4 = FD no-BRS/about 2/about 4 Mbps. */
static inline int M7CanValid(uint32_t value)
{ return value == 1U || value == 0U || value == 2U || value == 4U; }
static inline int M7Number(const char *text, uint32_t *value)
{
    uint32_t number = 0U;
    if (!*text) { return 0; }
    while (*text) {
        if (*text < '0' || *text > '9' || number > 100000U) { return 0; }
        number = number * 10U + (uint32_t)(*text++ - '0');
    }
    *value = number; return 1;
}
static inline int M7ParseCommand(const char *data, size_t length, struct M7Command *command)
{
    char line[M7_COMMAND_LIMIT + 1U], *tokens[5];
    size_t i, count = 0U;
    struct M7Command parsed = {0};
    if (!data || !command || !length || length > M7_COMMAND_LIMIT) { return 0; }
    while (length && (data[length - 1U] == '\n' || data[length - 1U] == '\r')) { length--; }
    for (i = 0U; i < length; i++) {
        if ((unsigned char)data[i] < 32U || (unsigned char)data[i] > 126U) { return 0; }
        line[i] = data[i];
    }
    line[length] = '\0';
    for (i = 0U; i < length;) {
        while (i < length && line[i] == ' ') { line[i++] = '\0'; }
        if (i == length) { break; }
        if (count == 5U) { return 0; }
        tokens[count++] = &line[i];
        while (i < length && line[i] != ' ') { i++; }
    }
    if (count < 2U || strcmp(tokens[0], "M7")) { return 0; }
    if (count == 2U && !strcmp(tokens[1], "status")) { *command = parsed; return 1; }
    if (count < 4U || strcmp(tokens[1], "run")) { return 0; }
    if (count == 5U && !strcmp(tokens[2], "all")) {
        if (!M7Number(tokens[3], &parsed.value[1]) || !M7BaudValid(parsed.value[1]) ||
            !M7Number(tokens[4], &parsed.value[0]) || !M7CanValid(parsed.value[0])) { return 0; }
        parsed.mask = M7_ALL_MASK; parsed.value[2] = parsed.value[1];
    } else if (count == 4U) {
        uint32_t value;
        if (!M7Number(tokens[3], &value)) { return 0; }
        if (!strcmp(tokens[2], "can") && M7CanValid(value)) {
            parsed.mask = M7_CAN_MASK; parsed.value[0] = value;
        } else if (!strcmp(tokens[2], "rs232") && M7BaudValid(value)) {
            parsed.mask = M7_RS232_MASK; parsed.value[1] = value;
        } else if (!strcmp(tokens[2], "rs485") && M7BaudValid(value)) {
            parsed.mask = M7_RS485_MASK; parsed.value[2] = value;
        } else if (!strcmp(tokens[2], "eth") && (value == 0U || value == 64U || value == 1514U)) {
            parsed.mask = M7_ETH_MASK; parsed.value[3] = value;
        } else { return 0; }
    } else { return 0; }
    *command = parsed; return 1;
}
#endif
