#include <stdio.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>

__attribute__((used)) static const char __rcsid[] = "@(#)kars/penguin_tool for utapri/All Stars    "
    "Copyright (c) 2019, the Holy Constituency of the Summer Triangle. All rights reserved.";

struct penguin_keyset {
    uint32_t k1;
    uint32_t k2;
    uint32_t k3;
};

#define PENGUIN_K3_DEFAULT 0x3039

extern void penguin_decrypt_buf(struct penguin_keyset *initp, uint8_t *buf, int size);
void penguin_decrypt_buf(struct penguin_keyset *initp, uint8_t *buf, int size) {
    uint32_t mul1 = initp->k1; // esi
    uint32_t mul2 = initp->k2; // edi
    uint32_t mul_static = initp->k3; // ecx

    while (size --> 0) {
        uint32_t k1 = mul1 >> 0x18; // eax
        uint32_t k2 = mul2 >> 0x18; // ebp
        uint32_t k3 = mul_static >> 0x18;

        uint8_t op = *buf;
        op ^= k1;
        op ^= k2;
        op ^= k3;

        mul1 *= 0x343FD;
        mul1 += 0x269EC3;

        mul2 *= 0x343FD;
        mul2 += 0x269EC3;

        mul_static *= 0x343FD;
        mul_static += 0x269EC3;
        *buf++ = op;
    }

    initp->k1 = mul1;
    initp->k2 = mul2;
    initp->k3 = mul_static;
}

#if HAVE_MAIN
int main(int argc, char const *argv[]) {
    int input_fd = STDIN_FILENO,
        output_fd = STDOUT_FILENO;
    const char *k1s = NULL, *k2s = NULL, *k3s = NULL;

    switch (argc) {
    case 5:
        k2s = argv[4];
    case 4:
        k1s = argv[3];
    case 3: {
        /* use - in place of a filename to use stdin/stdout */
        if (strcmp(argv[2], "-")) {
            output_fd = open(argv[2], O_CREAT | O_WRONLY, 0644);

            if (output_fd < 0) {
                fprintf(stderr, "[!] error opening %s for output: %s", argv[2], strerror(errno));
                return 1;
            }
        }
    }
    /* fall through to opening the input file. */
    case 2: {
        if (strcmp(argv[1], "-")) {
            input_fd = open(argv[1], O_RDONLY);

            if (input_fd < 0) {
                fprintf(stderr, "[!] error opening %s for input: %s", argv[1], strerror(errno));
                return 1;
            }
        }
    }
    default:
        break;
    }

    uint32_t initk1, initk2, initk3;
    if (!k1s) {
        k1s = getenv("PENGUIN_KEY_1");
        if (!k1s) {
            fprintf(stderr, "[!] key1 not provided\n");
            return 1;
        }
    }
    if (!k2s) {
        k2s = getenv("PENGUIN_KEY_2");
        if (!k2s) {
            fprintf(stderr, "[!] key2 not provided\n");
        }
    }
    if (!k3s) {
        k3s = getenv("PENGUIN_KEY_3");
        if (!k3s) {
            k3s = "3039";
        }
    }

    initk1 = strtoul(k1s, NULL, 16);
    initk2 = strtoul(k2s, NULL, 16);
    initk3 = strtoul(k3s, NULL, 16);

    uint8_t data[4096];
    ssize_t datalen;

    struct penguin_keyset key = {
        .k1 = initk1,
        .k2 = initk2,
        .k3 = initk3,
    };

    while (1) {
        datalen = read(input_fd, data, 4096);

        if (datalen == 0) {
            // EOF
            errno = 0;
            break;
        } else if (datalen == -1) {
            fprintf(stderr, "[!] error reading the is: %s", strerror(errno));
            break;
        }

        penguin_decrypt_buf(&key, data, datalen);
        if (write(output_fd, data, datalen) != datalen) {
            fprintf(stderr, "[!] error writing output: %s", strerror(errno));
            break;
        }
    }

    return errno;
}
#endif