#include "simple_system_common.h"
#include "vectors.h"

static volatile uint32_t *const mmio = (volatile uint32_t *)0x40000;
static int32_t raw[125 * 64];
static int8_t output[125 * 64];

static uint32_t cycles(void) {
    uint32_t v;
    asm volatile ("csrr %0, mcycle" : "=r"(v) :: "memory");
    return v;
}

static void cpu(void) {
    for (int p = 0; p < 125; ++p)
        for (int c = 0; c < 64; ++c) {
            int32_t sum = 0;
            for (int k = 0; k < 64; ++k)
                sum += input[p*64+k] * weight[c*64+k];
            raw[p*64+c] = sum;
        }
}

static void pins(void) {
    for (int p = 0; p < 125; ++p)
        for (int c = 0; c < 64; c += 8) {
            mmio[5<<5] = 0;
            for (int k = 0; k < 64; ++k) {
                for (int lane = 0; lane < 8; ++lane)
                    mmio[32+lane] = (uint8_t)weight[(c+lane)*64+k];
                mmio[3<<5] = (uint8_t)input[p*64+k];
            }
            mmio[0] = 0;
            for (int lane = 0; lane < 8; ++lane) {
                uint32_t value = 0;
                for (int b = 0; b < 4; ++b)
                    value |= mmio[b*8+lane] << (8*b);
                raw[p*64+c+lane] = (int32_t)value;
            }
        }
}

static void reuse(void) {
    for (int c = 0; c < 64; c += 8) {
        for (int k = 0; k < 64; ++k)
            for (int half = 0; half < 2; ++half) {
                uint32_t word = 0;
                for (int b = 0; b < 4; ++b)
                    word |= (uint32_t)(uint8_t)weight[(c+half*4+b)*64+k] << (8*b);
                mmio[0x400/4 + 2*k + half] = word;
            }
        for (int p = 0; p < 125; ++p) {
            mmio[0x604/4] = 0;
            for (int k = 0; k < 64; k += 4) {
                uint32_t word;
                __builtin_memcpy(&word, &input[p*64+k], sizeof(word));
                while (mmio[0x608/4]) {}
                mmio[0x600/4] = word;
            }
            while (mmio[0x608/4]) {}
            for (int lane = 0; lane < 8; ++lane)
                raw[p*64+c+lane] = (int32_t)mmio[0x620/4+lane];
        }
    }
}

static void requantize(void) {
    for (int i = 0; i < 125*64; ++i) {
        int c = i & 63;
        int64_t product = (int64_t)(raw[i]+offset[c]) * mult[c];
        int32_t high = (int32_t)((product + (1LL<<30)) >> 31);
        int mask = (1 << shift[c]) - 1;
        int value = (high >> shift[c]) + ((high & mask) > ((mask>>1) + (high < 0))) - 128;
        output[i] = value < -128 ? -128 : value > 127 ? 127 : value;
    }
}

static void run(const char *name, void (*kernel)(void), uint32_t expected_launches) {
    for (int i = 0; i < 125*64; ++i) raw[i] = 0x55555555;
    uint32_t before = mmio[0x60c/4];
    uint32_t start = cycles();
    kernel();
    uint32_t middle = cycles();
    requantize();
    uint32_t end = cycles();
    uint32_t launches = mmio[0x60c/4] - before;
    puts(name); putchar(' '); puthex(middle-start); putchar(' ');
    puthex(end-start); putchar(' '); puthex(launches);
    for (int i = 0; i < 125*64; ++i)
        if (raw[i] != expected_raw[i] || output[i] != expected[i]) {
            puts(" FAIL index "); puthex(i); putchar('\n'); sim_halt(); return;
        }
    puts(launches == expected_launches ? " PASS\n" : " FAIL launches\n");
}

int main(void) {
    pcount_enable(1);
    run("CPU", cpu, 0);
    run("PINS", pins, 64000);
    run("REUSE", reuse, 64000);
    return 0;
}
