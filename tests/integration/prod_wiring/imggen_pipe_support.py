"""IMGGEN-PIPE test support: the real sidecar HTTP server of IMGGEN-SVC (tools/imagegen/server.py) on a free loopback port with a
scripted engine backend (no torch, GPU or weights), and a scripted chat route for the illustration role. Nothing here touches
the network beyond 127.0.0.1.
"""
from __future__ import annotations

import json
import struct
import sys
import threading
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))

from imagegen import engine, protocol, server, weights  # noqa: E402

TOKEN = 't' * 43
VERIFIED = weights.Verification(True, [], [], [], False, False, 0.0)
NOT_PROVISIONED = weights.Verification(False, ['system_prompts.json'], [], [], False, False, 0.0)
PUP_PROMPT = 'You are the prompt upsampler of a text-to-image model (scripted stand-in for the pinned t2i prompt).'


def solid_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xFFFFFFFF)
    row = b'\x00' + bytes(rgb) * width
    return (engine.PNG_SIGNATURE + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(row * height, 1)) + chunk(b'IEND', b''))


class ScriptedBackend:
    """Stands in for engine.KleinBackend: a solid PNG of the requested size per item, coloured by its seed. `gate` (an Event) holds
    every load until it is set; `fail` makes every decode raise (the sidecar reports GENERATION_FAILED, retryable)."""

    def __init__(self, *, gate: threading.Event | None = None, fail: bool = False) -> None:
        self.gate = gate
        self.fail = fail
        self.decoded: list[str] = []

    def requirement(self, phase):
        return engine.PHASE_REQUIREMENT_BYTES[phase]

    def free_vram(self):
        return 20_000_000_000

    def host_available(self):
        return None

    def memory(self):
        return None

    def is_oom(self, error):
        return False

    def fp8_path(self):
        return 'tensorwise'

    def load(self, phase):
        if self.gate is not None:
            self.gate.wait(30)
        return None

    def unload(self, phase):
        return {'peak_allocated_bytes': 1}

    def encode(self, item):
        return ('embeds', item.key)

    def denoise(self, item, embeds):
        return ('latents', item.key)

    def decode(self, item, latents):
        self.decoded.append(item.key)
        if self.fail:
            raise ValueError('scripted decode failure')
        return solid_png(item.width, item.height, (item.seed % 251, (item.seed >> 8) % 251, (item.seed >> 16) % 251))

    def release(self):
        pass


class Sidecar:
    """The real IMGGEN-SVC App and HTTP server; `endpoint_file` is written like the launcher (IMGGEN-LAUNCH) writes it."""

    def __init__(self, tmp_path: Path, endpoint_file: Path, backend: ScriptedBackend | None = None, *, verification=VERIFIED) -> None:
        self.backend = backend or ScriptedBackend()
        self.logs: list[str] = []
        self.app = server.App(backend=self.backend, out_dir=tmp_path / 'imagegen-out', token=TOKEN, verifier=lambda: verification,
                              gpu_memory=lambda: {'free_bytes': 11_000_000_000, 'total_bytes': 12_878_610_432}, log=self.logs.append)
        self.http = server.make_server(self.app, 0)
        self.port = self.http.server_address[1]
        self.endpoint_file = endpoint_file
        endpoint_file.parent.mkdir(parents=True, exist_ok=True)
        endpoint_file.write_text(json.dumps({'url': f'http://127.0.0.1:{self.port}', 'token': TOKEN, 'pid': 4242}), encoding='utf-8')
        self.thread = threading.Thread(target=server.serve, args=(self.app, self.http),
                                       kwargs={'stop_file': None, 'parent_alive': lambda: True, 'grace': 5, 'poll': 0.05}, daemon=True)
        self.thread.start()
        deadline = time.monotonic() + 10
        while self.app.health()['state'] == 'verifying' and time.monotonic() < deadline:
            time.sleep(0.02)

    def jobs(self) -> dict:
        return dict(self.app.jobs.jobs)

    def stop(self) -> None:
        self.app.request_stop('test teardown')
        self.thread.join(10)


def plan_payload(count: int, shots=('wide', 'medium', 'close_detail', 'object', 'aftermath')) -> dict:
    card = {name: f'{name} of a calm overcast harbor morning' for name in
            ('palette', 'light', 'contrast', 'grain', 'lens', 'depth_of_field', 'weather', 'mood')}
    return {'style_card': card, 'requests': [
        {'shot': shot, 'scene_intent': 'scene one', 'description': f'A {shot} view of an empty quay with stacked containers.'}
        for shot in shots[:count]]}


GOOD_CAPTION = ' '.join([
    'A wide documentary photograph of an empty concrete quay at dawn, with rows of plain gray shipping containers stacked three high',
    'under a pale overcast sky. Two small anonymous figures in plain dark jackets walk away from the camera along the edge of the',
    'water, far in the middle distance, their faces turned away. Wet asphalt reflects the soft cool light, and a calm sea fills the',
    'background with a faint haze over the horizon. The palette is muted blue and gray with a little warm light near the cranes, the',
    'contrast is gentle, fine film grain covers the frame, and a moderate wide lens keeps the foreground, the middle ground and the',
    'background in clear focus across the tall vertical frame.'])


class ScriptedChatRoute:
    """invoke_chat of the illustration role: the plan call (system names the planner) answers the next plan, every other call the
    next caption; when the scripts run out it answers a valid plan of the asked count and GOOD_CAPTION. Records every call."""

    def __init__(self, *, plans=(), captions=()) -> None:
        self.plans = list(plans)
        self.captions = list(captions)
        self.calls: list[dict] = []

    def invoke_vision(self, *args, **kwargs):
        raise AssertionError('the illustration role never calls invoke_vision')

    def invoke_chat(self, ai_role, system, text, images=(), *, timeout):
        self.calls.append({'ai_role': ai_role, 'system': system, 'text': text, 'images': tuple(images), 'timeout': timeout})
        if system.startswith('You plan documentary photographs'):
            if self.plans:
                return self.plans.pop(0)
            count = int(text.split('Plan exactly ', 1)[1].split(' ', 1)[0])
            return json.dumps(plan_payload(count))
        return self.captions.pop(0) if self.captions else GOOD_CAPTION

    def plan_calls(self) -> list[dict]:
        return [call for call in self.calls if call['system'].startswith('You plan documentary photographs')]

    def caption_calls(self) -> list[dict]:
        return [call for call in self.calls if not call['system'].startswith('You plan documentary photographs')]


__all__ = ['GOOD_CAPTION', 'NOT_PROVISIONED', 'PUP_PROMPT', 'TOKEN', 'VERIFIED', 'ScriptedBackend', 'ScriptedChatRoute', 'Sidecar',
           'plan_payload', 'protocol', 'solid_png']
