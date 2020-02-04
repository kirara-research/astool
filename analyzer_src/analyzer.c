#include <stdio.h>
#include <stdint.h>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <stddef.h>
#include <string.h>
#include <capstone/capstone.h>

__attribute__((used)) static char *whats = 
    "@(#)analyzer.c: master key finder (c) 2020 The Holy Constituency of the Summer Triangle. All rights reserved.";

void print_code_seg(uint32_t *code, int ninsns) {
    csh handle;
	cs_insn *insn;
	size_t count;

    cs_err error;
	if ((error = cs_open(CS_ARCH_ARM, CS_MODE_ARM, &handle)) != CS_ERR_OK) {
        fprintf(stderr, "[!] Failed to initialize Capstone: %d\n", error);
        fprintf(stderr, "[!] Code readout is unavailable\n");
        return;
    }

	count = cs_disasm(handle, (uint8_t *)code, sizeof(*code) * ninsns, 0x1000, 0, &insn);
	if (count > 0) {
		size_t j;
		for (j = 0; j < count; j++) {
            if (strstr(insn[j].op_str, "#4") || strstr(insn[j].op_str, "#8")) {
                printf("**\t%s\t\t%s\n", insn[j].mnemonic,
					insn[j].op_str);
            } else {
                printf("\t%s\t\t%s\n", insn[j].mnemonic,
					insn[j].op_str);
            }
		}

		cs_free(insn, count);
	} else {
        fprintf(stderr, "[!] Disassembly failed: %d\n", cs_errno(handle));
        fprintf(stderr, "[!] Code readout is unavailable\n");
    }

	cs_close(&handle);
}

uint32_t *load_dumpfile(int fd, size_t *sizeout) {
    off_t len = lseek(fd, 0, SEEK_END);
    printf("Image size: %lld\n", len);
    uint8_t *base = mmap(NULL, len, PROT_READ, MAP_PRIVATE | MAP_FILE, fd, 0);

    if (base != MAP_FAILED) {
        *sizeout = len;
        return (uint32_t *)base;
    }

    return NULL;
}

uint32_t *find_image_base(uint32_t *min, uint32_t *start) {
    start = (uint32_t *)((uintptr_t)start & (~0xFFFllu));
    for (; start > min; start -= 1024) {
        if (*start == 0x464c457f /* \x7fELF */) {
            return start;
        }
    }

    return NULL;
}

uint32_t *find_subr_start(uint32_t *min, uint32_t *start) {
    #define MASK_STMDB 0xffff0000U
    #define EXPECT_STMDB 0xe92d0000U

    for (; start > min; --start) {
        if (((*start) & MASK_STMDB) == EXPECT_STMDB) {
            return start;
        }
    }

    return NULL;
}

enum CI_REC_STATE {
    CIR_START,
    CIR_HAVE_MOVW,
    CIR_HAVE_MOVT,
    CIR_DONE
};

uint32_t *find_constant_init(uint32_t *indata, size_t extent, uintptr_t real_base) {
    #define MASK_MOVW 0xffff0fffU
    #define MASK_MOVT 0xffff0fffU
    #define MASK_REGN 0xf000U

    #define EXPECT_MOVW_83D600 0xe30d0600U
    #define EXPECT_MOVT_83D600 0xe3400083U

    int state = CIR_START;
    int walk = 0;
    uint32_t reg = 0xffffffff;
    uint32_t *done = NULL;

    for (size_t i = 0; i < extent; ++i) {
        switch(state) {
            case CIR_START: {
                if ((indata[i] & MASK_MOVW) == EXPECT_MOVW_83D600) {
                    state = CIR_HAVE_MOVW;
                } else if ((indata[i] & MASK_MOVT) == EXPECT_MOVT_83D600) {
                    state = CIR_HAVE_MOVT;
                } else {
                    break;
                }

                reg = indata[i] & MASK_REGN;
                break;
            }

            case CIR_HAVE_MOVT: {
                walk++;
                if ((indata[i] & MASK_MOVW) == EXPECT_MOVW_83D600
                    && (indata[i] & MASK_REGN) == reg) {
                    state = CIR_DONE;
                    done = &indata[i];
                    break;
                }
            }

            case CIR_HAVE_MOVW: {
                walk++;
                if ((indata[i] & MASK_MOVT) == EXPECT_MOVT_83D600
                    && (indata[i] & MASK_REGN) == reg) {
                    state = CIR_DONE;
                    done = &indata[i];
                    break;
                }
            }

            default: break;
        }

        if (state == CIR_DONE) break;
    }

    if (!done) {
        fprintf(stderr, "[!] No candidates found (or reached EOF)\n");
        return NULL;
    }

    uint32_t *start = find_subr_start(indata, done);
    if (!start) {
        return done;
    }

    return start;
}

int main(int argc, char const *argv[]) {
    if (argc < 2) {
        fputs("usage: ./analyzer [path-to-dumped-image]", stderr);
        return 1;
    }

    int fd = open(argv[1], O_RDONLY);
    if (!fd) {
        perror("open");
        return 2;
    }

    size_t extent;
    uint32_t *base = load_dumpfile(fd, &extent);
    uint32_t *max = base + (extent / 4);

    if (!base) {
        perror("Map failed");
        return 2;
    }

    uint32_t *sfrom = base;
    while (sfrom < max) {
        ptrdiff_t dist = sfrom - base;
        uint32_t *ca_func = find_constant_init(sfrom, (extent / 4) - dist, (uintptr_t)base);
        if (!ca_func) {
            break;
        }

        uint32_t *image = find_image_base(base, ca_func);
        if (image) {
            printf("[-] Base of image containing candidate: +%016lx\n",
                ((uintptr_t)image) - (uintptr_t)base);
        }

        printf("[-] Potential candidate at + %016lx\n", 
                ((uintptr_t)ca_func) - (uintptr_t)base);
        if (((*ca_func) & MASK_STMDB) == EXPECT_STMDB) {
            print_code_seg(ca_func, 50);
        }

        sfrom = ca_func + 1;
    }

    munmap(base, extent);
    close(fd);
    return 0;
}
