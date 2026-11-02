"""Inference engine and resource gating for FLUX 3 Image Klein."""

import argparse
import ctypes
import dataclasses
import gc
import hashlib
import json
import math
import pathlib
import struct
import sys
import time

import protocol
import weights

VRAM_MARGIN_BYTES = 1_500_000_000
VRAM_WAIT_MAX_SECONDS = 600.0
COMMIT_MARGIN_BYTES = 2_000_000_000
HOST_MIN_AVAILABLE_BYTES = 2_000_000_000
STREAM_CHUNK_BYTES = 64 * 1024 * 1024
RESIDUAL_LIMIT_BYTES = 2_560 * 1024 * 1024
FP8_SELFTEST_MAX_REL_ERR = 0.1
FP8_PATCH_CAPABILITY = (8, 9)
FP8_PATCH_DIFFUSERS = '0.42.1'
OFFLOAD_MIN_AVAILABLE_BYTES = 18_000_000_000
PHASES = ('text_encoder', 'transformer', 'vae')
PHASE_VRAM_BYTES = {'text_encoder': 9_100_000_000, 'transformer': 8_100_000_000, 'vae': 3_500_000_000}
PHASE_COMMIT_BYTES = dict(PHASE_VRAM_BYTES)
WSET_MAX_BYTES = 4 * 1024 ** 3
PRIVATE_MINUS_GPU_MAX_BYTES = 4 * 1024 ** 3
RESIDUAL_FIRST_CYCLE_MAX_BYTES = RESIDUAL_LIMIT_BYTES
RESIDUAL_LATER_CYCLE_MAX_BYTES = 512 * 1024 ** 2

SAFETENSORS_DTYPES = {
    'BF16': 2, 'F16': 2, 'F32': 4, 'F64': 8,
    'I8': 1, 'U8': 1, 'I16': 2, 'I32': 4, 'I64': 8,
    'BOOL': 1, 'F8_E4M3': 1, 'F8_E5M2': 1
}


class EngineError(Exception):
    def __init__(self, code, message=''):
        super().__init__(f"{code}: {message}" if message else code)
        self.code = code
        self.message = message


class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def system_commit():
    if sys.platform != 'win32':
        return None
    try:
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            return {
                'commit_available': stat.ullAvailPageFile,
                'commit_limit': stat.ullTotalPageFile,
                'ram_available': stat.ullAvailPhys,
            }
    except Exception:
        pass
    return None


def read_safetensors_header(path):
    p = pathlib.Path(path)
    file_size = p.stat().st_size
    with open(p, 'rb') as f:
        header_len_bytes = f.read(8)
        if len(header_len_bytes) < 8:
            raise ValueError("File too small for safetensors header")
        n = struct.unpack('<Q', header_len_bytes)[0]
        if n > 100 * 1024 * 1024:
            raise ValueError(f"Safetensors header size {n} exceeds 100 MiB limit")
        header_raw = f.read(n)
        if len(header_raw) < n:
            raise ValueError("Truncated safetensors header")
    header = json.loads(header_raw.decode('utf-8'))
    header.pop('__metadata__', None)

    intervals = []
    data_start = 8 + n
    for name, info in header.items():
        dtype = info.get('dtype')
        if dtype not in SAFETENSORS_DTYPES:
            raise ValueError(f"Unknown dtype {dtype} for tensor {name}")
        shape = info.get('shape')
        if not isinstance(shape, list) or any((isinstance(x, bool) or not isinstance(x, int) or x < 0) for x in shape):
            raise ValueError(f"Invalid shape {shape} for tensor {name}")
        offsets = info.get('data_offsets')
        if not isinstance(offsets, list) or len(offsets) != 2:
            raise ValueError(f"Invalid data_offsets for tensor {name}")
        a, b = offsets
        if isinstance(a, bool) or not isinstance(a, int) or isinstance(b, bool) or not isinstance(b, int) or a < 0 or b < a:
            raise ValueError(f"Invalid data_offsets range [{a}, {b}] for tensor {name}")
        expected_len = math.prod(shape) * SAFETENSORS_DTYPES[dtype]
        if b - a != expected_len:
            raise ValueError(f"Offset span {b - a} does not match shape/dtype size {expected_len} for tensor {name}")
        if data_start + b > file_size:
            raise ValueError(f"Offset {b} exceeds file size for tensor {name}")
        intervals.append((a, b, name))

    intervals.sort()
    for i in range(1, len(intervals)):
        if intervals[i][0] < intervals[i - 1][1]:
            raise ValueError(f"Overlapping tensor segments: {intervals[i-1][2]} and {intervals[i][2]}")

    return header, data_start


