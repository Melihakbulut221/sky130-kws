# SKY130 eight-lane keyword-spotting accelerator

Target: Tiny Tapeout TTSKY26e, SKY130A high-density standard cells, 4×2 tiles,
25 MHz input clock. The macro contains eight signed int8 multipliers, eight
int32 accumulators and lane-local operand registers. Intermediate activations
and model weights live on the host. The board protocol and reset sequence are
in [the datasheet](docs/info.md). A MicroPython board smoke test is in
[firmware/vec8.py](firmware/vec8.py).

## Reproduce the checks

From the project root, with Python 3.12, Icarus Verilog, Verilator, make and a
C++ toolchain on PATH:

```sh
python -m pip install -r test/requirements.txt -r model/requirements.txt
make -C test
verilator --cc --exe --build --Mdir /tmp/vec8sim --top-module tt_um_kws_vec8 \
    src/project.v "$PWD/model/pin_sim.cpp"
python model/run_kws.py /tmp/vec8sim/Vtt_um_kws_vec8
```

The model runner sends one pin command per simulated clock, reconstructs every
32-bit accumulator via its output pins, and feeds each requantized activation
to the next layer. It compares every convolution tensor against LiteRT's
integer reference kernels. The classifier tail runs in LiteRT on the host.
The default input is the upstream reference feature tensor. Pass
`--seed 130` for a random int8 tensor. Feature extraction from audio runs
outside this benchmark. The model runner resets between layers.

The nine convolutions execute 2,656,000 MACs per input including padded taps.
The reference schedule uses 3,582,000 bus cycles plus nine simulator reset
edges. At 25 MHz this is 143.28 ms of bus time. Host processing, feature
extraction and board software add latency. The MicroPython driver uses manual
clock edges. Its speed has to be measured on a board.

## Physical build

The GitHub Actions workflow uses the official TTSKY26e GDS, precheck and
gate-level test actions. The local build used LibreLane 3.0.14,
SKY130 open_pdks 8afc8346a57fe1ab7934ba5a6056ea8b43078e71 and Tiny Tapeout
support tools 8f7b5060d7f6df73bfd2e0b8d8fa0fd1dca0a0b1. The base template
was TinyTapeout/ttsky-verilog-template at a42e6662fab316e93b4e26399e21d41664a460b7.
Tiny Tapeout assigns the board selection index during shuttle integration.

## Model provenance

The trained model and the signed 490-byte test input are from MLCommons Tiny
commit 4addd0fa08d216e20637637874e084895f289da4. The input bytes were decoded
from the C array g_kws_inputs. The upstream license accompanies the files.
Model SHA-256: aeea436800704fce17b17292e4412630ad856e9d777c044c64ef748a880bd0ae.

[Trained model](https://github.com/mlcommons/tiny/blob/4addd0fa08d216e20637637874e084895f289da4/benchmark/training/keyword_spotting/trained_models/kws_ref_model.tflite) ·
[Test input](https://github.com/mlcommons/tiny/blob/4addd0fa08d216e20637637874e084895f289da4/benchmark/reference_submissions/keyword_spotting/kws/kws_input_data.cc)
