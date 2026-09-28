set pagination off
set confirm off
set print thread-events off
set logging file /root/m7-observe-20260928/micad-abort-gdb.txt
set logging overwrite on
set logging enabled on
handle SIGABRT stop print pass
continue
thread apply all bt
info registers
generate-core-file /root/m7-observe-20260928/micad-abort.core
detach
quit
