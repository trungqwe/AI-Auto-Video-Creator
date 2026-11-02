"""Sidecar HTTP sinh ảnh minh hoạ (IMGGEN-SVC, DESIGN wave 42 mục 2): một tiến trình riêng do launcher quản lý.

Chạy: <data>/imagegen/venv/Scripts/python.exe -I tools/imagegen/server.py --port 57030 --hub <data>/models/hf-hub
      --out <data>/imagegen/out --parent-pid <pid launcher> --stop-file <data>/state/stop.request
với AIAVC_IMAGEGEN_TOKEN (>= 32 ký tự, mỗi lần khởi động một token) trong môi trường. Chỉ nghe 127.0.0.1; bearer token trên mọi
lệnh trừ /v1/health. Sidecar tự đặt HF_HUB_OFFLINE=1 và TRANSFORMERS_OFFLINE=1: không bao giờ tải gì.

Vòng đời: lúc khởi động kiểm trọng số (verifying) theo tem, rồi idle hoặc not_provisioned (kèm danh sách tệp). Một worker FIFO:
mỗi chu kỳ lấy tối đa 16 ảnh đang chờ, chạy engine.run_cycle (loading/busy theo pha). Job lưu ở <out>/<job_id>/job.json và
item-<n>.png, nạp lại khi khởi động (ảnh dở được xếp lại), giữ 24 giờ. Dừng khi có tệp stop.request, khi tiến trình cha thoát,
hoặc POST /v1/shutdown; ảnh đang dở được xếp lại hàng để lần chạy sau làm tiếp.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import http.server
import json
import os
import re
import socket
import sys
import threading
import time
from pathlib import Path

if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from imagegen import engine, protocol, weights  # noqa: E402

STOP_POLL_SECONDS = 1.0
STOP_GRACE_SECONDS = 20.0
PRUNE_EVERY_SECONDS = 600.0
JOB_FILE = 'job.json'
EXIT_OK, EXIT_USAGE, EXIT_PORT_IN_USE, EXIT_PARENT_GONE = 0, 2, 3, 4
_JOB_PATH = re.compile(r'/v1/jobs/([0-9a-f]{32})')
_ITEM_PATH = re.compile(r'/v1/jobs/([0-9a-f]{32})/items/([A-Za-z0-9][A-Za-z0-9_-]{0,63})')
_JOB_FILES = re.compile(r'(job\.json|item-[0-9]{1,2}\.png)(\.partial-[0-9]+-[0-9]+)?')


def process_memory() -> dict | None:
    """Memory of this process (psutil is in the sidecar env, not in the product runtime). The weights are memory-mapped, so the working
    set also counts reclaimable file pages; the private commit (peak_private_bytes) is what can exhaust the machine's memory."""
    try:
        import psutil
    except ImportError:
        return None
    info = psutil.Process().memory_info()
    return {'rss_bytes': int(info.rss), 'peak_wset_bytes': getattr(info, 'peak_wset', None),
            'private_bytes': getattr(info, 'private', None), 'peak_private_bytes': getattr(info, 'peak_pagefile', None)}


def _write_bytes_atomic(path: Path, data: bytes) -> None:
    tmp = path.with_name(f'{path.name}.partial-{os.getpid()}-{time.time_ns()}')
    with tmp.open('wb') as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