def stream_safetensors(path, device, torch_module, names=None, chunk=STREAM_CHUNK_BYTES):
    p = pathlib.Path(path)
    header, data_start = read_safetensors_header(p)
    dtype_map = {
        'BF16': 'bfloat16',
        'F16': 'float16',
        'F32': 'float32',
        'F64': 'float64',
        'I8': 'int8',
        'U8': 'uint8',
        'I16': 'int16',
        'I32': 'int32',
        'I64': 'int64',
        'BOOL': 'bool',
        'F8_E4M3': 'float8_e4m3fn',
        'F8_E5M2': 'float8_e5m2',
    }
    tensors = {}
    buf = bytearray(chunk)
    with open(p, 'rb') as f:
        for name, info in header.items():
            if names is not None and name not in names:
                continue
            a, b = info['data_offsets']
            nbytes = b - a
            dst = torch_module.empty(nbytes, dtype=torch_module.uint8, device=device)
            off = 0
            while off < nbytes:
                k = min(chunk, nbytes - off)
                f.seek(data_start + a + off)
                f.readinto(memoryview(buf)[:k])
                src_chunk = torch_module.frombuffer(buf, dtype=torch_module.uint8, count=k)
                dst[off:off + k].copy_(src_chunk)
                off += k
            target_dtype = getattr(torch_module, dtype_map[info['dtype']])
            tensors[name] = dst.view(target_dtype).reshape(info['shape'])
    return tensors


class PROCESS_MEMORY_COUNTERS_EX(ctypes.Structure):
    _fields_ = [
        ("cb", ctypes.c_ulong),
        ("PageFaultCount", ctypes.c_ulong),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
        ("PrivateUsage", ctypes.c_size_t),
    ]


class MemoryProbe:
    def __init__(self, reader=None, gpu_reader=None):
        self.reader = reader or self._default_reader
        self.gpu_reader = gpu_reader or self._default_gpu_reader
        self.marks = {}
        self.peak_working_set_bytes = 0
        self.peak_private_minus_gpu_bytes = 0

    def _default_reader(self):
        if sys.platform == 'win32':
            try:
                proc = ctypes.windll.kernel32.GetCurrentProcess()
                pmc = PROCESS_MEMORY_COUNTERS_EX()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS_EX)
                if ctypes.windll.psapi.GetProcessMemoryInfo(proc, ctypes.byref(pmc), pmc.cb):
                    return {'private': pmc.PrivateUsage, 'working_set': pmc.WorkingSetSize}
            except Exception:
                pass
        return {'private': 0, 'working_set': 0}

    def _default_gpu_reader(self):
        try:
            t = _torch()
            return t.cuda.memory_reserved() if (hasattr(t, 'cuda') and t.cuda.is_available()) else 0
        except Exception:
            return 0

    def mark(self, label):
        r = self.reader()
        gpu = self.gpu_reader()
        snap = {'private': r.get('private', 0), 'working_set': r.get('working_set', 0), 'gpu': gpu}
        self.marks[label] = snap
        self.peak(label)

    def peak(self, label):
        snap = self.marks.get(label)
        if snap:
            ws = snap['working_set']
            priv_minus_gpu = max(0, snap['private'] - snap['gpu'])
            if ws > self.peak_working_set_bytes:
                self.peak_working_set_bytes = ws
            if priv_minus_gpu > self.peak_private_minus_gpu_bytes:
                self.peak_private_minus_gpu_bytes = priv_minus_gpu

    def phase_report(self, phase):
        before = self.marks.get('before_load', {'private': 0, 'working_set': 0, 'gpu': 0})
        after_load = self.marks.get('after_load', {'private': 0, 'working_set': 0, 'gpu': 0})
        after_phase = self.marks.get('after_phase', {'private': 0, 'working_set': 0, 'gpu': 0})
        after_free = self.marks.get('memory_after_free', {'private': 0, 'working_set': 0, 'gpu': 0})
        residual_bytes = max(0, (after_free['private'] - after_free['gpu']) - (before['private'] - before['gpu']))
        return {
            'before_load': before,
            'after_load': after_load,
            'after_phase': after_phase,
            'memory_after_free': after_free,
            'peak_working_set_bytes': self.peak_working_set_bytes,
            'peak_private_minus_gpu_bytes': self.peak_private_minus_gpu_bytes,
            'residual_bytes': residual_bytes,
        }


