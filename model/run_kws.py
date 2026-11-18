"""Exercise all nine convolutions over the chip pins and compare to LiteRT."""
import argparse
import pathlib
import struct
import subprocess

import numpy as np
import tflite
from ai_edge_litert.interpreter import Interpreter, OpResolverType


def interpreter(blob):
    runtime = Interpreter(model_content=bytes(blob), experimental_preserve_all_tensors=True,
                          experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
    runtime.allocate_tensors()
    return runtime


def cpu_tail(blob, activation, first_op):
    # Reuse the original pool, reshape, FC and softmax operators and constants.
    # Point the single subgraph input at the activation supplied by the chip.
    buf = bytearray(blob)
    graph = tflite.Model.GetRootAsModel(buf).Subgraphs(0)
    assert graph.InputsLength() == 1
    struct.pack_into('<I', buf, graph._tab.Vector(graph._tab.Offset(6)), 30)
    ops = graph._tab.Vector(graph._tab.Offset(10))
    count = graph.OperatorsLength() - first_op
    for i in range(count):
        src = ops + 4 * (i + first_op)
        offset, = struct.unpack_from('<I', buf, src)
        struct.pack_into('<I', buf, ops + 4*i, offset + 4*first_op)
    struct.pack_into('<I', buf, ops - 4, count)
    cpu = interpreter(buf)
    cpu.set_tensor(30, activation)
    cpu.invoke()
    return cpu.get_tensor(cpu.get_output_details()[0]['index'])


def requant(acc, scales, zero):
    frac, exponent = np.frexp(scales)
    multiplier = np.floor(frac * (1 << 31) + 0.5).astype(np.int64)
    carry = multiplier == 1 << 31
    multiplier = np.where(carry, multiplier // 2, multiplier)
    exponent = exponent + carry
    value = (acc << np.maximum(exponent, 0)) * multiplier
    high = (value + (1 << 30)) >> 31
    shift = np.maximum(-exponent, 0)
    mask = (np.int64(1) << shift) - 1
    rounded = (high >> shift) + ((high & mask) > ((mask >> 1) + (high < 0)))
    return np.clip(rounded + zero, zero, 127).astype(np.int8)  # fused ReLU


def chip_layer(sim, image, weights, bias, izero, depthwise, stride, out_shape):
    height, width, channels = image.shape
    oh, ow, oc = out_shape
    _, kh, kw, _ = weights.shape
    ph = max(0, (oh-1)*stride + kh-height)
    pw = max(0, (ow-1)*stride + kw-width)
    padded = np.pad(image, ((ph//2, ph-ph//2), (pw//2, pw-pw//2), (0, 0)),
                    constant_values=izero)
    lanes = np.arange(8)
    taps = kh*kw if depthwise else kh*kw*channels
    cmds_per_tap = 17 if depthwise else 9
    groups = oc//8
    if depthwise:
        kernels = weights.reshape(taps, groups, 8).transpose(1, 0, 2)
    else:
        kernels = weights.reshape(groups, 8, taps).transpose(0, 2, 1)
    # Each output group has a clear, a tap loop, a pipeline drain and 32 reads.
    frames = np.zeros((oh, ow, groups, 34 + taps*cmds_per_tap, 2), np.uint8)
    frames[:, :, :, 0, 0] = 5 << 5
    frames[:, :, :, -33, 0] = 6 << 5
    frames[:, :, :, -32:, 0] = (lanes[:, None] + 8*np.arange(4)).reshape(32)
    body = frames[:, :, :, 1:-33].reshape(oh, ow, groups, taps, cmds_per_tap, 2)
    body[..., :8, 0] = 32 + lanes
    body[..., :8, 1] = kernels
    body[..., -1, 0] = (4 if depthwise else 3) << 5
    for y, x in np.ndindex(oh, ow):
        window = padded[y*stride:y*stride+kh, x*stride:x*stride+kw]
        if depthwise:
            body[y,x,:,:,8:16,0] = 64 + lanes
            body[y,x,:,:,8:16,1] = window.reshape(taps,groups,8).transpose(1,0,2)
        else:
            body[y,x,:,:,-1,1] = window.reshape(taps)
    output = subprocess.run([sim], input=frames.tobytes(), stdout=subprocess.PIPE, check=True)
    raw = np.frombuffer(output.stdout, '<i4').reshape(oh, ow, oc).astype(np.int64)
    correction = kernels.astype(np.int64).sum(axis=1).reshape(oc) * izero
    return raw + bias - correction, frames.size//2, oh*ow*oc*taps


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('simulator')
    source = parser.add_mutually_exclusive_group()
    source.add_argument('--seed', type=int)
    source.add_argument('--sample', type=int, default=0)
    args = parser.parse_args()
    blob = pathlib.Path(__file__).with_name('kws_ref_model.tflite').read_bytes()
    ref = interpreter(blob)
    details = {t['index']: t for t in ref.get_tensor_details()}
    if args.seed is None:
        samples = np.fromfile(pathlib.Path(__file__).with_name('reference_inputs.i8'), np.int8)
        image = samples.reshape(-1, 49, 10, 1)[args.sample][None]
    else:
        image = np.random.default_rng(args.seed).integers(-128, 128, (1,49,10,1), dtype=np.int8)
    ref.set_tensor(0, image)
    ref.invoke()
    total = 0
    for n, op in enumerate(ref._get_ops_details()[:9]):
        act, filt, bias = op['inputs']
        out, = op['outputs']
        depthwise = op['op_name'] == 'DEPTHWISE_CONV_2D'
        isc, iz = details[act]['quantization']
        osc, oz = details[out]['quantization']
        ws = details[filt]['quantization_parameters']['scales'].astype(np.float64)
        acc, cycles, macs = chip_layer(args.simulator, image[0], ref.get_tensor(filt),
                                       ref.get_tensor(bias), iz, depthwise, 2 if n==0 else 1,
                                       details[out]['shape'][1:])
        image = requant(acc, isc*ws/osc, oz)[None]
        np.testing.assert_array_equal(image, ref.get_tensor(out))
        print(f'{n+1:2} {op["op_name"]:19} {macs:8} MAC {cycles:8} clocks   bit-exact')
        total += cycles
    result = cpu_tail(blob, image, 9)
    np.testing.assert_array_equal(result, ref.get_tensor(34))
    print('Classifier bytes', result.tolist(), 'bus clocks', total)


if __name__ == '__main__':
    main()