class JobStore:
    """Jobs in memory, mirrored to <out>/<job_id>/job.json and item-<n>.png. Thread-safe; FIFO queue of item keys."""

    def __init__(self, out_dir: Path, clock=time.time, log=None):
        self.out = Path(out_dir)
        self.clock = clock
        self.log = log or (lambda message: None)
        self.lock = threading.RLock()
        self.jobs: dict = {}
        self.queue: list = []

    # -- persistence --------------------------------------------------------------------------------------------------
    def _dir(self, job_id: str) -> Path:
        return self.out / job_id

    def _persist(self, record: dict) -> None:
        record['updated_at'] = self.clock()
        directory = self._dir(record['job_id'])
        directory.mkdir(parents=True, exist_ok=True)
        weights.atomic_write_text(directory / JOB_FILE, json.dumps(record, ensure_ascii=False))

    def load(self) -> dict:
        """Reads the jobs a previous run left (younger than RESULT_TTL_SECONDS); unfinished items are queued again."""
        loaded = requeued = lost = 0
        if not self.out.is_dir():
            return {'loaded': 0, 'requeued': 0, 'lost': 0}
        found = []
        for entry in os.scandir(self.out):
            if not entry.is_dir(follow_symlinks=False) or not protocol.JOB_ID_PATTERN.fullmatch(entry.name):
                continue
            try:
                record = json.loads((Path(entry.path) / JOB_FILE).read_text(encoding='utf-8'))
                request = protocol.parse_job(protocol.canonical_json(record['request']))
                if record['job_id'] != entry.name or request.body_sha256 != record['body_sha256']:
                    raise ValueError('job.json does not match its directory or body hash')
                if set(record['items']) != {item.item_id for item in request.items}:
                    raise ValueError('job.json items do not match the request')
            except (OSError, ValueError, KeyError, TypeError, protocol.ProtocolError) as error:
                self.log(f'skip {entry.name}: {type(error).__name__}')
                continue
            found.append(record)
        with self.lock:
            for record in sorted(found, key=lambda r: r.get('created_at', 0)):
                if self._expired(record):
                    self._remove(record['job_id'])
                    continue
                changed = False
                for index, item in enumerate(record['request']['items']):
                    state = record['items'][item['item_id']]
                    if state['state'] in ('queued', 'running'):
                        state['state'] = 'queued'
                        self.queue.append(f"{record['job_id']}/{item['item_id']}")
                        requeued += 1
                        changed = True
                    elif state['state'] == 'done' and not (self._dir(record['job_id']) / f'item-{index}.png').is_file():
                        self._set_failed(state, protocol.RESULT_MISSING, 'the PNG of a finished item is missing')
                        lost += 1
                        changed = True
                self.jobs[record['job_id']] = record
                loaded += 1
                if changed:
                    self._persist(record)
        return {'loaded': loaded, 'requeued': requeued, 'lost': lost}

    def _expired(self, record: dict) -> bool:
        active = any(s['state'] in ('queued', 'running') for s in record['items'].values())
        return not active and record.get('updated_at', 0) + protocol.RESULT_TTL_SECONDS < self.clock()

    def _remove(self, job_id: str) -> None:
        directory = self._dir(job_id)
        self.jobs.pop(job_id, None)
        try:
            for entry in os.scandir(directory):
                if entry.is_file(follow_symlinks=False) and _JOB_FILES.fullmatch(entry.name):
                    os.unlink(entry.path)
            directory.rmdir()
        except OSError as error:
            self.log(f'prune {job_id}: {type(error).__name__}')

    def prune(self) -> int:
        with self.lock:
            expired = [job_id for job_id, record in self.jobs.items() if self._expired(record)]
            for job_id in expired:
                self._remove(job_id)
            return len(expired)

    # -- requests ---------------------------------------------------------------------------------------------------
    def _active_items(self) -> int:
        return sum(1 for r in self.jobs.values() for s in r['items'].values() if s['state'] in ('queued', 'running'))

    @staticmethod
    def _set_failed(state: dict, code: str, message: str) -> None:
        state.update(state='failed', error=code, message=message[:500], finished_at=time.time())

    def submit(self, request: protocol.JobRequest) -> tuple[dict, bool]:
        """Idempotent on (job_id, body sha256): the same body returns the job and queues again the items that failed with a
        retryable error and attempts left; another body under the same job_id is a conflict."""
        with self.lock:
            record = self.jobs.get(request.job_id)
            if record is not None:
                if record['body_sha256'] != request.body_sha256:
                    raise protocol.ProtocolError(protocol.JOB_CONFLICT, 'job_id already holds a different body', 'job_id')
                again = [item.item_id for item in request.items if self._retryable(record['items'][item.item_id])]
                if again and self._active_items() + len(again) > protocol.MAX_QUEUED_ITEMS:
                    raise protocol.ProtocolError(protocol.QUEUE_FULL, f'at most {protocol.MAX_QUEUED_ITEMS} items may wait')
                for item_id in again:
                    record['items'][item_id].update(state='queued', error=None, message=None, finished_at=None)
                    self.queue.append(f'{request.job_id}/{item_id}')
                if again:
                    self._persist(record)
                return self._view(record), False
            if self._active_items() + len(request.items) > protocol.MAX_QUEUED_ITEMS:
                raise protocol.ProtocolError(protocol.QUEUE_FULL, f'at most {protocol.MAX_QUEUED_ITEMS} items may wait')
            now = self.clock()
            record = {'job_id': request.job_id, 'body_sha256': request.body_sha256, 'created_at': now, 'updated_at': now,
                      'request': request.as_dict(),
                      'items': {item.item_id: {'state': 'queued', 'sha256': None, 'bytes': None, 'error': None, 'message': None,
                                               'fp8_path': None, 'attempts': 0, 'seconds': {}, 'finished_at': None}
                                for item in request.items}}
            self._persist(record)
            self.jobs[request.job_id] = record
            self.queue.extend(f'{request.job_id}/{item.item_id}' for item in request.items)
            return self._view(record), True

    @staticmethod
    def _retryable(state: dict) -> bool:
        return (state['state'] == 'failed' and state.get('error') in protocol.RETRYABLE_ITEM_ERRORS
                and state.get('attempts', 0) < protocol.MAX_ITEM_ATTEMPTS)

    def view(self, job_id: str) -> dict | None:
        with self.lock:
            record = self.jobs.get(job_id)
            return None if record is None else self._view(record)

    def _view(self, record: dict) -> dict:
        items = []
        for item in record['request']['items']:
            state = record['items'][item['item_id']]
            error = protocol.error_view(state.get('error'), state.get('message'))
            if error is not None:
                error['retryable'] = self._retryable(state)
            items.append({'item_id': item['item_id'], 'state': state['state'], 'sha256': state.get('sha256'),
                          'bytes': state.get('bytes'), 'width': item['width'], 'height': item['height'], 'steps': item['steps'],
                          'seed': item['seed'], 'fp8_path': state.get('fp8_path'), 'attempts': state.get('attempts', 0),
                          'seconds': state.get('seconds') or {}, 'error': error})
        return {'job_id': record['job_id'], 'state': protocol.job_state(i['state'] for i in items),
                'created_at': protocol.iso(record['created_at']),
                'expires_at': protocol.iso(record.get('updated_at', record['created_at']) + protocol.RESULT_TTL_SECONDS),
                'model': {'repo': protocol.MODEL_REPO, 'revision': protocol.MODEL_REVISION}, 'items': items}

    def png(self, job_id: str, item_id: str) -> tuple[bytes, str]:
        with self.lock:
            record = self.jobs.get(job_id)
            if record is None or item_id not in record['items']:
                raise protocol.ProtocolError(protocol.NOT_FOUND, 'no such job item')
            state = record['items'][item_id]
            if state['state'] != 'done':
                raise protocol.ProtocolError(protocol.ITEM_NOT_READY, f"item is {state['state']}")
            index = [item['item_id'] for item in record['request']['items']].index(item_id)
            path = self._dir(job_id) / f'item-{index}.png'
            try:
                data = path.read_bytes()
            except OSError:
                data = None
            if data is None or hashlib.sha256(data).hexdigest() != state['sha256']:
                self._set_failed(state, protocol.RESULT_MISSING, 'the stored PNG is missing or does not match its sha256')
                self._persist(record)
                raise protocol.ProtocolError(protocol.RESULT_CORRUPT, 'the stored PNG is missing or corrupt; repeat the POST to regenerate')
            return data, state['sha256']

    # -- worker side ------------------------------------------------------------------------------------------------
    def take(self, limit: int) -> list:
        """Pops up to `limit` queued items (FIFO) and marks them running."""
        with self.lock:
            batch, touched = [], {}
            while self.queue and len(batch) < limit:
                key = self.queue.pop(0)
                job_id, item_id = key.split('/', 1)
                record = self.jobs.get(job_id)
                if record is None or record['items'][item_id]['state'] != 'queued':
                    continue
                item = next(i for i in record['request']['items'] if i['item_id'] == item_id)
                state = record['items'][item_id]
                state['state'] = 'running'
                state['attempts'] = state.get('attempts', 0) + 1
                touched[job_id] = record
                batch.append(engine.WorkItem(key, item['caption'], item['width'], item['height'], item['steps'], item['seed']))
            for record in touched.values():
                self._persist(record)
            return batch

    def finish(self, result: engine.CycleResult) -> None:
        with self.lock:
            touched = {}
            interrupted = set(result.interrupted)
            requeue = []
            for outcome in result.outcomes:
                job_id, item_id = outcome.key.split('/', 1)
                record = self.jobs.get(job_id)
                if record is None:
                    continue
                state = record['items'][item_id]
                touched[job_id] = record
                state['seconds'] = dict(outcome.seconds)
                if outcome.fp8_path:
                    state['fp8_path'] = outcome.fp8_path
                if outcome.key in interrupted:
                    state['state'] = 'queued'
                    state['attempts'] = max(0, state.get('attempts', 1) - 1)
                    requeue.append(outcome.key)
                elif outcome.png is not None:
                    index = [item['item_id'] for item in record['request']['items']].index(item_id)
                    try:
                        self._dir(job_id).mkdir(parents=True, exist_ok=True)
                        _write_bytes_atomic(self._dir(job_id) / f'item-{index}.png', outcome.png)
                    except OSError as error:
                        self._set_failed(state, protocol.OUTPUT_WRITE_FAILED, f'{type(error).__name__}: {error}')
                        continue
                    state.update(state='done', sha256=hashlib.sha256(outcome.png).hexdigest(), bytes=len(outcome.png), error=None,
                                 message=None, finished_at=self.clock())
                else:
                    self._set_failed(state, outcome.error_code or protocol.GENERATION_FAILED, outcome.message or '')
            self.queue[:0] = requeue
            for record in touched.values():
                self._persist(record)

    def fail_keys(self, keys, code: str, message: str, only_state: str | None = None) -> int:
        with self.lock:
            touched, failed = {}, 0
            for key in keys:
                job_id, item_id = key.split('/', 1)
                record = self.jobs.get(job_id)
                if record is None or (only_state and record['items'][item_id]['state'] != only_state):
                    continue
                self._set_failed(record['items'][item_id], code, message)
                touched[job_id] = record
                failed += 1
            for record in touched.values():
                self._persist(record)
            return failed

    def fail_queued(self, code: str, message: str) -> int:
        with self.lock:
            keys, self.queue = list(self.queue), []
            return self.fail_keys(keys, code, message, only_state='queued')

    def counts(self) -> dict:
        with self.lock:
            jobs = sum(1 for r in self.jobs.values() if any(s['state'] in ('queued', 'running') for s in r['items'].values()))
            return {'jobs': jobs, 'items': self._active_items()}