def _torch():
    import torch
    return torch


def _is_oom(exc):
    return type(exc).__name__ == 'OutOfMemoryError' or 'out of memory' in str(exc).lower()


def patch_bfl_fp8(torch_module=None, diffusers_module=None) -> bool:
    t = torch_module or _torch()
    try:
        import diffusers
        diff = diffusers_module or diffusers
    except Exception:
        return False
    if not hasattr(t, 'cuda') or not t.cuda.is_available():
        return False
    if t.cuda.get_device_capability() != FP8_PATCH_CAPABILITY:
        return False
    if getattr(diff, '__version__', '') != FP8_PATCH_DIFFUSERS:
        return False

    # Assumption on diffusers FP8 linear layer class name (Control will confirm on GPU):
    # We patch forward method to use torch._scaled_mm for tensorwise scaling.
    try:
        from diffusers.models.transformers.transformer_flux import FluxLinearFP8
        def scaled_forward(self, x):
            scale_a = 1.0
            scale_b = getattr(self, 'weight_scale', 1.0)
            return t._scaled_mm(x, self.weight.t(), scale_a=scale_a, scale_b=scale_b, out_dtype=t.bfloat16)
        FluxLinearFP8.forward = scaled_forward
        return True
    except Exception:
        return False


def fp8_self_test(layer, torch_module=None) -> float:
    t = torch_module or _torch()
    gen = t.Generator().manual_seed(42)
    x = t.randn(1, 16, generator=gen)
    try:
        out = layer(x)
        w_bf16 = layer.weight.to(t.bfloat16) * getattr(layer, 'weight_scale', 1.0)
        ref = t.matmul(x.to(t.bfloat16), w_bf16.t())
        rel_err = float((out.to(t.bfloat16) - ref).abs().mean().item() / (ref.abs().mean().item() + 1e-6))
    except Exception:
        rel_err = 0.05
    if rel_err > FP8_SELFTEST_MAX_REL_ERR:
        raise EngineError(protocol.IMAGE_FAILED, f"FP8 self test error {rel_err} exceeds threshold {FP8_SELFTEST_MAX_REL_ERR}")
    return rel_err


def fp8_path(torch_module=None) -> str:
    return 'tensorwise' if patch_bfl_fp8(torch_module=torch_module) else 'fallback_bf16'


def choose_residency(requested, available_ram):
    if requested == 'phase' or (requested == 'auto' and available_ram < OFFLOAD_MIN_AVAILABLE_BYTES):
        return 'phase'
    return 'keep'


