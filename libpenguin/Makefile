all: libpenguin.dylib penguin_tool

penguin_tool: penguin_tool.c
	${CC} -O3 -Wall -DHAVE_MAIN=1 ${CFLAGS} ${LDFLAGS} -o $@ $<

libpenguin.dylib: penguin_tool.c
	${CC} -shared -O3 -Wall ${CFLAGS} ${LDFLAGS} -o $@ $<