class App:
    """Service state, the worker thread and the verification thread. backend: engine.KleinBackend or a test double with the same
    methods (requirement, free_vram, load, unload, encode, denoise, decode, is_oom, fp8_path, release; optional host_available,
    commit_available and memory)."""

    def __init__(self, *, backend, out_dir: Path, token: str, verifier, gpu_memory=None, commit_probe=None, clock=time.time,
                 monotonic=time.monotonic, vram_wait_max: float = engine.VRAM_WAIT_MAX_SECONDS, log=None):
        self.backend = backend
        self.token = token
        self.verifier = verifier
        self.gpu_memory = gpu_memory or engine.CachedGpuMemory()
        self.commit_probe = commit_probe or engine.system_commit
        self.clock = clock
        self.monotonic = monotonic
        self.vram_wait_max = vram_wait_max
        self.log = log or (lambda message: print(f'{protocol.iso(time.time())} imagegen: {message}', file=sys.stderr, flush=True))
        self.jobs = JobStore(out_dir, clock, self.log)
        self.state, self.phase = 'verifying', None
        self.problems: list = []
        self.error = None
        self.stop_reason = None
        self.verification = None
        self.last_cycle = None
        self.cycles = 0
        self.stopping = threading.Event()
        self.wake = threading.Event()
        self._state_lock = threading.Lock()
        self._threads: list = []

    # -- state ------------------------------------------------------------------------------------------------------
    def set_state(self, state: str, phase: str | None = None) -> None:
        with self._state_lock:
            if state != self.state or phase != self.phase:
                self.log(f'state {self.state}/{self.phase} -> {state}/{phase}')
            self.state, self.phase = state, phase

    def health(self) -> dict:
        with self._state_lock:
            state, phase, problems, error = self.state, self.phase, list(self.problems), self.error
        body = {'service': protocol.SERVICE_NAME, 'protocol': protocol.PROTOCOL_VERSION, 'state': state, 'phase': phase,
                'model': {'repo': protocol.MODEL_REPO, 'revision': protocol.MODEL_REVISION}, 'revision': protocol.MODEL_REVISION,
                'queue': self.jobs.counts(), 'fp8_path': self.backend.fp8_path(), 'vram': self.gpu_memory(), 'pid': os.getpid(),
                'process': process_memory(), 'memory': getattr(self.backend, 'memory', lambda: None)(), 'commit': self.commit_probe(),
                'cycles': self.cycles,
                'last_cycle': self.last_cycle, 'stopping': self.stopping.is_set()}
        if state == 'not_provisioned':
            body['missing'] = problems
        if error:
            body['error'] = error
        return body

    def accept(self) -> None:
        """Raises the 503 a POST /v1/jobs gets in the current state."""
        if self.stopping.is_set():
            raise protocol.ProtocolError(protocol.SHUTTING_DOWN, 'the service is stopping')
        with self._state_lock:
            state, problems, error = self.state, list(self.problems), self.error
        if state == 'not_provisioned':
            raise protocol.ProtocolError(protocol.SERVICE_NOT_PROVISIONED, 'the pinned weights are not installed or do not match',
                                         missing=problems)
        if state == 'error':
            raise protocol.ProtocolError(protocol.SERVICE_UNAVAILABLE, error or 'the image engine is unavailable')

    def submit(self, request: protocol.JobRequest) -> tuple[dict, bool]:
        self.accept()
        view, created = self.jobs.submit(request)
        self.wake.set()
        return view, created

    # -- threads ----------------------------------------------------------------------------------------------------
    def start(self) -> None:
        summary = self.jobs.load()
        if summary['loaded']:
            self.log(f"loaded {summary['loaded']} jobs ({summary['requeued']} items queued again, {summary['lost']} results missing)")
        for target, name in ((self._verify, 'imagegen-verify'), (self._work, 'imagegen-worker')):
            thread = threading.Thread(target=target, name=name, daemon=True)
            thread.start()
            self._threads.append(thread)

    def _verify(self) -> None:
        try:
            result = self.verifier()
        except Exception as error:
            with self._state_lock:
                self.problems = [f'verification failed: {type(error).__name__}: {error}']
            self.set_state('not_provisioned')
            self.wake.set()
            return
        self.verification = {'ok': result.ok, 'rehashed': result.rehashed, 'stamp_written': result.stamp_written, 'seconds': result.seconds}
        with self._state_lock:
            self.problems = [] if result.ok else result.problems()
        self.log(f"weights {'verified' if result.ok else 'NOT provisioned'} in {result.seconds} s (rehashed={result.rehashed})")
        self.set_state('idle' if result.ok else 'not_provisioned')
        self.wake.set()

    def _sleep(self, seconds: float) -> None:
        self.stopping.wait(seconds)

    def _work(self) -> None:
        context = {'idle_since': self.monotonic(), 'last_prune': self.monotonic(), 'holding': False}
        while not self.stopping.is_set():
            try:
                self._work_once(context)
            except Exception as error:  # a fault of the job store (disk full, permissions) must not end the worker
                self.log(f'worker fault: {engine._describe(error)}')
                self._pause(1.0)
        self._release()

    def _work_once(self, context: dict) -> None:
        state = self.state
        if state == 'verifying':
            self._pause(0.2)
            return
        if state in ('not_provisioned', 'error'):
            code = protocol.NOT_PROVISIONED if state == 'not_provisioned' else protocol.ENGINE_UNAVAILABLE
            failed = self.jobs.fail_queued(code, '; '.join(self.problems)[:500] if state == 'not_provisioned' else (self.error or ''))
            if failed:
                self.log(f'{failed} queued items failed with {code}')
            self._pause(1.0)
            return
        if self.monotonic() - context['last_prune'] >= PRUNE_EVERY_SECONDS:
            context['last_prune'] = self.monotonic()
            self.jobs.prune()
        batch = self.jobs.take(protocol.MAX_ITEMS_PER_CYCLE)
        if not batch:
            if context['holding'] and self.monotonic() - context['idle_since'] >= protocol.IDLE_UNLOAD_SECONDS:
                self._release()
                context['holding'] = False
            self._pause(0.5)
            return
        context['holding'] = True
        self.log(f'cycle of {len(batch)} items')
        try:
            result = engine.run_cycle(self.backend, batch, on_state=self.set_state, stopping=self.stopping.is_set,
                                      sleep=self._sleep, clock=self.monotonic, vram_wait_max=self.vram_wait_max)
        except engine.EngineUnavailable as error:
            with self._state_lock:
                self.error = error.message
            self.jobs.fail_keys([item.key for item in batch], protocol.ENGINE_UNAVAILABLE, error.message)
            self.set_state('error')
            self.log(f'engine unavailable: {error.message}')
            return
        except Exception as error:
            self.jobs.fail_keys([item.key for item in batch], protocol.GENERATION_FAILED, engine._describe(error))
            self.log(f'cycle failed: {engine._describe(error)}')
            if not self.stopping.is_set():
                self.set_state('idle')
            return
        self.jobs.finish(result)
        self.cycles += 1
        self.last_cycle = {'items': len(batch), 'done': sum(1 for o in result.outcomes if o.png is not None),
                           'interrupted': len(result.interrupted), 'stats': result.stats}
        self.log(f"cycle done: {self.last_cycle['done']}/{len(batch)} in {result.stats.get('cycle_seconds')} s")
        for phase in engine.PHASES:
            record = result.stats.get(phase) or {}
            if record.get('peak_private_bytes_phase') is not None:
                self.log(f"{phase}: private before load {(record.get('memory_before_load') or {}).get('private_bytes')} B, "
                         f"peak {record['peak_private_bytes_phase']} B, residual after free {record.get('residual_private_bytes')} B")
        context['idle_since'] = self.monotonic()
        if not self.stopping.is_set():
            self.set_state('idle')

    def _pause(self, seconds: float) -> None:
        self.wake.wait(seconds)
        self.wake.clear()

    def _release(self) -> None:
        try:
            self.backend.release()
        except Exception as error:
            self.log(f'release failed: {engine._describe(error)}')

    def request_stop(self, reason: str) -> None:
        if not self.stopping.is_set():
            self.stop_reason = reason
            self.log(f'stopping: {reason}')
            self.stopping.set()
            self.wake.set()

    def join(self, timeout: float) -> bool:
        """Waits for the worker, the only thread that holds the GPU; a verification still hashing writes its stamp atomically."""
        workers = [thread for thread in self._threads if thread.name == 'imagegen-worker']
        deadline = time.monotonic() + timeout
        for thread in workers:
            thread.join(max(0.0, deadline - time.monotonic()))
        return not any(thread.is_alive() for thread in workers)


