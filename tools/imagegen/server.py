"""HTTP server and job orchestration for FLUX 3 Image Klein sidecar."""

import argparse
import ctypes
import hashlib
import hmac
import http.server
import json
import os
import pathlib
import shutil
import socket
import sys
import threading
import time

import engine
import protocol
import weights


class JobStore:
    def __init__(self, out_dir, clock=time.time):
        self.out_dir = pathlib.Path(out_dir)
        self.clock = clock
        self.out_dir.mkdir(parents=True, exist_ok=True)

    def create(self, job):
        job_id = job['job_id']
        job_dir = self.out_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        items_map = {}
        for it in job['items']:
            items_map[it['item_id']] = {
                'item': it,
                'status': 'queued',
                'attempts': 0,
                'error': None,
                'message': '',
                'sha256': None,
            }
        job_data = {
            'job_id': job_id,
            'body_sha256': protocol.body_sha256(job),
            'created_at': self.clock(),
            'items': items_map,
        }
        self.save(job_data)
        return job_data

    def save(self, job_data):
        job_id = job_data['job_id']
        job_dir = self.out_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        tmp = job_dir / 'job.json.tmp'
        target = job_dir / 'job.json'
        tmp.write_text(json.dumps(job_data, indent=2), encoding='utf-8')
        os.replace(tmp, target)

    def get(self, job_id):
        p = self.out_dir / job_id / 'job.json'
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            return None

    def all_jobs(self):
        jobs = []
        if not self.out_dir.exists():
            return jobs
        for p in sorted(self.out_dir.iterdir()):
            if p.is_dir() and (p / 'job.json').exists():
                j = self.get(p.name)
                if j:
                    jobs.append(j)
        return jobs

    def load_all(self):
        now = self.clock()
        for job_dir in list(self.out_dir.iterdir()):
            if not job_dir.is_dir():
                continue
            j_file = job_dir / 'job.json'
            if not j_file.exists():
                continue
            try:
                data = json.loads(j_file.read_text(encoding='utf-8'))
                if data.get('created_at', 0) < now - protocol.RESULT_TTL_SECONDS:
                    shutil.rmtree(job_dir, ignore_errors=True)
                else:
                    changed = False
                    for it in data.get('items', {}).values():
                        if it.get('status') == 'running':
                            it['status'] = 'queued'
                            changed = True
                    if changed:
                        self.save(data)
            except Exception:
                pass

    def expire(self):
        self.load_all()

    def queued_count(self):
        count = 0
        for job in self.all_jobs():
            for it in job.get('items', {}).values():
                if it.get('status') == 'queued':
                    count += 1
        return count

    def item_png_path(self, job_id, item_id):
        return self.out_dir / job_id / f"{item_id}.png"


