#!/usr/bin/env bash
set -euo pipefail

here=$(cd "$(dirname "$0")" && pwd)
work=$(mktemp -d)
echo "Benchmark build directory: $work"
ibex="$work/ibex"
git init -q "$ibex"
git -C "$ibex" fetch -q --depth=1 https://github.com/lowRISC/ibex 3d524f19ee8e464b3fb0e29c77dc9ff45934815a
git -C "$ibex" checkout -q --detach FETCH_HEAD
git -C "$ibex" apply "$here/simple-system.patch"
rtl="$ibex/examples/simple_system/rtl"
cp "$here/kws_mmio.sv" "$rtl/"
cp "$here/../../src/project.v" "$rtl/tt_um_kws_vec8.v"
cd "$ibex"
flags=$(util/ibex_config.py small fusesoc_opts)
fusesoc --cores-root=. run --target=sim --setup --build lowrisc:ibex:ibex_simple_system $flags

cd "$work"
python -B "$here/vectors.py" > vectors.h
common="$ibex/examples/sw/simple_system/common"
"${RISCV_CC:-riscv64-unknown-elf-gcc}" -march=rv32imc_zicsr -mabi=ilp32 -O2 \
    -ffreestanding -nostdlib -msmall-data-limit=0 -I"$common" -I. -T "$common/link.ld" \
    "$common/crt0.S" "$common/simple_system_common.c" "$here/pointwise.c" -o pointwise.elf
sim="$ibex/build/lowrisc_ibex_ibex_simple_system_0/sim-verilator/Vibex_simple_system"
timeout 180 "$sim" --meminit=ram,pointwise.elf +ibex_tracer_enable=0
cat ibex_simple_system.log
for kernel in CPU PINS REUSE; do
    grep -Eq "^$kernel [0-9A-F]{8} [0-9A-F]{8} [0-9A-F]{8} PASS$" ibex_simple_system.log
done