class ParentWatch:
    """The launcher process, watched through a handle opened at start on Windows, so a reused PID never looks alive."""

    def __init__(self, pid: int):
        self.pid = pid
        self._handle = None
        if sys.platform == 'win32':
            import ctypes
            from ctypes import wintypes
            kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
            kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            kernel32.OpenProcess.restype = ctypes.c_void_p
            kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, wintypes.DWORD]
            kernel32.WaitForSingleObject.restype = wintypes.DWORD
            self._kernel32 = kernel32
            self._handle = kernel32.OpenProcess(0x00100000 | 0x1000, False, pid) if pid > 0 else None

    def alive(self) -> bool:
        if sys.platform == 'win32':
            return bool(self._handle) and self._kernel32.WaitForSingleObject(self._handle, 0) == 0x102
        if self.pid <= 0 or os.getppid() != self.pid:
            return False
        try:
            os.kill(self.pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        return True


def watch_stop(app: App, stop_file: Path | None, parent_alive=None, interval: float = STOP_POLL_SECONDS) -> threading.Thread:
    """Stops the app when the launcher's stop.request appears or the parent process exits."""

    def loop():
        while not app.stopping.is_set():
            if stop_file is not None and stop_file.exists():
                app.request_stop(f'{stop_file.name} present')
                return
            if parent_alive is not None and not parent_alive():
                app.request_stop('parent process exited')
                return
            app.stopping.wait(interval)

    thread = threading.Thread(target=loop, name='imagegen-stopwatch', daemon=True)
    thread.start()
    return thread


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = 'aiavc-imagegen/1'
    sys_version = ''
    protocol_version = 'HTTP/1.1'

    @property
    def app(self) -> App:
        return self.server.app

    def log_message(self, format, *args):  # noqa: A002 - BaseHTTPRequestHandler signature
        self.app.log('http ' + (format % args))

    def log_request(self, code='-', size='-'):
        # Health and job polls that succeed are not logged; POSTs and errors are.
        if isinstance(code, int) and code < 400 and self.command == 'GET':
            return
        super().log_request(code, size)

    def _send(self, status: int, body: bytes, content_type: str, headers: dict | None = None) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload) -> None:
        self._send(status, protocol.json_bytes(payload), 'application/json; charset=utf-8')

    def _error(self, error: protocol.ProtocolError) -> None:
        self._json(error.status, error.body())

    def _authorized(self) -> bool:
        given = self.headers.get('Authorization', '')
        return hmac.compare_digest(given.encode('utf-8', 'replace'), f'Bearer {self.app.token}'.encode('utf-8'))

    def _route(self, method: str) -> None:
        path = self.path.split('?', 1)[0]
        self._body_read = False
        try:
            if method == 'GET' and path == '/v1/health':
                self._json(200, self.app.health())
                return
            known = path in ('/v1/jobs', '/v1/shutdown', '/v1/health') or _JOB_PATH.fullmatch(path) or _ITEM_PATH.fullmatch(path)
            if not known:
                raise protocol.ProtocolError(protocol.NOT_FOUND, 'no such endpoint')
            if not self._authorized():
                raise protocol.ProtocolError(protocol.UNAUTHORIZED, 'missing or wrong bearer token')
            if method == 'POST' and path == '/v1/jobs':
                self._post_job()
            elif method == 'POST' and path == '/v1/shutdown':
                self._json(202, {'stopping': True})
                self.app.request_stop('POST /v1/shutdown')
            elif method == 'GET' and _ITEM_PATH.fullmatch(path):
                job_id, item_id = _ITEM_PATH.fullmatch(path).groups()
                data, sha256 = self.app.jobs.png(job_id, item_id)
                self._send(200, data, 'image/png', {'X-Content-SHA256': sha256})
            elif method == 'GET' and _JOB_PATH.fullmatch(path):
                view = self.app.jobs.view(_JOB_PATH.fullmatch(path).group(1))
                if view is None:
                    raise protocol.ProtocolError(protocol.NOT_FOUND, 'no such job')
                self._json(200, view)
            else:
                raise protocol.ProtocolError(protocol.METHOD_NOT_ALLOWED, f'{method} is not allowed on {path}')
        except protocol.ProtocolError as error:
            if self.headers.get('Content-Length') not in (None, '0') and not self._body_read:
                # The unread body would be parsed as the next request on this keep-alive connection.
                self.close_connection = True
            self._error(error)
        except Exception as error:  # an unexpected fault answers 500 and keeps the server alive
            self.app.log(f'handler fault: {engine._describe(error)}')
            self.close_connection = True
            self._json(500, {'error': {'code': 'INTERNAL', 'message': type(error).__name__}})

    def _post_job(self) -> None:
        length = self.headers.get('Content-Length')
        if length is None or not length.isdigit():
            self.close_connection = True
            raise protocol.ProtocolError(protocol.LENGTH_REQUIRED, 'Content-Length is required')
        if int(length) > protocol.MAX_BODY_BYTES:
            self.close_connection = True
            raise protocol.ProtocolError(protocol.BODY_TOO_LARGE, f'the body may hold at most {protocol.MAX_BODY_BYTES} bytes')
        raw = self.rfile.read(int(length))
        self._body_read = True
        self.app.accept()
        request = protocol.parse_job(raw)
        view, created = self.app.submit(request)
        self._json(202, dict(view, created=created))

    def do_GET(self):  # noqa: N802
        self._route('GET')

    def do_POST(self):  # noqa: N802
        self._route('POST')

    def do_PUT(self):  # noqa: N802
        self._route('PUT')

    def do_DELETE(self):  # noqa: N802
        self._route('DELETE')


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def make_server(app: App, port: int) -> _Server:
    server = _Server((protocol.HOST, port), Handler)
    server.app = app
    return server


