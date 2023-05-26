#include <stdint.h>

struct hwd_keyset {
    uint32_t k1;
    uint32_t k2;
    uint32_t k3;
};

extern void hwd_decrypt_buf(struct hwd_keyset *initp, uint8_t *buf, int size);
void hwd_decrypt_buf(struct hwd_keyset *initp, uint8_t *buf, int size) {
    uint32_t mul1 = initp->k1;       // esi
    uint32_t mul2 = initp->k2;       // edi
    uint32_t mul_static = initp->k3; // ecx
    uint32_t k1, k2, k3;
    uint8_t op;

    while (size-- > 0) {
        k1 = mul1 >> 0x18; // eax
        k2 = mul2 >> 0x18; // ebp
        k3 = mul_static >> 0x18;

        op = *buf;
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
