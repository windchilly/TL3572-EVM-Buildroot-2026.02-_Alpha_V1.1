#include <stdarg.h>
#include "prt_typedef.h"
#include "cpu_config.h"
#include "securec.h"

/* Each instance owns the 2 MiB immediately before its firmware image. */
#define UP_LOG_BASE_ADDR       (MMU_IMAGE_ADDR - OPENAMP_LOG_LENGTH)
#define UP_LOG_MAGIC           0x55374c47U /* U7LG */
#define UP_LOG_VERSION         1U
#define UP_LOG_HEADER_SIZE     4096U
#define UP_LOG_RECORD_SIZE     512U
#define UP_LOG_TEXT_SIZE       (UP_LOG_RECORD_SIZE - 16U)
#define UP_LOG_RECORD_COUNT    ((OPENAMP_LOG_LENGTH - UP_LOG_HEADER_SIZE) / UP_LOG_RECORD_SIZE)

struct UpLogHeader {
    U32 magic;
    U32 version;
    U32 cpuId;
    U32 recordSize;
    U32 recordCount;
    U32 bootId;
    U32 writeSeq;
    U32 truncated;
};

struct UpLogRecord {
    U32 committedSeq;
    U32 bootId;
    U32 length;
    U32 reserved;
    char text[UP_LOG_TEXT_SIZE];
};

typedef char UpLogRecordSizeCheck[(sizeof(struct UpLogRecord) == UP_LOG_RECORD_SIZE) ? 1 : -1];

static volatile struct UpLogHeader *const g_upLogHeader =
    (volatile struct UpLogHeader *)UP_LOG_BASE_ADDR;
static volatile struct UpLogRecord *const g_upLogRecords =
    (volatile struct UpLogRecord *)(UP_LOG_BASE_ADDR + UP_LOG_HEADER_SIZE);

static unsigned long UpLogIrqSave(void)
{
    unsigned long flags;
    __asm__ volatile("mrs %0, daif\n\tmsr daifset, #3" : "=r"(flags) :: "memory");
    return flags;
}

static void UpLogIrqRestore(unsigned long flags)
{
    __asm__ volatile("msr daif, %0" :: "r"(flags) : "memory");
}

static void UpLogInitLocked(void)
{
    if (g_upLogHeader->magic == UP_LOG_MAGIC &&
        g_upLogHeader->version == UP_LOG_VERSION &&
        g_upLogHeader->cpuId == MCS_CLIENT_CPU_ID &&
        g_upLogHeader->recordSize == UP_LOG_RECORD_SIZE &&
        g_upLogHeader->recordCount == UP_LOG_RECORD_COUNT) {
        return;
    }

    g_upLogHeader->magic = 0U;
    g_upLogHeader->version = UP_LOG_VERSION;
    g_upLogHeader->cpuId = MCS_CLIENT_CPU_ID;
    g_upLogHeader->recordSize = UP_LOG_RECORD_SIZE;
    g_upLogHeader->recordCount = UP_LOG_RECORD_COUNT;
    g_upLogHeader->bootId = 0U;
    g_upLogHeader->writeSeq = 0U;
    g_upLogHeader->truncated = 0U;
    __asm__ volatile("dsb sy" ::: "memory");
    g_upLogHeader->magic = UP_LOG_MAGIC;
}

void UpLogBoot(void)
{
    unsigned long flags = UpLogIrqSave();
    UpLogInitLocked();
    g_upLogHeader->bootId++;
    __asm__ volatile("dsb sy" ::: "memory");
    UpLogIrqRestore(flags);
}

static int UpLogVprintf(const char *format, va_list args)
{
    static const char fallback[] = "[log] format error or message truncated\n";
    char text[UP_LOG_TEXT_SIZE];
    int len;
    U32 i, seq, index, formatError = 0U;
    unsigned long flags;
    volatile struct UpLogRecord *record;

    if (format == NULL) {
        return -1;
    }
    len = vsnprintf_s(text, sizeof(text), sizeof(text) - 1U, format, args);
    if (len < 0) {
        formatError = 1U;
        len = (int)(sizeof(fallback) - 1U);
        for (i = 0U; i < (U32)len; i++) {
            text[i] = fallback[i];
        }
        text[len] = '\0';
    }

    flags = UpLogIrqSave();
    UpLogInitLocked();
    if (g_upLogHeader->bootId == 0U) {
        g_upLogHeader->bootId = 1U;
    }
    if (formatError != 0U) {
        g_upLogHeader->truncated++;
    }
    seq = g_upLogHeader->writeSeq + 1U;
    index = (seq - 1U) % UP_LOG_RECORD_COUNT;
    record = &g_upLogRecords[index];
    record->committedSeq = 0U;
    record->bootId = g_upLogHeader->bootId;
    record->length = (U32)len;
    record->reserved = 0U;
    for (i = 0U; i < (U32)len; i++) {
        record->text[i] = text[i];
    }
    record->text[len] = '\0';
    __asm__ volatile("dsb sy" ::: "memory");
    record->committedSeq = seq;
    __asm__ volatile("dsb sy" ::: "memory");
    g_upLogHeader->writeSeq = seq;
    UpLogIrqRestore(flags);
    return len;
}

U32 PRT_Printf(const char *format, ...)
{
    va_list args;
    int ret;

    va_start(args, format);
    ret = UpLogVprintf(format, args);
    va_end(args);
    return (ret < 0) ? (U32)ret : OS_OK;
}

int printf(const char *format, ...)
{
    va_list args;
    int ret;

    va_start(args, format);
    ret = UpLogVprintf(format, args);
    va_end(args);
    return ret;
}
