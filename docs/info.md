## How it works

Eight signed 8-bit multipliers feed separate signed 32-bit wrapping accumulators.
The host streams weights and activations. For pointwise convolution one input
is broadcast across all eight output channels. For depthwise convolution each
lane multiplies its own activation. The host handles padding, input zero-point
correction, bias, per-channel requantization, pooling and classification.

The control byte on uio has opcode in bits 7–5, result byte index in bits 4–3
and lane in bits 2–0. All eight bidirectional pins are inputs. Drive data on ui.
Commands latch on the rising clock edge while ena is high.

| Opcode | Action |
| --- | --- |
| 0, 6, 7 | Idle. A pending product commits. |
| 1 | Write ui to the selected lane's weight. |
| 2 | Write ui to the selected lane's activation. |
| 3 | Multiply every weight by signed ui. |
| 4 | Multiply each weight by its lane activation. |
| 5 | Clear every accumulator and discard any pending product. Weight and activation registers retain their values. |

A multiply commits on the next enabled edge. Consecutive launches overlap.
An idle edge drains the last product. Low ena freezes the pipeline. Active-low
synchronous reset overrides ena and clears all state. The selected result byte
is continuously visible on uo, least-significant byte at index zero. Keep host
control and data stable around the active clock edge.

## How to test

Select the macro and apply reset across a rising edge. Write 0xfd to lane 0
with opcode 1. Send 0x07 with opcode 3 and apply an idle edge. Reading lane 0
at byte indices 0 through 3 must return eb ff ff ff (decimal -21).
The firmware/vec8.py driver includes an eight-lane board self-test.

## External hardware

A Tiny Tapeout demo board with its RP2040 can supply data, commands and clock.
A synchronous external host can supply the same interface.
