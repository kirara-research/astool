analyzer_SRC = analyzer.c
LDFLAGS = -lcapstone
CFLAGS = -O3 -Wall

analyzer: $(analyzer_SRC)
	$(CC) -o $@ $^ ${CFLAGS} ${LDFLAGS}

.phony clean:
	rm -f analyzer