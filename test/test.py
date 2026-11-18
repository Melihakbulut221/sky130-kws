import random

import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def protocol(dut):
    weights = [0] * 8
    activations = [0] * 8
    sums = [0] * 8
    pending = [0] * 8
    rng = random.Random(26011)
    for step in range(260):
        op = rng.choice([1, 2, 3, 3, 4, 4, 0, 5, 6, 7])
        lane = rng.randrange(8)
        data = rng.choice([-128, 127, rng.randrange(-128, 128)])
        enable = rng.randrange(5) != 0
        reset = step in (0, 137)
        dut.clk.value = 0
        dut.ena.value = enable
        dut.rst_n.value = int(not reset)
        dut.ui_in.value = data & 255
        dut.uio_in.value = (op << 5) | lane
        await Timer(20, unit="ns")
        dut.clk.value = 1
        await Timer(20, unit="ns")
        if reset:
            weights, activations, sums, pending = ([0] * 8 for _ in range(4))
        elif enable:
            sums = [0 if op == 5 else a + b for a, b in zip(sums, pending)]
            pending = [w * (data if op == 3 else x) if op in (3, 4) else 0
                       for w, x in zip(weights, activations)]
            if op == 1:
                weights[lane] = data
            if op == 2:
                activations[lane] = data
        assert int(dut.uio_oe.value) == 0
        for lane in range(8):
            for byte in range(4):
                dut.uio_in.value = byte * 8 + lane
                await Timer(12, unit="ns")
                assert int(dut.uo_out.value) == (sums[lane] >> (8 * byte)) & 255
