"""Bộ sinh ảnh FLUX 3 Image Klein theo pha cho sidecar IMGGEN-SVC (DESIGN wave 42 mục 2).

Mỗi chu kỳ lấy tối đa 16 ảnh đang chờ và đi qua ba pha, mỗi pha chỉ một mô hình trên GPU: text encoder (mã hoá mọi caption),
transformer FP8 (khử nhiễu mọi ảnh), VAE (giải mã ra PNG). Trước mỗi pha cần VRAM trống (torch.cuda.mem_get_info) bằng nhu cầu
của pha cộng 1,5 GB, commit trống của hệ thống >= PHASE_COMMIT_BYTES của pha cộng 2 GB (WDDM tính VRAM vào commit của tiến
trình) và RAM trống của máy >= HOST_MIN_AVAILABLE_BYTES, không thì chờ (tối đa VRAM_WAIT_MAX_SECONDS rồi GPU_MEMORY_UNAVAILABLE,
HOST_COMMIT_LOW hay HOST_MEMORY_LOW); OOM thì giải phóng, thử lại một lần, rồi GPU_OUT_OF_MEMORY. Ngân sách bộ nhớ (memory_budget):
working set đỉnh <= 4 GiB, đỉnh (private - VRAM đang giữ, cùng mẫu) <= 4 GiB, phần dư sau pha <= 2,5 GiB ở chu kỳ đầu và <= 512 MiB
về sau; private thô chỉ báo cáo.

Nạp không qua RAM (đo của Control 02/11/2026: safetensors.load_file ánh xạ cả tệp 6,27 GB copy-on-write, bộ nhớ riêng đỉnh 16,2 GB):
stream_safetensors() đọc header bằng thư viện chuẩn rồi đọc từng khúc STREAM_CHUNK_BYTES của mỗi tensor vào một bộ đệm nhỏ và
chép thẳng vào tensor CUDA; không mmap, không giữ cả tệp. Text encoder và VAE dựng trên thiết bị meta rồi
load_state_dict(assign=True); transformer FP8 đi đúng đường của diffusers from_single_file(dict) qua bộ lượng tử BFL. Hết pha:
bỏ tham chiếu, gc.collect(), torch.cuda.empty_cache(); bộ nhớ riêng phải về gần mức trước khi nạp (dư quá RESIDUAL_LIMIT_BYTES thì
pha sau từ chối nạp với HOST_MEMORY_LOW). Mỗi pha ghi bộ nhớ riêng trước/sau nạp, sau pha, sau giải phóng và đỉnh trong pha.

Bản vá FP8: diffusers 0.42.1 BFLFP8RLinear dùng torch._scaled_mm thang theo hàng từ compute capability 8.9, nhưng torch chỉ hỗ
trợ thang theo hàng từ 9.0 (RTX 40/Ada báo "Rowwise scaling is not currently supported"). patch_bfl_fp8() chỉ áp trên (8, 9)
với diffusers 0.42.1: GEMM FP8 với thang đơn vị toàn tensor ra fp32, rồi nhân thang hàng của activation và thang hàng của trọng
số (cùng tích). Một lớp tự kiểm so với giải lượng tử; lệch quá FP8_SELFTEST_MAX_REL_ERR hoặc RuntimeError thì về giải lượng tử.

Không import torch khi nạp module: test của lane nạp module này bằng runtime sản phẩm (không có torch); KleinBackend import trễ.
Đo trên GPU (Control): python -I tools/imagegen/engine.py measure --hub <hub> --captions <json> --out <dir>
"""
from __future__ import annotations

import argparse
import gc
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imagegen import protocol  # noqa: E402

PHASES = ('text_encoder', 'transformer', 'vae')
# Bytes a phase needs on the GPU. Control's measurement on the RTX 4070 SUPER (02/11/2026, 864x1536, 16 steps): peak allocated
# 9.07e9 (text encoder), 8.08e9 (transformer), 3.41e9 (VAE); free VRAM before each phase about 11.5e9.
PHASE_REQUIREMENT_BYTES = {'text_encoder': 9_300_000_000, 'transformer': 9_300_000_000, 'vae': 4_000_000_000}
VRAM_MARGIN_BYTES = 1_500_000_000
# WDDM charges device memory to the process commit (Control 02/11/2026: private bytes = base + torch reserved in every phase), so
# a phase also needs system commit: its peak torch reserved (measured 9.16e9, 10.0e9, 5.87e9) plus COMMIT_MARGIN_BYTES.
PHASE_COMMIT_BYTES = {'text_encoder': 9_200_000_000, 'transformer': 10_100_000_000, 'vae': 6_000_000_000}
COMMIT_MARGIN_BYTES = 2_000_000_000
# Memory budget (Control 02/11/2026): working set and private commit not explained by GPU memory, and what a phase leaves.
BUDGET_WSET_MAX_BYTES = 4 * 1024 ** 3
BUDGET_HOST_PRIVATE_MAX_BYTES = 4 * 1024 ** 3
STEADY_RESIDUAL_MAX_BYTES = 512 * 1024 ** 2
VRAM_POLL_SECONDS = 2.0
VRAM_WAIT_MAX_SECONDS = 600.0
HOST_MIN_AVAILABLE_BYTES = 2_000_000_000
STREAM_CHUNK_BYTES = 64 * 1024 * 1024
FREE_TOLERANCE_BYTES = 512 * 1024 * 1024
RESIDUAL_LIMIT_BYTES = 2_560 * 1024 * 1024
MEMORY_SAMPLE_SECONDS = 0.05
FP8_SELFTEST_MAX_REL_ERR = 0.1
FP8_PATCH_CAPABILITY = (8, 9)
FP8_PATCH_DIFFUSERS = '0.42.1'
OFFLOAD_MIN_AVAILABLE_BYTES = 18_000_000_000
RESIDENCIES = ('phase', 'offload')
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
TIED_TEXT_ENCODER_KEYS = ('lm_head.weight',)
HF_OFFLINE_ENV = {'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1', 'DO_NOT_TRACK': '1'}
# safetensors dtype -> (torch dtype name, bytes per element).
SAFETENSORS_DTYPES = {'F64': ('float64', 8), 'F32': ('float32', 4), 'F16': ('float16', 2), 'BF16': ('bfloat16', 2),
                      'I64': ('int64', 8), 'I32': ('int32', 4), 'I16': ('int16', 2), 'I8': ('int8', 1), 'U8': ('uint8', 1),
                      'BOOL': ('bool', 1), 'F8_E4M3': ('float8_e4m3fn', 1), 'F8_E5M2': ('float8_e5m2', 1)}
HEADER_MAX_BYTES = 100 * 1024 * 1024

# Process-wide state of the FP8 path: None until the transformer first loads, then 'tensorwise', 'dequantize' or 'native'.
FP8_STATE = {'path': None, 'detail': None, 'rel_err': None, 'capability': None, 'tested': False}
_UNIT_SCALES: dict = {}


