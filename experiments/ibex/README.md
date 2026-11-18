# Ibex pointwise convolution benchmark

This simulation measures the first 1×1 convolution of the reference KWS input
on the Ibex Simple System, configuration `small`. Each of 125 pixels has
64 signed int8 inputs and 64 output channels (512,000 MACs). All three paths
run in the same RV32IMC firmware image with the same instruction and data RAM.
The measured interval includes storing intermediate int32 sums, bias and
zero-point correction, per-channel requantization, fused ReLU and writing
all 8,000 int8 outputs. Validation and printing are outside the interval.

| Path | Kernel cycles | Total mcycle delta | Eight-lane MAC launches | Time at 25 MHz |
| --- | ---: | ---: | ---: | ---: |
| Scalar C, GCC -O2 | 6,720,764 | 7,125,667 | 0 | 285.03 ms |
| v1 RTL with byte-level MMIO bridge | 6,138,057 | 6,542,960 | 64,000 | 261.72 ms |
| Cached weights and packed MMIO | 314,146 | 719,049 | 64,000 | 28.76 ms |

The total-cycle speedups against the scalar C loop are 1.089× and 9.910×.
The cached path is 9.10× faster than the pin bridge. Its common CPU
postprocessing takes 404,903 cycles (56.3% of the measured interval).
An optimized RISC-V kernel could change the scalar baseline. These results
cover one layer on one reference feature tensor. CPU timing uses simulated
on-chip RAM, without RP2040 board transfers or external-memory wait states.
25 MHz is a conversion assumption for the experimental system.

## What is compared

* The pin bridge instantiates the production `tt_um_kws_vec8` unchanged.
  A word store at base + 4 × control drives one command and one byte.
  Four reads reconstruct each signed 32-bit sum.
* The experimental device has 64 rows of eight signed weights. Firmware
  loads a 512-byte bank for each group of eight output channels and reuses
  that bank for 125 pixels. Packing weights from the original channel-major
  array is inside the measurement. A one-word input buffer accepts four
  activations per write, then issues one eight-lane MAC per cycle. Firmware
  polls its busy flag and reads each accumulated result with one 32-bit load.
  The speedup includes weight reuse, packed input and wider result reads.
* The MMIO base is 0x40000. Register byte offsets are 0x000–0x3fc for
  v1 commands, 0x400–0x5fc for weights, 0x600 to submit, 0x604 to clear
  the eight sums and tap index, 0x608 for busy, 0x60c for the cumulative
  vector-launch count, and 0x620–0x63c for eight sums. The driver uses
  aligned full-word transfers and waits before submitting the next word.
* The layer-specific zero-point correction and fixed-point multipliers are
  precomputed for every path. All 8,000 raw sums are checked against NumPy
  int32 matrix multiplication and all 8,000 output bytes against the LiteRT
  reference kernel. A launch-count check verifies all 512,000 hardware MACs.

## Reproduce

Install the project's model/requirements.txt plus FuseSoC 2.4.3, Edalize
0.5.4, Verilator 5.032, a C++ toolchain, libelf headers and a bare-metal
RISC-V GCC (tested with 14.2.0 and RV32IMC support). The build script fetches
Ibex at commit 3d524f19ee8e464b3fb0e29c77dc9ff45934815a, applies the bus
patch, compiles the RTL and runs a single ELF. From the project root run:

```sh
experiments/ibex/run.sh
```

The simulator prints kernel cycles, total cycles and hardware launches in hex.
The script requires three PASS records. Set RISCV_CC to override the compiler.
The new memory and datapath are simulation RTL. Their SKY130 area and timing
have yet to be measured.