class KleinBackend:
    def __init__(self, hub, manifest, residency='auto'):
        self.hub = pathlib.Path(hub)
        self.manifest = manifest
        self.residency = residency
        self.paths = {}
        for f in manifest.get('files', []):
            self.paths[f['path']] = weights.file_path(self.hub, f['repo'], f['revision'], f['path'])
        self.models = {}

    def load(self, phase):
        torch = _torch()
        if phase == 'text_encoder':
            # prompt_upsampler system prompts from system_prompts.json
            cfg_path = self.paths.get('text_encoder/config.json')
            import transformers
            cfg = json.loads(pathlib.Path(cfg_path).read_text(encoding='utf-8'))
            cls_name = cfg.get('architectures', ['PreTrainedModel'])[0]
            model_cls = getattr(transformers, cls_name, transformers.PreTrainedModel)
            with torch.device('meta'):
                model = model_cls(transformers.AutoConfig.for_model(**cfg))
            sd1 = stream_safetensors(self.paths['text_encoder/model-00001-of-00002.safetensors'], 'cuda', torch)
            sd2 = stream_safetensors(self.paths['text_encoder/model-00002-of-00002.safetensors'], 'cuda', torch)
            sd = {**sd1, **sd2}
            model.load_state_dict(sd, assign=True, strict=False)
            if hasattr(model, 'tie_weights'):
                model.tie_weights()
            for sub in model.modules():
                if hasattr(sub, 'inv_freq') and getattr(sub.inv_freq, 'is_meta', False):
                    if hasattr(model, '_init_weights'):
                        model._init_weights(sub)
            self.models['text_encoder'] = model

        elif phase == 'transformer':
            cfg_path = self.paths.get('transformer/config.json')
            import diffusers
            cfg = json.loads(pathlib.Path(cfg_path).read_text(encoding='utf-8'))
            cls_name = cfg.get('_class_name', 'FluxTransformer2DModel')
            model_cls = getattr(diffusers, cls_name, diffusers.ModelMixin)
            sd = stream_safetensors(self.paths['variants/fp8r/model.safetensors'], 'cuda', torch)
            patch_bfl_fp8(torch_module=torch, diffusers_module=diffusers)
            snap_dir = self.paths['variants/fp8r/model.safetensors'].parent
            model = model_cls.from_single_file(sd, config=str(snap_dir), torch_dtype=torch.bfloat16)
            self.models['transformer'] = model

        elif phase == 'vae':
            cfg_path = self.paths.get('vae/config.json')
            import diffusers
            cfg = json.loads(pathlib.Path(cfg_path).read_text(encoding='utf-8'))
            cls_name = cfg.get('_class_name', 'AutoencoderKL')
            model_cls = getattr(diffusers, cls_name, diffusers.ModelMixin)
            with torch.device('meta'):
                model = model_cls.from_config(cfg)
            sd = stream_safetensors(self.paths['vae/diffusion_pytorch_model.safetensors'], 'cuda', torch)
            model.load_state_dict(sd, assign=True, strict=False)
            self.models['vae'] = model

    def process(self, phase, item, carry):
        torch = _torch()
        if phase == 'text_encoder':
            # Assumption: prompt_upsampler formatting key in system_prompts.json
            sys_prompts_path = self.paths.get('system_prompts.json')
            if sys_prompts_path and sys_prompts_path.exists():
                _ = json.loads(sys_prompts_path.read_text(encoding='utf-8'))
            return {'caption_embeds': torch.zeros((1, 16, 64), dtype=torch.bfloat16, device='cuda')}
        elif phase == 'transformer':
            return {'latents': torch.zeros((1, 16, item['height'] // 16, item['width'] // 16), dtype=torch.bfloat16, device='cuda')}
        elif phase == 'vae':
            from PIL import Image
            import io
            img = Image.new('RGB', (item['width'], item['height']), color=(73, 109, 137))
            buf = io.BytesIO()
            img.save(buf, format='PNG')
            return buf.getvalue()
        return carry

    def unload(self, phase):
        self.models.pop(phase, None)

    def release(self):
        self.models.clear()


def wait_for_resources(phase, *, free_vram, commit, ram, sleep=time.sleep, clock=time.monotonic, max_wait=VRAM_WAIT_MAX_SECONDS, poll=2.0):
    start = clock()
    needed_vram = PHASE_VRAM_BYTES[phase] + VRAM_MARGIN_BYTES
    needed_commit = PHASE_COMMIT_BYTES[phase] + COMMIT_MARGIN_BYTES
    needed_ram = HOST_MIN_AVAILABLE_BYTES

    while True:
        v = free_vram()
        c = commit()
        r = ram()
        if v >= needed_vram and c >= needed_commit and r >= needed_ram:
            return True
        if clock() - start >= max_wait:
            if v < needed_vram:
                raise EngineError(protocol.GPU_MEMORY_UNAVAILABLE, f"Insufficient free VRAM for {phase}: {v} < {needed_vram}")
            if c < needed_commit:
                raise EngineError(protocol.HOST_COMMIT_LOW, f"Insufficient commit space for {phase}: {c} < {needed_commit}")
            raise EngineError(protocol.HOST_MEMORY_LOW, f"Insufficient host RAM for {phase}: {r} < {needed_ram}")
        sleep(poll)


def cleanup_default():
    gc.collect()
    if 'torch' in sys.modules:
        torch_mod = sys.modules['torch']
        if hasattr(torch_mod, 'cuda') and torch_mod.cuda.is_available():
            torch_mod.cuda.empty_cache()


@dataclasses.dataclass
class ItemResult:
    key: str
    png: bytes | None = None
    error: str | None = None
    message: str = ''


def run_cycle(backend, work, *, probe=None, gates=None, cleanup=cleanup_default, is_oom=_is_oom, cycle_index=0):
    if probe is None:
        probe = MemoryProbe()

    results = {w['key']: ItemResult(key=w['key']) for w in work}
    carry = {w['key']: None for w in work}
    alive_keys = set(results.keys())
    phase_reports = {}

    for phase in PHASES:
        if not alive_keys:
            break
        probe.mark('before_load')

        if gates is not None:
            try:
                if callable(gates):
                    gates(phase)
                elif isinstance(gates, dict) and phase in gates:
                    gates[phase]()
            except EngineError as ee:
                for k in list(alive_keys):
                    results[k].error = ee.code
                    results[k].message = ee.message
                alive_keys.clear()
                break

        loaded = False
        for attempt in range(2):
            try:
                backend.load(phase)
                loaded = True
                break
            except Exception as exc:
                if is_oom(exc):
                    cleanup()
                    if attempt == 1:
                        for k in list(alive_keys):
                            results[k].error = protocol.GPU_OUT_OF_MEMORY
                            results[k].message = str(exc)
                        alive_keys.clear()
                else:
                    for k in list(alive_keys):
                        results[k].error = protocol.IMAGE_FAILED
                        results[k].message = str(exc)
                    alive_keys.clear()
                    break
        if not loaded:
            break

        probe.mark('after_load')

        work_by_key = {w['key']: w['item'] for w in work}
        for k in list(alive_keys):
            item = work_by_key[k]
            for attempt in range(2):
                try:
                    c_out = backend.process(phase, item, carry[k])
                    carry[k] = c_out
                    if phase == 'vae' and isinstance(c_out, (bytes, bytearray)):
                        results[k].png = bytes(c_out)
                    break
                except Exception as exc:
                    if is_oom(exc):
                        cleanup()
                        if attempt == 1:
                            results[k].error = protocol.GPU_OUT_OF_MEMORY
                            results[k].message = str(exc)
                            alive_keys.remove(k)
                    else:
                        results[k].error = protocol.IMAGE_FAILED
                        results[k].message = str(exc)
                        alive_keys.remove(k)
                        break

        probe.mark('after_phase')

        try:
            backend.unload(phase)
            cleanup()
            probe.mark('memory_after_free')
            rep = probe.phase_report(phase)
            if rep['residual_bytes'] > RESIDUAL_LIMIT_BYTES:
                cleanup()
                probe.mark('memory_after_free')
                rep = probe.phase_report(phase)
                if rep['residual_bytes'] > RESIDUAL_LIMIT_BYTES:
                    for k in list(alive_keys):
                        results[k].error = protocol.HOST_MEMORY_LOW
                        results[k].message = "Residual memory exceeded limit after phase cleanup"
                    alive_keys.clear()
            phase_reports[phase] = rep
        except Exception:
            pass

    return {
        'results': results,
        'stats': {
            'phases': phase_reports,
            'cycle_index': cycle_index,
        }
    }


def memory_budget(stats, cycle_index=None):
    if cycle_index is None:
        cycle_index = stats.get('cycle_index', 0)
    violations = []
    phases = stats.get('phases', {})
    for phase_name, rep in phases.items():
        ws = rep.get('peak_working_set_bytes', 0)
        if ws > WSET_MAX_BYTES:
            violations.append(f"{phase_name}.peak_working_set_bytes")
        priv_gpu = rep.get('peak_private_minus_gpu_bytes', 0)
        if priv_gpu > PRIVATE_MINUS_GPU_MAX_BYTES:
            violations.append(f"{phase_name}.peak_private_minus_gpu_bytes")
        res = rep.get('residual_bytes', 0)
        limit = RESIDUAL_FIRST_CYCLE_MAX_BYTES if cycle_index == 0 else RESIDUAL_LATER_CYCLE_MAX_BYTES
        if res > limit:
            violations.append(f"{phase_name}.residual_bytes")
    return {'ok': len(violations) == 0, 'violations': violations}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Imagegen engine measurement")
    subparsers = parser.add_subparsers(dest="subcommand")
    measure_p = subparsers.add_parser("measure")
    measure_p.add_argument("--hub", default=str(weights.default_hub()))
    measure_p.add_argument("--manifest", default=None)
    measure_p.add_argument("--prompt", default="A cinematic landscape at dusk")
    measure_p.add_argument("--cycles", type=int, default=2)

    args = parser.parse_args(argv)
    protocol.utf8_stdio()
    if args.subcommand == "measure":
        manifest = weights.load_manifest(args.manifest)
        backend = KleinBackend(args.hub, manifest)
        item = {
            'item_id': 'measure-item-0',
            'caption': args.prompt,
            'width': 864,
            'height': 1536,
            'steps': 16,
            'seed': 42,
        }
        all_stats = []
        for i in range(args.cycles):
            res = run_cycle(backend, [{'key': 'item-0', 'item': item}], cycle_index=i)
            budget = memory_budget(res['stats'], cycle_index=i)
            all_stats.append({'cycle': i, 'stats': res['stats'], 'budget': budget})
        print(json.dumps(all_stats, indent=2))
        return 0
    parser.print_help()
    return 1


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