class EngineError(Exception):
    """A phase the engine refuses to run (stable item error code and an English message)."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


class EngineUnavailable(EngineError):
    """The engine cannot run at all (no torch, no CUDA): the service goes to state 'error'."""

    def __init__(self, message: str):
        super().__init__(protocol.ENGINE_UNAVAILABLE, message)


class _Interrupted(Exception):
    pass


@dataclass(frozen=True)
class WorkItem:
    key: str
    caption: str
    width: int
    height: int
    steps: int
    seed: int


@dataclass
class ItemOutcome:
    key: str
    png: bytes | None = None
    error_code: str | None = None
    message: str | None = None
    fp8_path: str | None = None
    seconds: dict = field(default_factory=dict)


@dataclass
class CycleResult:
    outcomes: list
    interrupted: list
    stats: dict


def _describe(error: BaseException) -> str:
    text = ' '.join(str(error).split())
    return f'{type(error).__name__}: {text[:300]}'


def _is_oom_error(error: BaseException) -> bool:
    seen = set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        if type(error).__name__ == 'OutOfMemoryError' or 'out of memory' in str(error).lower():
            return True
        error = error.__cause__ or error.__context__
    return False


# ---------------------------------------------------------------------------------------------------------------------------
# safetensors without a memory map (stdlib header; torch only to place the bytes).

def read_safetensors_header(path: Path) -> tuple[int, dict]:
    """Returns (offset of the data block, {name: (dtype, shape, begin, end)}) after checking every entry against the file size."""
    path = Path(path)
    size = path.stat().st_size
    with path.open('rb') as handle:
        raw = handle.read(8)
        if len(raw) != 8:
            raise ValueError(f'{path.name}: shorter than a safetensors header')
        length = int.from_bytes(raw, 'little')
        if not 2 <= length <= HEADER_MAX_BYTES or 8 + length > size:
            raise ValueError(f'{path.name}: header length {length} is not valid')
        header = json.loads(handle.read(length).decode('utf-8'))
    if not isinstance(header, dict):
        raise ValueError(f'{path.name}: header is not an object')
    data_offset, entries = 8 + length, {}
    for name, spec in header.items():
        if name == '__metadata__':
            continue
        dtype, shape, offsets = spec.get('dtype'), spec.get('shape'), spec.get('data_offsets')
        if dtype not in SAFETENSORS_DTYPES:
            raise ValueError(f'{path.name}: {name} has unsupported dtype {dtype}')
        if not isinstance(shape, list) or not all(type(d) is int and d >= 0 for d in shape):
            raise ValueError(f'{path.name}: {name} has an invalid shape')
        if not isinstance(offsets, list) or len(offsets) != 2 or not all(type(o) is int for o in offsets):
            raise ValueError(f'{path.name}: {name} has invalid data_offsets')
        begin, end = offsets
        if begin < 0 or end - begin != math.prod(shape) * SAFETENSORS_DTYPES[dtype][1] or data_offset + end > size:
            raise ValueError(f'{path.name}: {name} offsets do not match its shape or the file size')
        entries[name] = (dtype, tuple(shape), begin, end)
    return data_offset, entries


def chunk_spans(total: int, chunk: int) -> list[tuple[int, int]]:
    """(start, length) pieces of at most `chunk` bytes covering `total` bytes."""
    if chunk <= 0:
        raise ValueError('chunk must be positive')
    return [(start, min(chunk, total - start)) for start in range(0, total, chunk)]


def stream_safetensors(paths, device, *, torch, cast=None, keys=None, chunk_bytes: int = STREAM_CHUNK_BYTES) -> dict:
    """Reads tensors from .safetensors files straight into tensors on `device`, through one reusable buffer of chunk_bytes
    (no memory map: a copy-on-write map of a whole file is charged to the process commit on Windows). Floating tensors are cast to
    `cast` on the device. `keys` limits the names read."""
    staging = window = None
    out: dict = {}
    on_cpu = torch.device(device).type == 'cpu'
    try:
        for path in paths:
            data_offset, entries = read_safetensors_header(Path(path))
            with open(path, 'rb', buffering=0) as handle:
                for name, (dtype, shape, begin, end) in sorted(entries.items(), key=lambda kv: kv[1][2]):
                    if keys is not None and name not in keys:
                        continue
                    tensor = torch.empty(shape, dtype=getattr(torch, SAFETENSORS_DTYPES[dtype][0]), device=device)
                    if end > begin:
                        flat = tensor.view(-1).view(torch.uint8)
                        if on_cpu:
                            target = memoryview(flat.numpy())
                        elif staging is None:
                            staging = torch.empty(chunk_bytes, dtype=torch.uint8)
                            window = memoryview(staging.numpy())
                        handle.seek(data_offset + begin)
                        for start, length in chunk_spans(end - begin, chunk_bytes):
                            done = 0
                            while done < length:
                                got = handle.readinto(target[start + done:start + length] if on_cpu else window[done:length])
                                if not got:
                                    raise EOFError(f'{Path(path).name}: {name} is truncated')
                                done += got
                            if not on_cpu:
                                flat[start:start + length].copy_(staging[:length])
                    if cast is not None and tensor.is_floating_point() and tensor.dtype != cast:
                        tensor = tensor.to(cast)
                    out[name] = tensor
    finally:
        window = staging = None
    return out


def assign_state(model, state: dict, allowed_missing=()) -> None:
    """Puts the streamed tensors into a model built on the meta device, without copying them."""
    result = model.load_state_dict(state, strict=False, assign=True)
    missing = sorted(set(result.missing_keys) - set(allowed_missing))
    if missing or result.unexpected_keys:
        raise RuntimeError(f'weights do not match the model: missing {missing[:5]}, unexpected {sorted(result.unexpected_keys)[:5]}')


def ensure_materialized(model, name: str) -> None:
    left = [n for n, t in list(model.named_parameters()) + list(model.named_buffers()) if t.is_meta]
    if left:
        raise RuntimeError(f'{name}: {len(left)} tensors still on the meta device, e.g. {left[:3]}')


def rebuild_buffers(model, device, *, torch) -> list[str]:
    """Buffers that are not in the weights (rotary inv_freq) were built on the meta device with the model: give them storage on
    `device` and compute the rotary ones again with the model's own _init_weights, as transformers' from_pretrained does after its
    meta initialisation."""
    rebuilt = []
    for name, buffer in list(model.named_buffers()):
        if buffer.is_meta:
            owner_name, _, attr = name.rpartition('.')
            owner = model.get_submodule(owner_name) if owner_name else model
            owner._buffers[attr] = torch.empty_like(buffer, device=device)
            rebuilt.append(name)
    for module in model.modules():
        if 'RotaryEmbedding' in type(module).__name__ and hasattr(module, 'original_inv_freq'):
            model._init_weights(module)
    return rebuilt


def residual_action(before_private: int | None, after_private: int | None) -> str:
    """After a phase is freed: 'ok', 'clean' (above FREE_TOLERANCE_BYTES: clean once more) or 'refuse' (above RESIDUAL_LIMIT_BYTES:
    a component's worth of private memory did not come back, so the next phase must not stack another one on top)."""
    if before_private is None or after_private is None:
        return 'ok'
    residual = after_private - before_private
    if residual > RESIDUAL_LIMIT_BYTES:
        return 'refuse'
    return 'clean' if residual > FREE_TOLERANCE_BYTES else 'ok'


# ---------------------------------------------------------------------------------------------------------------------------
# The cycle (pure Python; the backend does the GPU work).

def system_commit() -> dict | None:
    """System commit limit, available commit and available RAM (GlobalMemoryStatusEx; stdlib ctypes; None off Windows). On WDDM the
    GPU memory of a phase is charged to this commit, so a phase must not start when the machine is near its commit limit."""
    if sys.platform != 'win32':
        return None
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [('dwLength', ctypes.c_ulong), ('dwMemoryLoad', ctypes.c_ulong), ('ullTotalPhys', ctypes.c_ulonglong),
                    ('ullAvailPhys', ctypes.c_ulonglong), ('ullTotalPageFile', ctypes.c_ulonglong), ('ullAvailPageFile', ctypes.c_ulonglong),
                    ('ullTotalVirtual', ctypes.c_ulonglong), ('ullAvailVirtual', ctypes.c_ulonglong), ('ullAvailExtendedVirtual', ctypes.c_ulonglong)]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(MemoryStatus)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    limit, available = int(status.ullTotalPageFile), int(status.ullAvailPageFile)
    return {'limit_bytes': limit, 'available_bytes': available, 'used_bytes': limit - available, 'ram_available_bytes': int(status.ullAvailPhys)}


def memory_budget(cycle_stats: list, peaks: dict) -> dict:
    """Control's budget (02/11/2026): peak working set <= BUDGET_WSET_MAX_BYTES, peak (private - GPU reserved, same sample) <=
    BUDGET_HOST_PRIVATE_MAX_BYTES, residual after a phase is freed <= RESIDUAL_LIMIT_BYTES in the first cycle and <=
    STEADY_RESIDUAL_MAX_BYTES in later ones. The raw private peak is reported only: WDDM charges device memory to the process commit.
    cycle_stats: run_cycle stats per cycle; peaks: peak_wset_bytes, peak_private_minus_gpu_bytes, peak_private_bytes."""
    residuals = [{phase: (stats.get(phase) or {}).get('residual_private_bytes') for phase in PHASES if phase in stats} for stats in cycle_stats]
    first = residuals[0] if residuals else {}
    later = [value for cycle in residuals[1:] for value in cycle.values()]
    wset, host = peaks.get('peak_wset_bytes'), peaks.get('peak_private_minus_gpu_bytes')
    ok = {
        'peak_wset': wset is not None and wset <= BUDGET_WSET_MAX_BYTES,
        'peak_private_minus_gpu': host is not None and host <= BUDGET_HOST_PRIVATE_MAX_BYTES,
        'first_cycle_residual': bool(first) and all(v is not None and v <= RESIDUAL_LIMIT_BYTES for v in first.values()),
        'steady_residual': (all(v is not None and v <= STEADY_RESIDUAL_MAX_BYTES for v in later) if later else None),
    }
    return {'ok': ok, 'passed': all(value is not False for value in ok.values()),
            'figures': {'peak_wset_bytes': wset, 'peak_private_minus_gpu_bytes': host, 'peak_private_bytes': peaks.get('peak_private_bytes'),
                        'residuals': residuals}}


def _wait_for_room(backend, phase, on_state, stopping, sleep, clock, max_wait, record):
    """None when the phase may load, else (code, message) after max_wait: free VRAM >= requirement + VRAM margin and, when the backend
    can tell, available system commit >= PHASE_COMMIT_BYTES + COMMIT_MARGIN_BYTES and available RAM >= HOST_MIN_AVAILABLE_BYTES."""
    need = backend.requirement(phase) + VRAM_MARGIN_BYTES
    need_commit = PHASE_COMMIT_BYTES[phase] + COMMIT_MARGIN_BYTES
    host_available = getattr(backend, 'host_available', None)
    commit_available = getattr(backend, 'commit_available', None)
    started = clock()
    waited = None
    while True:
        free = backend.free_vram()
        commit = commit_available() if commit_available is not None else None
        host = host_available() if host_available is not None else None
        vram_ok = free is None or free >= need
        commit_ok = commit is None or commit >= need_commit
        host_ok = host is None or host >= HOST_MIN_AVAILABLE_BYTES
        if vram_ok and commit_ok and host_ok:
            record['free_before_bytes'] = free
            if commit is not None:
                record['commit_available_before_bytes'] = commit
            if host is not None:
                record['host_available_before_bytes'] = host
            if waited:
                record['waited_seconds'] = round(clock() - started, 1)
            return None
        if clock() - started >= max_wait:
            record['free_before_bytes'] = free
            if not vram_ok:
                return protocol.GPU_MEMORY_UNAVAILABLE, f'{phase}: free VRAM stayed below {need} bytes for {max_wait:.0f} s'
            if not commit_ok:
                return protocol.HOST_COMMIT_LOW, f'{phase}: available system commit stayed below {need_commit} bytes for {max_wait:.0f} s'
            return protocol.HOST_MEMORY_LOW, f'{phase}: available RAM stayed below {HOST_MIN_AVAILABLE_BYTES} bytes for {max_wait:.0f} s'
        if stopping():
            raise _Interrupted()
        reason = 'vram' if not vram_ok else 'commit' if not commit_ok else 'ram'
        if waited != reason:
            on_state('busy', f'waiting_{reason}:{phase}')
            waited = reason
        sleep(VRAM_POLL_SECONDS)


def _run_phase(backend, phase, items, step, fail, outcomes, stats, on_state, stopping, sleep, clock, max_wait):
    """Runs step(item) for every item with the phase's model loaded; returns the items that succeeded. An out-of-memory error frees
    the model and retries the remaining items once (after the gate again); a second one fails them with GPU_OUT_OF_MEMORY.
    Any other error in a step fails only that item (GENERATION_FAILED); a failed load fails them all (MODEL_LOAD_FAILED)."""
    remaining = list(items)
    succeeded = []
    record = stats.setdefault(phase, {'items': 0, 'loads': 0, 'oom_retries': 0})
    oom_retried = False
    while remaining:
        if stopping():
            raise _Interrupted()
        blocked = _wait_for_room(backend, phase, on_state, stopping, sleep, clock, max_wait, record)
        if blocked is not None:
            for item in remaining:
                fail(item, *blocked)
            return succeeded
        oom_message = None
        loaded = False
        try:
            on_state('loading', phase)
            started = clock()
            info = backend.load(phase)
            loaded = True
            record['loads'] += 1
            record['load_seconds'] = round(clock() - started, 2)
            if isinstance(info, dict):
                record.update(info)
            on_state('busy', phase)
            while remaining:
                if stopping():
                    raise _Interrupted()
                item = remaining[0]
                began = clock()
                try:
                    step(item)
                except (_Interrupted, EngineUnavailable):
                    raise
                except Exception as error:
                    if backend.is_oom(error):
                        raise
                    fail(item, protocol.GENERATION_FAILED, f'{phase}: {_describe(error)}')
                else:
                    outcomes[item.key].seconds[phase] = round(clock() - began, 2)
                    succeeded.append(item)
                remaining.pop(0)
        except (_Interrupted, EngineUnavailable):
            raise
        except EngineError as error:
            for item in remaining:
                fail(item, error.code, f'{phase}: {error.message}')
            remaining = []
        except Exception as error:
            if backend.is_oom(error):
                oom_message = f'{phase}: {_describe(error)}'
            else:
                code = protocol.GENERATION_FAILED if loaded else protocol.MODEL_LOAD_FAILED
                for item in remaining:
                    fail(item, code, f'{phase}: {_describe(error)}')
                remaining = []
        finally:
            try:
                info = backend.unload(phase)
            except Exception:
                info = None
            if info:
                record.update(info)
        if oom_message is not None:
            if oom_retried:
                for item in remaining:
                    fail(item, protocol.GPU_OUT_OF_MEMORY, oom_message)
                break
            oom_retried = True
            record['oom_retries'] += 1
    record['items'] += len(succeeded)
    return succeeded


def run_cycle(backend, items, *, on_state=None, stopping=None, sleep=time.sleep, clock=time.monotonic,
              vram_wait_max=VRAM_WAIT_MAX_SECONDS) -> CycleResult:
    """Takes the batch through text encoder -> transformer -> VAE. Returns one outcome per item (PNG bytes or an error code); items
    still unfinished when stopping() turns true are listed in `interrupted` (the server queues them again). EngineUnavailable
    propagates: the service cannot generate at all."""
    on_state = on_state or (lambda state, phase: None)
    stopping = stopping or (lambda: False)
    items = list(items)
    outcomes = {item.key: ItemOutcome(item.key) for item in items}
    stats: dict = {}
    embeds: dict = {}
    latents: dict = {}

    def fail(item, code, message):
        outcomes[item.key].error_code = code
        outcomes[item.key].message = message[:500]
        embeds.pop(item.key, None)
        latents.pop(item.key, None)

    def encode(item):
        embeds[item.key] = backend.encode(item)

    def denoise(item):
        latents[item.key] = backend.denoise(item, embeds[item.key])
        del embeds[item.key]
        outcomes[item.key].fp8_path = backend.fp8_path()

    def decode(item):
        png = backend.decode(item, latents[item.key])
        if not isinstance(png, (bytes, bytearray)) or not bytes(png[:8]) == PNG_SIGNATURE:
            raise ValueError('the decoder did not return PNG bytes')
        outcomes[item.key].png = bytes(png)
        del latents[item.key]

    started = clock()
    pending = items
    try:
        for phase, step in (('text_encoder', encode), ('transformer', denoise), ('vae', decode)):
            pending = _run_phase(backend, phase, pending, step, fail, outcomes, stats, on_state, stopping, sleep, clock, vram_wait_max)
            if not pending:
                break
    except _Interrupted:
        pass
    stats['cycle_seconds'] = round(clock() - started, 2)
    interrupted = [item.key for item in items if outcomes[item.key].png is None and outcomes[item.key].error_code is None]
    return CycleResult([outcomes[item.key] for item in items], interrupted, stats)


# ---------------------------------------------------------------------------------------------------------------------------
# FP8 on Ada.

def _tensorwise_matmul(layer, inputs):
    import torch
    from diffusers.quantizers.bfl import utils as bfl
    x = inputs.reshape(-1, layer.in_features).float()
    x_scale = (x.abs().amax(dim=1, keepdim=True) / bfl.FP8_MAX).clamp(min=1e-12)
    x_q = (x / x_scale).clamp(-bfl.FP8_MAX, bfl.FP8_MAX).to(torch.float8_e4m3fn)
    one = _UNIT_SCALES.get(inputs.device)
    if one is None:
        one = _UNIT_SCALES[inputs.device] = torch.ones((), device=inputs.device, dtype=torch.float32)
    out = torch._scaled_mm(x_q, layer.weight.T, one, one, out_dtype=torch.float32)
    out = (out * x_scale * layer.weight_scale[None, :]).to(layer.compute_dtype)
    out = out.reshape(*inputs.shape[:-1], layer.out_features)
    return out + layer.bias if layer.bias is not None else out


def _dequantized_matmul(layer, inputs):
    import torch
    from diffusers.quantizers.bfl import utils as bfl
    weight = bfl.dequantize_fp8r(layer.weight, layer.weight_scale).to(layer.compute_dtype)
    return torch.nn.functional.linear(inputs, weight, layer.bias)


def _fall_back(detail: str) -> None:
    FP8_STATE.update(path='dequantize', detail=detail[:300])


def _patched_forward(self, inputs):
    if FP8_STATE['path'] == 'tensorwise' and inputs.is_cuda and self.in_features % 16 == 0 and self.out_features % 16 == 0:
        try:
            return _tensorwise_matmul(self, inputs)
        except RuntimeError as error:
            if _is_oom_error(error):
                raise
            _fall_back(f'RuntimeError in the tensorwise FP8 GEMM: {_describe(error)}')
    return _dequantized_matmul(self, inputs)


def patch_bfl_fp8(torch) -> str:
    """Replaces BFLFP8RLinear.forward only on compute capability (8, 9) with diffusers 0.42.1; elsewhere the library forward stays."""
    if FP8_STATE['path'] is not None:
        return FP8_STATE['path']
    import diffusers
    from diffusers.quantizers.bfl import utils as bfl
    capability = tuple(torch.cuda.get_device_capability())
    FP8_STATE['capability'] = list(capability)
    if capability != FP8_PATCH_CAPABILITY or diffusers.__version__ != FP8_PATCH_DIFFUSERS:
        FP8_STATE.update(path='native', detail=f'capability {capability}, diffusers {diffusers.__version__}: library forward kept')
        return 'native'
    bfl.BFLFP8RLinear.forward = _patched_forward
    FP8_STATE.update(path='tensorwise', detail='patched; self-test pending')
    return 'tensorwise'


def fp8_self_test(layer, torch) -> str:
    """Compares the tensorwise GEMM of one BFLFP8RLinear layer with dequantisation on a seeded input; on a mismatch above
    FP8_SELFTEST_MAX_REL_ERR, a non-finite result or a RuntimeError the process switches to dequantisation. Runs once."""
    if FP8_STATE['path'] != 'tensorwise' or FP8_STATE['tested']:
        return FP8_STATE['path']
    FP8_STATE['tested'] = True
    dtype = layer.compute_dtype or torch.bfloat16
    generator = torch.Generator(device=layer.weight.device).manual_seed(0)
    x = torch.randn((64, layer.in_features), generator=generator, device=layer.weight.device, dtype=torch.float32).to(dtype)
    with torch.no_grad():
        try:
            got = _tensorwise_matmul(layer, x).float()
        except RuntimeError as error:
            if _is_oom_error(error):
                FP8_STATE['tested'] = False
                raise
            _fall_back(f'self-test RuntimeError: {_describe(error)}')
            return FP8_STATE['path']
        want = _dequantized_matmul(layer, x).float()
        rel = float(((got - want).norm() / want.norm().clamp(min=1e-12)).item())
    FP8_STATE['rel_err'] = round(rel, 5) if math.isfinite(rel) else None
    if not math.isfinite(rel) or rel > FP8_SELFTEST_MAX_REL_ERR:
        _fall_back(f'self-test relative error {rel:.4f} above {FP8_SELFTEST_MAX_REL_ERR}')
    else:
        FP8_STATE['detail'] = f'self-test passed (relative error {rel:.4f})'
    return FP8_STATE['path']


def _synthetic_fp8_layer(torch, device):
    from diffusers.quantizers.bfl import utils as bfl
    generator = torch.Generator(device=device).manual_seed(1)
    weight = torch.randn((3072, 3072), generator=generator, device=device, dtype=torch.float32) * 0.02
    layer = bfl.BFLFP8RLinear(3072, 3072, bias=True, compute_dtype=torch.bfloat16, device=device)
    weight_q, weight_scale = bfl.quantize_fp8r(weight)
    layer.weight = torch.nn.Parameter(weight_q, requires_grad=False)
    layer.weight_scale = weight_scale
    layer.bias = torch.nn.Parameter(torch.zeros(3072, device=device, dtype=torch.bfloat16), requires_grad=False)
    return layer


# ---------------------------------------------------------------------------------------------------------------------------
# Memory of the sidecar process.

class MemoryProbe:
    """Private commit and working set of this process (psutil, in the sidecar env) and the GPU caching allocator. Between begin() and
    end() it samples every MEMORY_SAMPLE_SECONDS the private commit, the working set and the private commit minus torch's reserved
    GPU memory read in the same sample (WDDM charges device memory to the process commit); it also keeps the process-lifetime
    peak of that difference."""

    def __init__(self, torch=None, interval: float = MEMORY_SAMPLE_SECONDS):
        import psutil
        self._psutil = psutil
        self._process = psutil.Process()
        self._torch = torch
        self._interval = interval
        self._lock = threading.Lock()
        self._active = threading.Event()
        self._phase = None
        self._lifetime_host = None
        threading.Thread(target=self._sample, name='imagegen-memory', daemon=True).start()

    def private(self) -> int:
        info = self._process.memory_info()
        return int(getattr(info, 'private', info.rss))

    def host_available(self) -> int:
        return int(self._psutil.virtual_memory().available)

    def _reserved(self) -> int:
        torch = self._torch
        return int(torch.cuda.memory_reserved()) if torch is not None and torch.cuda.is_initialized() else 0

    def host_private(self) -> tuple[int, int, int]:
        """(private, working set, private - reserved). Reserved is read before and after the private read and the larger is used, so
        an allocation landing between the reads never shows up as host memory."""
        before = self._reserved()
        info = self._process.memory_info()
        reserved = max(before, self._reserved())
        private = int(getattr(info, 'private', info.rss))
        return private, int(info.rss), private - reserved

    def snapshot(self) -> dict:
        info = self._process.memory_info()
        snap = {'private_bytes': int(getattr(info, 'private', info.rss)), 'rss_bytes': int(info.rss)}
        torch = self._torch
        if torch is not None and torch.cuda.is_initialized():
            snap['gpu_allocated_bytes'] = int(torch.cuda.memory_allocated())
            snap['gpu_reserved_bytes'] = int(torch.cuda.memory_reserved())
        return snap

    def _record(self, private: int, rss: int, host: int) -> None:
        with self._lock:
            phase = self._phase
            if phase is not None:
                phase['private'] = max(phase['private'], private)
                phase['rss'] = max(phase['rss'], rss)
                phase['host'] = max(phase['host'], host)
            self._lifetime_host = host if self._lifetime_host is None else max(self._lifetime_host, host)

    def begin(self) -> None:
        private, rss, host = self.host_private()
        with self._lock:
            self._phase = {'private': private, 'rss': rss, 'host': host}
        self._record(private, rss, host)
        self._active.set()

    def end(self) -> dict:
        self._active.clear()
        self._record(*self.host_private())
        with self._lock:
            phase, self._phase = self._phase, None
        if phase is None:
            return {}
        return {'peak_private_bytes_phase': phase['private'], 'peak_rss_bytes_phase': phase['rss'],
                'peak_private_minus_gpu_bytes_phase': phase['host']}

    def peaks(self) -> dict:
        info = self._process.memory_info()
        with self._lock:
            host = self._lifetime_host
        return {'peak_wset_bytes': getattr(info, 'peak_wset', None), 'peak_private_bytes': getattr(info, 'peak_pagefile', None),
                'peak_private_minus_gpu_bytes': host}

    def _sample(self) -> None:
        while True:
            self._active.wait()
            try:
                private, rss, host = self.host_private()
                if self._lifetime_host is not None and host > self._lifetime_host:
                    # A new high is read once more: a transient skew between the two counters must not set the peak.
                    time.sleep(0.005)
                    again = self.host_private()
                    host = min(host, again[2])
                self._record(private, rss, host)
            except Exception:
                pass
            time.sleep(self._interval)


# ---------------------------------------------------------------------------------------------------------------------------
# The real backend.

class KleinBackend:
    """FLUX 3 Image Klein (distilled) through the diffusers 0.42.1 modular FLUX.3 blocks without the prompt upsampler: the
    captions come complete from the caption writer. residency='phase' keeps one model on the GPU at a time; 'offload' is the
    prototype's auto CPU offload and needs OFFLOAD_MIN_AVAILABLE_BYTES of available RAM."""

    def __init__(self, snapshot: Path, *, residency: str = 'phase', device: str = 'cuda'):
        if residency not in RESIDENCIES:
            raise ValueError(f'residency must be one of {RESIDENCIES}')
        self.snapshot = Path(snapshot)
        self.residency = residency
        self.device = device
        self._torch = None
        self._blocks = None
        self._memory = None
        self._pipes: dict = {}
        self._manager = None
        self._before_load_private = None
        self._residual = None

    def describe(self) -> dict:
        return {'residency': self.residency, 'device': self.device, 'snapshot': str(self.snapshot)}

    def _setup(self):
        if self._torch is not None:
            return self._torch
        try:
            import torch
            from diffusers import Flux3DistilledAutoBlocks
            if not torch.cuda.is_available():
                raise EngineUnavailable('CUDA is not available')
            blocks = Flux3DistilledAutoBlocks()
            # Captions are written in full by the caption writer (Klein README "Prompt upsampling"): encode them as given.
            blocks.sub_blocks.pop('prompt_upsampler', None)
            patch_bfl_fp8(torch)
            memory = MemoryProbe(torch)
        except EngineUnavailable:
            raise
        except Exception as error:
            raise EngineUnavailable(f'cannot set up the image stack: {_describe(error)}') from None
        self._blocks = blocks
        self._memory = memory
        self._torch = torch
        return torch

    def requirement(self, phase: str) -> int:
        return PHASE_REQUIREMENT_BYTES[phase]

    def free_vram(self) -> int:
        torch = self._setup()
        device = torch.device(self.device)
        free, _total = torch.cuda.mem_get_info(device)
        if self.residency == 'offload':
            # The components manager moves this process's own models off the GPU when a phase needs the room.
            free += torch.cuda.memory_reserved(device)
        return int(free)

    def host_available(self) -> int | None:
        return self._memory.host_available() if self._memory is not None else None

    def commit_available(self) -> int | None:
        commit = system_commit()
        return None if commit is None else commit['available_bytes']

    def memory(self) -> dict | None:
        """Current private, working set and GPU memory, with the process-lifetime peaks the budget is judged on."""
        if self._memory is None:
            return None
        return dict(self._memory.snapshot(), **self._memory.peaks())

    def is_oom(self, error: BaseException) -> bool:
        return _is_oom_error(error)

    def fp8_path(self):
        return FP8_STATE['path']

    def _load_spec(self, pipe, name: str, **kwargs):
        # ComponentSpec.load raises (load_components only logs), so an out-of-memory error reaches the retry.
        component = pipe.get_component_spec(name).load(**kwargs)
        pipe.update_components(**{name: component})
        if getattr(pipe, name, None) is None:
            raise RuntimeError(f'{name} did not load')

    def _free(self) -> dict:
        torch = self._torch
        gc.collect()
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
        return self._memory.snapshot()

    def _load_text_encoder(self, device):
        torch = self._torch
        from transformers import AutoConfig, Qwen3VLForConditionalGeneration
        folder = self.snapshot / 'text_encoder'
        index = json.loads((folder / 'model.safetensors.index.json').read_text(encoding='utf-8'))['weight_map']
        config = AutoConfig.from_pretrained(str(folder))
        # Built on the meta device: no parameter is ever allocated in RAM (accelerate's init_empty_weights would allocate each
        # one on the CPU first, 742 MiB for embed_tokens).
        with torch.device('meta'):
            model = Qwen3VLForConditionalGeneration._from_config(config, dtype=torch.bfloat16)
        state = stream_safetensors([folder / name for name in sorted(set(index.values()))], device, torch=torch)
        if set(state) != set(index):
            raise RuntimeError('the text encoder shards do not hold the tensors their index lists')
        assign_state(model, state, allowed_missing=TIED_TEXT_ENCODER_KEYS)
        state.clear()
        model.tie_weights()
        rebuild_buffers(model, device, torch=torch)
        ensure_materialized(model, 'text_encoder')
        model.eval()
        return model

    def _load_transformer(self, device):
        torch = self._torch
        from diffusers.models.transformers.transformer_flux3 import Flux3Transformer2DModel
        from diffusers.quantizers.quantization_config import BFLQuantizationConfig
        state = stream_safetensors([self.snapshot / 'variants' / 'fp8r' / 'model.safetensors'], device, torch=torch)
        # from_single_file takes a state dict as is: the BFL quantizer wraps the fp8 weights and the BFL key renaming runs on the
        # device, with no second copy.
        model = Flux3Transformer2DModel.from_single_file(
            state, config=str(self.snapshot), subfolder='transformer',
            quantization_config=BFLQuantizationConfig(compute_dtype=torch.bfloat16),
            torch_dtype=torch.bfloat16, device=device,
        )
        state.clear()
        ensure_materialized(model, 'transformer')
        return model

    def _load_vae(self, device):
        torch = self._torch
        from diffusers import AutoencoderKLFlux2
        folder = self.snapshot / 'vae'
        config = AutoencoderKLFlux2.load_config(str(folder))
        with torch.device('meta'):
            vae = AutoencoderKLFlux2.from_config(config)
        # The file holds float32 weights and BatchNorm statistics: cast on the device to bfloat16, as the prototype loaded them.
        state = stream_safetensors([folder / 'diffusion_pytorch_model.safetensors'], device, torch=torch, cast=torch.bfloat16)
        assign_state(vae, state)
        state.clear()
        rebuild_buffers(vae, device, torch=torch)
        ensure_materialized(vae, 'vae')
        vae.eval()
        return vae

    def _first_fp8_layer(self, model):
        from diffusers.quantizers.bfl import utils as bfl
        return next((m for m in model.modules() if isinstance(m, bfl.BFLFP8RLinear)), None)

    def load(self, phase: str) -> dict:
        torch = self._setup()
        if self._residual is not None:
            again = self._free()
            if residual_action(self._before_load_private, again['private_bytes']) == 'refuse':
                raise EngineError(protocol.HOST_MEMORY_LOW, f'private memory stayed {again["private_bytes"] - self._before_load_private} '
                                  f'bytes above its level before the previous phase; {phase} is not loaded on top of it')
            self._residual = None
        torch.cuda.reset_peak_memory_stats()
        before = self._memory.snapshot()
        self._before_load_private = before['private_bytes']
        self._memory.begin()
        started = time.monotonic()
        if self.residency == 'offload':
            self._load_offload()
        else:
            blocks = self._blocks
            if phase == 'text_encoder':
                pipe = blocks.sub_blocks['text_encoder'].init_pipeline(str(self.snapshot))
                self._load_spec(pipe, 'tokenizer')
                pipe.update_components(text_encoder=self._load_text_encoder(self.device))
            elif phase == 'transformer':
                transformer = self._load_transformer(self.device)
                layer = self._first_fp8_layer(transformer)
                if layer is not None:
                    fp8_self_test(layer, torch)
                pipe = blocks.sub_blocks['denoise'].init_pipeline()
                pipe.update_components(transformer=transformer)
            elif phase == 'vae':
                pipe = blocks.sub_blocks['decode'].init_pipeline()
                pipe.update_components(vae=self._load_vae(self.device))
            else:
                raise ValueError(f'unknown phase {phase}')
            self._pipes[phase] = pipe
        return {'stream_seconds': round(time.monotonic() - started, 2), 'memory_before_load': before,
                'memory_after_load': self._memory.snapshot()}

    def _load_offload(self) -> None:
        if self._pipes:
            return
        available = self._memory.host_available()
        if available < OFFLOAD_MIN_AVAILABLE_BYTES:
            raise EngineError(protocol.HOST_MEMORY_LOW, f'{available} bytes of RAM available; offload residency needs {OFFLOAD_MIN_AVAILABLE_BYTES}')
        torch = self._torch
        from diffusers.modular_pipelines import ComponentsManager
        manager = ComponentsManager()
        manager.enable_auto_cpu_offload(device=self.device, memory_reserve_margin='2GB')
        blocks = self._blocks
        te = blocks.sub_blocks['text_encoder'].init_pipeline(str(self.snapshot), components_manager=manager)
        self._load_spec(te, 'tokenizer')
        te.update_components(text_encoder=self._load_text_encoder('cpu'))
        den = blocks.sub_blocks['denoise'].init_pipeline(components_manager=manager)
        den.update_components(transformer=self._load_transformer('cpu'))
        fp8_self_test(_synthetic_fp8_layer(torch, self.device), torch)
        dec = blocks.sub_blocks['decode'].init_pipeline(components_manager=manager)
        dec.update_components(vae=self._load_vae('cpu'))
        self._manager = manager
        self._pipes = {'text_encoder': te, 'transformer': den, 'vae': dec}

    def unload(self, phase: str) -> dict | None:
        torch = self._torch
        if torch is None:
            return None
        info = {'peak_allocated_bytes': int(torch.cuda.max_memory_allocated()), 'peak_reserved_bytes': int(torch.cuda.max_memory_reserved()),
                'memory_after_phase': self._memory.snapshot(), **self._memory.end()}
        if self.residency == 'phase':
            self._pipes.pop(phase, None)
        after = self._free()
        action = residual_action(self._before_load_private, after['private_bytes'])
        if action != 'ok' and self.residency == 'phase':
            after = self._free()
            action = residual_action(self._before_load_private, after['private_bytes'])
        info['memory_after_free'] = after
        if self._before_load_private is not None:
            info['residual_private_bytes'] = after['private_bytes'] - self._before_load_private
        # Offload keeps every component in RAM on purpose; only phase residency must give its component back.
        self._residual = info.get('residual_private_bytes') if action == 'refuse' and self.residency == 'phase' else None
        torch.cuda.reset_peak_memory_stats()
        return info

    def release(self) -> None:
        """Drops every model (idle for IDLE_UNLOAD_SECONDS, or stopping)."""
        self._pipes = {}
        self._manager = None
        if self._torch is not None:
            gc.collect()
            self._torch.cuda.empty_cache()

    def encode(self, item: WorkItem):
        embeds = self._pipes['text_encoder'](prompt=item.caption, output='prompt_embeds')
        return embeds.to('cpu')

    def denoise(self, item: WorkItem, embeds):
        torch = self._torch
        generator = torch.Generator().manual_seed(item.seed)
        latents = self._pipes['transformer'](prompt_embeds=embeds.to(self.device), height=item.height, width=item.width,
                                            num_inference_steps=item.steps, generator=generator, output='latents')
        return latents.to('cpu')

    def decode(self, item: WorkItem, latents) -> bytes:
        images = self._pipes['vae'](latents=latents.to(self.device), output_type='pil', output='images')
        image = images[0]
        if tuple(image.size) != (item.width, item.height):
            raise ValueError(f'decoded {image.size}, expected {(item.width, item.height)}')
        buffer = io.BytesIO()
        image.save(buffer, format='PNG')
        return buffer.getvalue()


# ---------------------------------------------------------------------------------------------------------------------------
# GPU memory for /v1/health without a CUDA context: nvidia-smi, cached.

def gpu_memory(run=subprocess.run) -> dict | None:
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
    try:
        done = run(['nvidia-smi', '--query-gpu=memory.free,memory.total', '--format=csv,noheader,nounits'],
                   capture_output=True, text=True, timeout=5, creationflags=flags)
    except (OSError, subprocess.SubprocessError):
        return None
    if done.returncode != 0 or not done.stdout.strip():
        return None
    try:
        free, total = (int(part.strip()) for part in done.stdout.strip().splitlines()[0].split(','))
    except ValueError:
        return None
    return {'free_bytes': free * 1024 * 1024, 'total_bytes': total * 1024 * 1024}


class CachedGpuMemory:
    def __init__(self, probe=gpu_memory, ttl: float = 5.0, clock=time.monotonic):
        self._probe, self._ttl, self._clock = probe, ttl, clock
        self._value, self._at = None, None
        self._lock = threading.Lock()

    def __call__(self):
        with self._lock:
            now = self._clock()
            if self._at is None or now - self._at >= self._ttl:
                self._value, self._at = self._probe(), now
            return self._value


def set_offline_env(hub: Path | None = None) -> None:
    """Never download: the sidecar only reads the pinned, verified cache."""
    os.environ.update(HF_OFFLINE_ENV)
    if hub is not None:
        os.environ['HF_HUB_CACHE'] = str(hub)


# ---------------------------------------------------------------------------------------------------------------------------
# Measurement on the GPU (Control only): one cycle through the same run_cycle as the server, with VRAM, memory and timings.

class _RssSampler(threading.Thread):
    def __init__(self, interval: float = 0.25):
        super().__init__(daemon=True)
        import psutil
        self._process = psutil.Process()
        self._psutil = psutil
        self._interval = interval
        self._halt = threading.Event()
        self.peak_rss = 0
        self.min_available = None

    def run(self):
        while not self._halt.is_set():
            self.peak_rss = max(self.peak_rss, self._process.memory_info().rss)
            available = self._psutil.virtual_memory().available
            self.min_available = available if self.min_available is None else min(self.min_available, available)
            self._halt.wait(self._interval)

    def stop(self) -> dict:
        self._halt.set()
        self.join(timeout=2)
        info = self._process.memory_info()
        # Private commit (peak_pagefile) is what can run the machine out of memory; the working set also counts file pages.
        return {'peak_rss_bytes': max(self.peak_rss, info.rss), 'peak_wset_bytes': getattr(info, 'peak_wset', None),
                'private_bytes': getattr(info, 'private', None), 'peak_private_bytes': getattr(info, 'peak_pagefile', None),
                'min_available_bytes': self.min_available}


def _phase_memory_lines(stats: dict) -> list[str]:
    lines = []
    gib = 1024 ** 3
    for phase in PHASES:
        record = stats.get(phase) or {}
        row = [phase]
        for key in ('memory_before_load', 'memory_after_load', 'memory_after_phase', 'memory_after_free'):
            snap = record.get(key) or {}
            if snap.get('private_bytes') is not None:
                row.append(f"{key[7:]} private {snap['private_bytes'] / gib:.2f} GiB gpu_reserved {snap.get('gpu_reserved_bytes', 0) / gib:.2f} GiB")
        if record.get('peak_private_bytes_phase') is not None:
            row.append(f"peak private {record['peak_private_bytes_phase'] / gib:.2f} GiB")
        if record.get('peak_private_minus_gpu_bytes_phase') is not None:
            row.append(f"peak private-gpu {record['peak_private_minus_gpu_bytes_phase'] / gib:.2f} GiB")
        if record.get('peak_rss_bytes_phase') is not None:
            row.append(f"peak wset {record['peak_rss_bytes_phase'] / gib:.2f} GiB")
        if record.get('commit_available_before_bytes') is not None:
            row.append(f"commit available {record['commit_available_before_bytes'] / gib:.1f} GiB")
        if record.get('residual_private_bytes') is not None:
            row.append(f"residual {record['residual_private_bytes'] / gib:+.2f} GiB")
        lines.append(' | '.join(row))
    return lines


def _measure(args) -> int:
    from imagegen import weights
    hub = Path(args.hub)
    set_offline_env(hub)
    manifest = weights.load_manifest(Path(args.manifest))
    if not args.skip_verify:
        check = weights.verify(hub, manifest, full=False, write=False)
        if not check.ok:
            print(json.dumps({'not_provisioned': check.problems()}, ensure_ascii=False, indent=1))
            return 2
    entries = json.loads(Path(args.captions).read_text(encoding='utf-8'))
    items = []
    for index, entry in enumerate(entries):
        ident = str(entry.get('id', index)) if isinstance(entry, dict) else str(index)
        caption = entry[args.caption_field] if isinstance(entry, dict) else str(entry)
        if args.strip_canvas_line and caption.startswith('TARGET CANVAS:'):
            caption = caption.split('\n', 1)[1] if '\n' in caption else ''
        items.append(WorkItem(ident, caption, args.width, args.height, args.steps, args.seed))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    sampler = _RssSampler()
    sampler.start()
    backend = KleinBackend(weights.snapshot_dir(hub, protocol.MODEL_REPO, protocol.MODEL_REVISION), residency=args.residency)
    states = []
    started = time.monotonic()
    results = []
    try:
        backend.free_vram()  # imports torch and diffusers and creates the CUDA context once, as the server's first cycle does
        setup_seconds = round(time.monotonic() - started, 1)
        setup_memory = backend.memory()
        for cycle in range(args.cycles):
            print(f'cycle {cycle + 1} of {args.cycles}', flush=True)
            results.append(run_cycle(backend, items, on_state=lambda state, phase: (
                states.append([round(time.monotonic() - started, 1), state, phase]), print(f'{state} {phase}', flush=True))))
    except EngineUnavailable as error:
        sampler.stop()
        print(json.dumps({'engine_unavailable': error.message}, ensure_ascii=False))
        return 3
    memory = sampler.stop()
    peaks = backend.memory() or {}
    budget = memory_budget([r.stats for r in results], {**peaks, 'peak_wset_bytes': memory.get('peak_wset_bytes'),
                                                         'peak_private_bytes': memory.get('peak_private_bytes')})
    torch = backend._torch
    result = results[0]
    report = {'gpu': torch.cuda.get_device_name(0) if torch else None, 'residency': args.residency, 'width': args.width,
              'height': args.height, 'steps': args.steps, 'seed': args.seed, 'strip_canvas_line': args.strip_canvas_line,
              'cycles': args.cycles, 'setup_seconds': setup_seconds, 'setup_memory': setup_memory, 'fp8': dict(FP8_STATE),
              'phases': result.stats, 'later_cycles': [r.stats for r in results[1:]], 'memory': memory, 'memory_peaks': peaks,
              'commit': system_commit(), 'budget': budget, 'states': states, 'items': []}
    for item, outcome in zip(items, result.outcomes):
        row = {'id': item.key, 'error': outcome.error_code, 'message': outcome.message, 'fp8_path': outcome.fp8_path, 'seconds': outcome.seconds}
        if outcome.png is not None:
            (out / f'{item.key}.png').write_bytes(outcome.png)
            row['sha256'] = hashlib.sha256(outcome.png).hexdigest()
        report['items'].append(row)
    done = sum(1 for o in result.outcomes if o.png is not None)
    all_done = all(o.png is not None for r in results for o in r.outcomes)
    report['seconds_per_image'] = round(result.stats.get('cycle_seconds', 0) / done, 1) if done else None
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    for number, cycle_result in enumerate(results, 1):
        for line in _phase_memory_lines(cycle_result.stats):
            print(f'cycle {number} {line}', flush=True)
    gib = 1024 ** 3
    figures = budget['figures']
    for name, value, limit in (('peak working set', figures['peak_wset_bytes'], BUDGET_WSET_MAX_BYTES),
                               ('peak private - gpu reserved', figures['peak_private_minus_gpu_bytes'], BUDGET_HOST_PRIVATE_MAX_BYTES)):
        verdict = 'PASS' if value is not None and value <= limit else 'FAIL'
        print(f"budget {name}: {verdict} {(value or 0) / gib:.2f} GiB <= {limit / gib:.2f} GiB", flush=True)
    print(f"budget first-cycle residual: {'PASS' if budget['ok']['first_cycle_residual'] else 'FAIL'} (<= {RESIDUAL_LIMIT_BYTES / gib:.2f} GiB)", flush=True)
    steady = budget['ok']['steady_residual']
    print(f"budget steady residual: {'not measured (use --cycles 2)' if steady is None else 'PASS' if steady else 'FAIL'} "
          f"(<= {STEADY_RESIDUAL_MAX_BYTES / gib:.2f} GiB)", flush=True)
    print(f"reported only: peak private {(figures['peak_private_bytes'] or 0) / gib:.2f} GiB (includes GPU memory under WDDM)", flush=True)
    print(json.dumps({'done': done, 'of': len(items), 'seconds_per_image': report['seconds_per_image'], 'fp8_path': FP8_STATE['path'],
                      'peaks': {p: result.stats.get(p, {}).get('peak_allocated_bytes') for p in PHASES}, 'memory': memory,
                      'budget_passed': budget['passed']}), flush=True)
    backend.release()
    if not all_done:
        return 1
    return 0 if budget['passed'] else 4


def main(argv=None) -> int:
    protocol.utf8_stdio()
    parser = argparse.ArgumentParser(prog='engine', description='Đo bộ sinh ảnh theo pha trên GPU (Control).')
    sub = parser.add_subparsers(dest='command', required=True)
    measure = sub.add_parser('measure', help='Chạy một chu kỳ trên các caption và ghi PNG cùng report.json.')
    measure.add_argument('--hub', required=True)
    measure.add_argument('--captions', required=True, help='JSON: danh sách {"id", "<trường caption>"} hoặc danh sách chuỗi')
    measure.add_argument('--caption-field', default='caption')
    measure.add_argument('--strip-canvas-line', action='store_true', help='bỏ dòng đầu "TARGET CANVAS: ..." trước khi mã hoá')
    measure.add_argument('--out', required=True)
    measure.add_argument('--width', type=int, default=protocol.DEFAULT_WIDTH)
    measure.add_argument('--height', type=int, default=protocol.DEFAULT_HEIGHT)
    measure.add_argument('--steps', type=int, default=protocol.DEFAULT_STEPS)
    measure.add_argument('--seed', type=int, default=7)
    measure.add_argument('--residency', choices=RESIDENCIES, default='phase')
    measure.add_argument('--cycles', type=int, default=1, help='số chu kỳ; từ 2 trở lên thì chấm phần dư ở trạng thái ổn định')
    measure.add_argument('--manifest', default=str(Path(__file__).resolve().with_name('weights.lock.json')))
    measure.add_argument('--skip-verify', action='store_true')
    args = parser.parse_args(argv)
    return _measure(args)


if __name__ == '__main__':
    sys.exit(main())