class Service:
    def __init__(self, store, backend, token, manifest=None, hub=None, provisioned=True, clock=time.time, gates=None):
        self.store = store
        self.backend = backend
        self.token = token
        self.manifest = manifest
        self.hub = hub
        self.provisioned = provisioned
        self.clock = clock
        self.gates = gates
        self.lock = threading.Lock()
        self.wake = threading.Event()
        self.stop_event = threading.Event()
        self.state = 'idle' if provisioned else 'error'
        self.last_stats = {}
        self.last_activity = clock()
        self.cycle_index = 0
        self.store.load_all()

    def submit(self, job):
        if not self.provisioned or self.state == 'error':
            err_code = 'not_provisioned' if not self.provisioned else 'error'
            return 503, {'error': err_code}

        existing = self.store.get(job['job_id'])
        if existing:
            new_sha = protocol.body_sha256(job)
            if new_sha == existing.get('body_sha256'):
                changed = False
                for it in existing.get('items', {}).values():
                    if it.get('status') == 'failed' and it.get('attempts', 0) < protocol.MAX_ITEM_ATTEMPTS:
                        it['status'] = 'queued'
                        it['error'] = None
                        it['message'] = ''
                        changed = True
                if changed:
                    self.store.save(existing)
                    self.wake.set()
                return 202, self.view(existing)
            else:
                return 409, {'error': 'conflict'}

        if self.store.queued_count() + len(job['items']) > protocol.MAX_QUEUED_ITEMS:
            return 429, {'error': 'queue_full'}

        created = self.store.create(job)
        self.wake.set()
        return 202, self.view(created)

    def view(self, job_data):
        items_list = list(job_data.get('items', {}).values())
        statuses = {it.get('status') for it in items_list}
        if 'running' in statuses:
            st = 'running'
        elif 'queued' in statuses:
            st = 'queued'
        elif all(it.get('status') == 'done' for it in items_list):
            st = 'done'
        elif all(it.get('status') == 'failed' for it in items_list):
            st = 'failed'
        else:
            st = 'done' if any(it.get('status') == 'done' for it in items_list) else 'queued'

        return {
            'job_id': job_data['job_id'],
            'state': st,
            'items': [
                {
                    'item_id': it['item']['item_id'],
                    'status': it['status'],
                    'attempts': it.get('attempts', 0),
                    'error': it.get('error'),
                    'sha256': it.get('sha256'),
                }
                for it in items_list
            ]
        }

    def run_worker(self):
        while not self.stop_event.is_set():
            self.wake.wait(timeout=1.0)
            if self.stop_event.is_set():
                break

            with self.lock:
                work = []
                jobs_to_save = {}
                for job in self.store.all_jobs():
                    for it_id, it_info in job.get('items', {}).items():
                        if it_info.get('status') == 'queued':
                            work.append({
                                'key': f"{job['job_id']}:{it_id}",
                                'job_id': job['job_id'],
                                'item_id': it_id,
                                'item': it_info['item'],
                            })
                            it_info['status'] = 'running'
                            jobs_to_save[job['job_id']] = job
                            if len(work) >= protocol.MAX_ITEMS_PER_CYCLE:
                                break
                    if len(work) >= protocol.MAX_ITEMS_PER_CYCLE:
                        break
                for j in jobs_to_save.values():
                    self.store.save(j)

            if not work:
                if self.clock() - self.last_activity > protocol.IDLE_UNLOAD_SECONDS:
                    self.backend.release()
                self.wake.clear()
                continue

            self.last_activity = self.clock()
            self.state = 'running'
            engine_work = [{'key': w['key'], 'item': w['item']} for w in work]
            res = engine.run_cycle(
                self.backend,
                engine_work,
                probe=engine.MemoryProbe(),
                gates=self.gates,
                cycle_index=self.cycle_index
            )
            item_results = res.get('results', {})
            with self.lock:
                for w in work:
                    job = self.store.get(w['job_id'])
                    if not job:
                        continue
                    it_info = job['items'].get(w['item_id'])
                    if not it_info:
                        continue
                    ires = item_results.get(w['key'])
                    if ires and ires.png:
                        png_path = self.store.item_png_path(w['job_id'], w['item_id'])
                        png_path.write_bytes(ires.png)
                        it_info['status'] = 'done'
                        it_info['sha256'] = hashlib.sha256(ires.png).hexdigest()
                        it_info['error'] = None
                        it_info['message'] = ''
                    else:
                        it_info['status'] = 'failed'
                        it_info['attempts'] = it_info.get('attempts', 0) + 1
                        it_info['error'] = ires.error if ires else protocol.IMAGE_FAILED
                        it_info['message'] = ires.message if ires else 'Generation failed'
                    self.store.save(job)
                self.last_stats = res.get('stats', {}).get('phases', {})
                self.cycle_index += 1
                self.state = 'idle'


def health_payload(service):
    return {
        'status': 'ok',
        'state': service.state,
        'provisioned': bool(service.provisioned),
        'queued_items': service.store.queued_count(),
        'memory': service.last_stats,
        'commit': engine.system_commit(),
    }


