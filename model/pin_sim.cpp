#include "Vtt_um_kws_vec8.h"
#include <cstdio>

// Binary records are control and data bytes, one record per rising edge.
// A read/idle command returns the selected byte after the edge.
int main() {
    Vtt_um_kws_vec8 chip;
    chip.ena = 1;
    chip.rst_n = 0;
    chip.clk = 0;
    chip.eval();
    chip.clk = 1;
    chip.eval();
    chip.rst_n = 1;
    int control;
    while ((control = std::getchar()) != EOF) {
        int data = std::getchar();
        if (data == EOF) return 1;
        chip.clk = 0;
        chip.uio_in = control;
        chip.ui_in = data;
        chip.eval();
        chip.clk = 1;
        chip.eval();
        if ((control >> 5) == 0) std::putchar(chip.uo_out);
    }
    chip.final();
    return std::ferror(stdin) || std::ferror(stdout);
}
