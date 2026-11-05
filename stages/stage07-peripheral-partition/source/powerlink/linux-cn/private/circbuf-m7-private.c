/* Fixed Linux single-process CN: heap buffers, static private mutex, no named
 * IPC. Like upstream circbuf-noos, both layers share one instance per id; unlike
 * noos, all data access is mutex-protected and connections own references.
 * Construction/connection/destruction are serialized by the lifecycle owner;
 * runtime data operations may use stack workers. No fork while the stack lives. */
#include <common/oplkinc.h>
#include "circbuf-arch.h"
#include <common/m7_cn_private.h>
#include <pthread.h>
#include <stdint.h>
static struct { tCircBufInstance instance; unsigned refs,closing; } pool[NR_OF_CIRC_BUFFERS];
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;

tCircBufInstance* circbuf_createInstance(UINT8 id,BOOL fresh)
{
    tCircBufInstance* result=NULL;
    if (id>=NR_OF_CIRC_BUFFERS) return NULL;
    pthread_mutex_lock(&lock);
    if ((fresh && !pool[id].refs) || (!fresh && pool[id].refs && pool[id].refs<2 && !pool[id].closing && pool[id].instance.pCircBufHeader)) {
        if (fresh) { memset(&pool[id],0,sizeof(pool[id]));pool[id].instance.bufferId=id; }
        pool[id].refs++;result=&pool[id].instance;
    }
    pthread_mutex_unlock(&lock);return result;
}
void circbuf_freeInstance(tCircBufInstance* instance)
{
    unsigned id=instance->bufferId;
    pthread_mutex_lock(&lock);
    if (--pool[id].refs==0) {
        free(instance->pCircBufHeader);
        memset(&pool[id],0,sizeof(pool[id]));
    }
    pthread_mutex_unlock(&lock);
}
tCircBufError circbuf_allocBuffer(tCircBufInstance* instance,size_t* size)
{
    if (!size || !*size || *size>1048576U || *size>SIZE_MAX-sizeof(tCircBufHeader)) return kCircBufInvalidArg;
    pthread_mutex_lock(&lock);
    instance->pCircBufHeader=calloc(1,sizeof(tCircBufHeader)+*size);
    if (instance->pCircBufHeader) instance->pCircBuf=(UINT8*)instance->pCircBufHeader+sizeof(tCircBufHeader);
    pthread_mutex_unlock(&lock);
    return instance->pCircBufHeader?kCircBufOk:kCircBufNoResource;
}
void circbuf_freeBuffer(tCircBufInstance* instance)
{
    pthread_mutex_lock(&lock);pool[instance->bufferId].closing=1;pthread_mutex_unlock(&lock);
    /* Storage remains until the last existing connector also releases it. */
}
tCircBufError circbuf_connectBuffer(tCircBufInstance* instance)
{ return instance->pCircBufHeader?kCircBufOk:kCircBufNoResource; }
void circbuf_disconnectBuffer(tCircBufInstance* instance) { (void)instance; }
void circbuf_lock(tCircBufInstance* instance) { (void)instance;pthread_mutex_lock(&lock); }
void circbuf_unlock(tCircBufInstance* instance) { (void)instance;pthread_mutex_unlock(&lock); }
unsigned m7_cn_private_buffers(void)
{
    unsigned id,count=0;pthread_mutex_lock(&lock);
    for (id=0;id<NR_OF_CIRC_BUFFERS;id++) if (pool[id].refs) count++;
    pthread_mutex_unlock(&lock);return count;
}
