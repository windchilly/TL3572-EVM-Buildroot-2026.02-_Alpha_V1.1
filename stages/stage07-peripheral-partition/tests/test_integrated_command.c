#include <assert.h>
#include <stdio.h>
#include "rk3572_integrated_command.h"
static void valid(const char *text, unsigned mask, unsigned can, unsigned rs232, unsigned rs485)
{
    struct M7Command command;
    assert(M7ParseCommand(text, strlen(text), &command));
    assert(command.mask == mask && command.value[0] == can && command.value[1] == rs232 && command.value[2] == rs485);
}
int main(void)
{
    char line[80];
    struct M7Command command = {99U, {99U, 99U, 99U}};
    const char *bad[] = {"", "M7", "M7 run", "M7 run all 9600", "M7 status extra", "M7 run can 3",
        "M7 run can -1", "M7 run can 4294967296", "M7 run can 10000000000000000000000000000000000",
        "M7 run rs232 19200", "M7 run rs485 0", "M7 run rs485 115200 extra", "M7 run all 115200 3",
        "M7 run all 0 4", "M7 run uart 9600", "M7 RUN can 1", "M7 run can 1\nM7 status", "M7\trun can 1"};
    valid("M7 status\n", 0U, 0U, 0U, 0U);
    valid("M7  status\r\n", 0U, 0U, 0U, 0U);
    for (unsigned i = 0U; i < 4U; i++) {
        unsigned profiles[] = {1U, 0U, 2U, 4U};
        snprintf(line, sizeof(line), "M7 run can %u\n", profiles[i]); valid(line, 1U, profiles[i], 0U, 0U);
        for (unsigned j = 0U; j < 3U; j++) {
            unsigned bauds[] = {9600U, 38400U, 115200U};
            snprintf(line, sizeof(line), "M7 run all %u %u\n", bauds[j], profiles[i]);
            valid(line, 7U, profiles[i], bauds[j], bauds[j]);
        }
    }
    for (unsigned j = 0U; j < 3U; j++) {
        unsigned bauds[] = {9600U, 38400U, 115200U};
        snprintf(line, sizeof(line), "M7 run rs232 %u", bauds[j]); valid(line, 2U, 0U, bauds[j], 0U);
        snprintf(line, sizeof(line), "M7 run rs485 %u", bauds[j]); valid(line, 4U, 0U, 0U, bauds[j]);
    }
    for (unsigned i = 0U; i < sizeof(bad) / sizeof(bad[0]); i++) {
        assert(!M7ParseCommand(bad[i], strlen(bad[i]), &command));
        assert(command.mask == 99U);
    }
    assert(!M7ParseCommand("M7 status\0tail", 14U, &command));
    memset(line, 'A', sizeof(line)); assert(!M7ParseCommand(line, sizeof(line), &command));
    assert(!M7ParseCommand(NULL, 1U, &command));
    puts("INTEGRATED COMMAND PASS: runtime profiles/bauds, bounded parse, invalid input has no side effects");
    return 0;
}