def make_handler(service):
    class ServiceHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def _send_json(self, status, payload):
            data = json.dumps(payload).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _check_auth(self):
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer '):
                return False
            token_val = auth[7:].strip()
            return hmac.compare_digest(token_val.encode('utf-8'), service.token.encode('utf-8'))

        def do_GET(self):
            path = self.path.split('?')[0]
            if path == '/v1/health':
                self._send_json(200, health_payload(service))
                return

            if not self._check_auth():
                self._send_json(401, {'error': 'unauthorized'})
                return

            parts = path.strip('/').split('/')
            if len(parts) == 3 and parts[0] == 'v1' and parts[1] == 'jobs':
                job_id = parts[2]
                job = service.store.get(job_id)
                if not job:
                    self._send_json(404, {'error': 'not_found'})
                else:
                    self._send_json(200, service.view(job))
                return

            if len(parts) == 5 and parts[0] == 'v1' and parts[1] == 'jobs' and parts[3] == 'items':
                job_id = parts[2]
                filename = parts[4]
                if not filename.endswith('.png'):
                    self._send_json(404, {'error': 'not_found'})
                    return
                item_id = filename[:-4]
                job = service.store.get(job_id)
                if not job or item_id not in job.get('items', {}):
                    self._send_json(404, {'error': 'not_found'})
                    return
                it_info = job['items'][item_id]
                if it_info.get('status') != 'done':
                    self._send_json(409, {'error': 'not_ready'})
                    return
                png_path = service.store.item_png_path(job_id, item_id)
                if not png_path.exists():
                    self._send_json(404, {'error': 'file_missing'})
                    return
                png_bytes = png_path.read_bytes()
                sha = hashlib.sha256(png_bytes).hexdigest()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.send_header('Content-Length', str(len(png_bytes)))
                self.send_header('X-Content-SHA256', sha)
                self.end_headers()
                self.wfile.write(png_bytes)
                return

            self._send_json(404, {'error': 'not_found'})

        def do_POST(self):
            path = self.path.split('?')[0]
            if not self._check_auth():
                self._send_json(401, {'error': 'unauthorized'})
                return

            if path == '/v1/shutdown':
                self._send_json(202, {'status': 'shutting_down'})
                service.stop_event.set()
                return

            if path == '/v1/jobs':
                content_len = int(self.headers.get('Content-Length', 0))
                if content_len > 1024 * 1024:
                    self._send_json(400, {'error': 'invalid', 'field': 'body'})
                    return
                body_bytes = self.rfile.read(content_len)
                try:
                    raw_dict = json.loads(body_bytes.decode('utf-8'))
                except Exception:
                    self._send_json(400, {'error': 'invalid', 'field': 'body'})
                    return
                try:
                    parsed_job = protocol.parse_job(raw_dict)
                except protocol.ProtocolError as pe:
                    self._send_json(pe.status, {'error': 'invalid', 'field': pe.field})
                    return
                status, payload = service.submit(parsed_job)
                self._send_json(status, payload)
                return

            self._send_json(404, {'error': 'not_found'})

    return ServiceHandler


class LoopbackServer(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, 'SO_EXCLUSIVEADDRUSE'):
            try:
                self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            except Exception:
                pass
        super().server_bind()


def make_server(service, port):
    handler_cls = make_handler(service)
    return LoopbackServer((protocol.HOST, port), handler_cls)


def parent_alive(pid):
    if pid is None:
        return True
    if sys.platform == 'win32':
        SYNCHRONIZE = 0x00100000
        handle = ctypes.windll.kernel32.OpenProcess(SYNCHRONIZE, False, int(pid))
        if not handle:
            return False
        try:
            res = ctypes.windll.kernel32.WaitForSingleObject(handle, 0)
            return res != 0
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    else:
        try:
            os.kill(int(pid), 0)
            return True
        except OSError:
            return False


def watch_stop(service, server, stop_file, parent_pid, interval=0.5):
    while not service.stop_event.is_set():
        if stop_file and pathlib.Path(stop_file).exists():
            service.stop_event.set()
            break
        if parent_pid is not None and not parent_alive(parent_pid):
            service.stop_event.set()
            break
        time.sleep(interval)
    try:
        server.shutdown()
    except Exception:
        pass


def main(argv=None):
    parser = argparse.ArgumentParser(description="Imagegen HTTP sidecar service")
    parser.add_argument("--port", type=int, default=protocol.DEFAULT_PORT)
    parser.add_argument("--hub", default=str(weights.default_hub()))
    parser.add_argument("--out", required=True)
    parser.add_argument("--parent-pid", type=int, default=None)
    parser.add_argument("--stop-file", default=None)
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--full-verify", action="store_true")
    parser.add_argument("--residency", choices=["auto", "phase", "keep"], default="auto")

    args = parser.parse_args(argv)
    protocol.utf8_stdio()
    token = os.environ.get(protocol.TOKEN_ENV, "")
    if len(token) < protocol.TOKEN_MIN_LENGTH:
        sys.stderr.write(f"Error: {protocol.TOKEN_ENV} must be at least {protocol.TOKEN_MIN_LENGTH} characters.\n")
        return 2

    hub_path = pathlib.Path(args.hub)
    manifest = weights.load_manifest(args.manifest)
    v_res = weights.verify(hub_path, manifest, full=args.full_verify)

    store = JobStore(args.out)
    if not v_res.ok:
        backend = engine.KleinBackend(hub_path, manifest, args.residency)
        service = Service(store, backend, token, manifest=manifest, hub=hub_path, provisioned=False)
    else:
        backend = engine.KleinBackend(hub_path, manifest, args.residency)
        service = Service(store, backend, token, manifest=manifest, hub=hub_path, provisioned=True)

    worker_thread = threading.Thread(target=service.run_worker, daemon=True)
    worker_thread.start()

    server = make_server(service, args.port)
    watcher_thread = threading.Thread(target=watch_stop, args=(service, server, args.stop_file, args.parent_pid), daemon=True)
    watcher_thread.start()

    try:
        server.serve_forever()
    finally:
        service.stop_event.set()
        backend.release()
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
