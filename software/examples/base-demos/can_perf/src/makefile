VPATH    =
LIB_DIR  = 
INCLUDES =
CFLAGS   = 
LIBS     = 

OBJS    =

TARGET  = can_perf

all:$(TARGET)

can_perf:can_perf.o $(OBJS)
	$(CC) -o $@ $^ $(INCLUDES) $(LIBS)

%.o:%.c
	$(CC) -c $< -o $@ $(INCLUDES) $(CFLAGS)

%.d:%.c
	@set -e; $(CC) -MM $< $(INCLUDES) > $@.$$$$; \
	sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' < $@.$$$$ > $@; \
	rm -f $@.$$$$

%.o:%.cpp
	$(CC) -c $< -o $@ $(INCLUDES) $(CFLAGS)

%.d:%.cpp
	@set -e; $(CC) -MM $< $(INCLUDES) > $@.$$$$; \
	sed 's,\($*\)\.o[ :]*,\1.o $@ : ,g' < $@.$$$$ > $@; \
	rm -f $@.$$$$
			
sinclude $(OBJS:.o=.d)

.PHONY:
clean:
	rm -f $(TARGET) *.o *.d *.d.* 
install:$(TARGET)
	cp $(TARGET) $(INSTALL_DIR)