def serve(app: App, server: _Server, *, stop_file: Path | None, parent_alive=None, grace: float = STOP_GRACE_SECONDS,
          poll: float = STOP_POLL_SECONDS) -> bool:
    """Runs until a stop trigger; returns True when the worker ended within the grace period."""
    app.start()
    watch_stop(app, stop_file, parent_alive, poll)
    http_thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.25}, name='imagegen-http', daemon=True)
    http_thread.start()
    app.log(f'listening on http://{protocol.HOST}:{server.server_address[1]}')
    app.stopping.wait()
    server.shutdown()
    server.server_close()
    ended = app.join(grace)
    app.log(f"stopped ({app.stop_reason}); worker {'ended' if ended else 'still busy, exiting anyway'}")
    return ended


def main(argv=None) -> int:
    protocol.utf8_stdio()
    parser = argparse.ArgumentParser(prog='imagegen-server', description='Sidecar sinh ảnh minh hoạ FLUX 3 Image Klein (chỉ 127.0.0.1).')
    parser.add_argument('--port', type=int, default=protocol.DEFAULT_PORT)
    parser.add_argument('--hub', required=True, help='<data>/models/hf-hub')
    parser.add_argument('--out', required=True, help='<data>/imagegen/out')
    parser.add_argument('--parent-pid', type=int, required=True)
    parser.add_argument('--stop-file', required=True, help='<data>/state/stop.request của launcher')
    parser.add_argument('--manifest', default=str(Path(__file__).resolve().with_name(weights.MANIFEST_NAME)))
    parser.add_argument('--full-verify', action='store_true', help='băm lại mọi tệp trọng số dù tem còn mới')
    parser.add_argument('--residency', choices=engine.RESIDENCIES, default='phase')
    args = parser.parse_args(argv)
    token = os.environ.get(protocol.TOKEN_ENV, '')
    if len(token) < protocol.TOKEN_MIN_CHARS or token.strip() != token:
        print(f'imagegen: {protocol.TOKEN_ENV} must hold a token of at least {protocol.TOKEN_MIN_CHARS} characters', file=sys.stderr)
        return EXIT_USAGE
    hub, out = Path(args.hub), Path(args.out)
    engine.set_offline_env(hub)
    try:
        manifest = weights.load_manifest(Path(args.manifest))
    except (OSError, weights.ManifestError) as error:
        print(f'imagegen: bad manifest: {error}', file=sys.stderr)
        return EXIT_USAGE
    parent = ParentWatch(args.parent_pid)
    if not parent.alive():
        print(f'imagegen: parent process {args.parent_pid} is not running', file=sys.stderr)
        return EXIT_PARENT_GONE
    out.mkdir(parents=True, exist_ok=True)
    backend = engine.KleinBackend(weights.snapshot_dir(hub, protocol.MODEL_REPO, protocol.MODEL_REVISION), residency=args.residency)
    app = App(backend=backend, out_dir=out, token=token,
              verifier=lambda: weights.verify(hub, manifest, full=args.full_verify))
    try:
        server = make_server(app, args.port)
    except OSError as error:
        print(f'imagegen: cannot listen on {protocol.HOST}:{args.port}: {error}', file=sys.stderr)
        return EXIT_PORT_IN_USE
    serve(app, server, stop_file=Path(args.stop_file), parent_alive=parent.alive)
    return EXIT_OK


if __name__ == '__main__':
    code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    # A worker still inside a CUDA call must not hold the exit.
    os._exit(code)
