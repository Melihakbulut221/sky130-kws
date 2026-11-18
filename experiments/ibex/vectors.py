"""Emit the first pointwise layer and its reference outputs for the RV32 binary."""
from pathlib import Path
import sys

import numpy as np

model = Path(__file__).resolve().parents[2] / "model"
sys.path.insert(0, str(model))
from run_kws import interpreter

ref = interpreter((model / "kws_ref_model.tflite").read_bytes())
ref.set_tensor(0, np.fromfile(model / "reference_inputs.i8", np.int8).reshape(-1,49,10,1)[:1])
ref.invoke()
op = ref._get_ops_details()[2]
act, weights, bias = op["inputs"]
out, = op["outputs"]
x = ref.get_tensor(act).reshape(125,64)
w = ref.get_tensor(weights).reshape(64,64)
t = {d["index"]: d for d in ref.get_tensor_details()}
isc, iz = t[act]["quantization"]
osc, oz = t[out]["quantization"]
assert oz == -128
scale = isc * t[weights]["quantization_parameters"]["scales"].astype(np.float64) / osc
frac, ex = np.frexp(scale)
mult = np.floor(frac * 2**31 + .5).astype(np.int64)
assert np.all(mult < 2**31) and np.all((-ex > 0) & (-ex < 31))
raw = x.astype(np.int32) @ w.astype(np.int32).T
for name, ctype, data in [
    ("input", "int8_t", x), ("weight", "int8_t", w),
    ("offset", "int32_t", ref.get_tensor(bias) - iz*w.astype(np.int32).sum(axis=1)),
    ("mult", "int32_t", mult), ("shift", "uint8_t", -ex),
    ("expected_raw", "int32_t", raw), ("expected", "int8_t", ref.get_tensor(out))
]:
    print(f"static const {ctype} {name}[] __attribute__((aligned(4))) = {{")
    flat = data.ravel()
    for start in range(0,len(flat),32):
        print(", ".join(map(str,flat[start:start+32]))+",")
    print("};")
