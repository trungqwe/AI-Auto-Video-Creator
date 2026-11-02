"""IMGGEN-PIPE: ImagegenClient (production_ports/imagegen_client.py) against the real sidecar server of IMGGEN-SVC with a scripted
engine: endpoint file of the launcher, token, idempotent submit, item PNG with its sha256, and every failure as a fixed code.
No database, GPU, torch or network beyond 127.0.0.1.

coveredIds: OI-CP7-11-Q2
"""
from __future__ import annotations

import ast
import hashlib
import json
import threading
import time
from pathlib import Path

import pytest

from controlplane.infrastructure.production_ports import imagegen_client as client_module
from controlplane.infrastructure.production_ports.imagegen_client import (
    ImagegenBusy, ImagegenClient, ImagegenRejected, ImagegenUnavailable, read_endpoint)
from tests.integration.prod_wiring.imggen_pipe_support import NOT_PROVISIONED, TOKEN, ScriptedBackend, Sidecar, protocol

ROOT = Path(__file__).resolve().parents[3]
JOB = 'c' * 32


@pytest.fixture
def sidecars():
    started = []
    yield started
    for item in started:
        item.stop()


def start(sidecars, tmp_path, **kwargs) -> Sidecar:
    sidecar = Sidecar(tmp_path, tmp_path / 'data' / 'imagegen' / 'endpoint.json', **kwargs)
    sidecars.append(sidecar)
    return sidecar


def body(count=2, job_id=JOB):
    return {'job_id': job_id, 'items': [{'item_id': f'shot-{n}', 'caption': f'A plain wide photograph of an empty quay, variant {n}.',
                                         'width': 864, 'height': 1536, 'steps': 16, 'seed': protocol.derive_seed(job_id, f'shot-{n}')}
                                        for n in range(count)]}


def wait_done(client, job_id=JOB):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        view = client.job(job_id)
        if view and all(item['state'] in ('done', 'failed') for item in view['items']):
            return view
        time.sleep(0.05)
    raise AssertionError('job did not finish')


def test_the_client_reads_the_launcher_endpoint_and_gets_each_png_with_its_sha256(sidecars, tmp_path):
    sidecar = start(sidecars, tmp_path)
    client = ImagegenClient(sidecar.endpoint_file)
    assert client.health()['state'] == 'idle' and client.job(JOB) is None
    first = client.submit(body())
    again = client.submit(body())
    assert first['job_id'] == again['job_id'] == JOB and first['created'] is True and again['created'] is False
    view = wait_done(client)
    assert [item['state'] for item in view['items']] == ['done', 'done']
    for item in view['items']:
        data, sha256 = client.png(JOB, item['item_id'])
        assert sha256 == hashlib.sha256(data).hexdigest() == item['sha256'] and data.startswith(b'\x89PNG')
    assert TOKEN not in repr(client) and TOKEN not in repr(read_endpoint(sidecar.endpoint_file))


def test_another_body_under_the_same_job_id_is_a_conflict_and_an_unknown_job_is_none(sidecars, tmp_path):
    client = ImagegenClient(start(sidecars, tmp_path).endpoint_file)
    client.submit(body(1))
    with pytest.raises(ImagegenRejected) as caught:
        client.submit(body(2))
    assert caught.value.code == 'job_conflict' and caught.value.status == 409
    assert client.job('d' * 32) is None


def test_missing_or_malformed_endpoint_refused_port_and_wrong_token_are_unavailable(sidecars, tmp_path):
    with pytest.raises(ImagegenUnavailable) as missing:
        ImagegenClient(tmp_path / 'nowhere.json').job(JOB)
    with pytest.raises(ImagegenUnavailable) as unset:
        ImagegenClient(None).health()
    assert missing.value.code == unset.value.code == 'endpoint_missing'
    bad = tmp_path / 'bad.json'
    for content in ('{', json.dumps({'url': 'http://10.0.0.5:57030', 'token': TOKEN}), json.dumps({'url': 'http://127.0.0.1:57030', 'token': 'short'})):
        bad.write_text(content, encoding='utf-8')
        with pytest.raises(ImagegenUnavailable) as caught:
            ImagegenClient(bad).health()
        assert caught.value.code == 'endpoint_invalid'
    sidecar = start(sidecars, tmp_path)
    wrong = tmp_path / 'wrong.json'
    wrong.write_text(json.dumps({'url': f'http://127.0.0.1:{sidecar.port}', 'token': 'w' * 43}), encoding='utf-8')
    with pytest.raises(ImagegenUnavailable) as unauthorized:
        ImagegenClient(wrong).job(JOB)
    assert unauthorized.value.code == 'unauthorized' and 'w' * 43 not in str(unauthorized.value)
    sidecar.stop()
    with pytest.raises(ImagegenUnavailable) as refused:
        ImagegenClient(sidecar.endpoint_file, timeout=2.0).health()
    assert refused.value.code == 'connection_failed'


def test_a_sidecar_without_weights_is_unavailable_for_health_and_submit(sidecars, tmp_path):
    client = ImagegenClient(start(sidecars, tmp_path, verification=NOT_PROVISIONED).endpoint_file)
    for call in (client.health, lambda: client.submit(body())):
        with pytest.raises(ImagegenUnavailable) as caught:
            call()
        assert caught.value.code == 'not_provisioned'


def test_an_item_not_ready_is_rejected_and_failed_items_report_retryable_errors(sidecars, tmp_path):
    gate = threading.Event()
    client = ImagegenClient(start(sidecars, tmp_path, backend=ScriptedBackend(gate=gate)).endpoint_file)
    client.submit(body(1))
    with pytest.raises(ImagegenRejected) as caught:
        client.png(JOB, 'shot-0')
    assert caught.value.code == 'item_not_ready'
    gate.set()
    wait_done(client)
    failing = ImagegenClient(start(sidecars, tmp_path / 'b', backend=ScriptedBackend(fail=True)).endpoint_file)
    failing.submit(body(1))
    item = wait_done(failing)['items'][0]
    assert item['state'] == 'failed' and item['error']['code'] == 'GENERATION_FAILED' and item['error']['retryable'] is True


def test_a_full_queue_is_busy(tmp_path):
    class Answer:
        status = 429

        def read(self, limit):
            return b'{"error": {"code": "QUEUE_FULL"}}'

        def getheaders(self):
            return []

    class Connection:
        def __init__(self, host, port, timeout):
            assert host == '127.0.0.1'

        def request(self, *args, **kwargs):
            pass

        def getresponse(self):
            return Answer()

        def close(self):
            pass

    path = tmp_path / 'endpoint.json'
    path.write_text(json.dumps({'url': 'http://127.0.0.1:57030', 'token': TOKEN}), encoding='utf-8')
    with pytest.raises(ImagegenBusy) as caught:
        ImagegenClient(path, connect=Connection).submit(body())
    assert caught.value.code == 'queue_full'


def test_the_client_restates_the_sidecar_protocol_and_never_imports_tools():
    assert (client_module.SERVICE_NAME, client_module.TOKEN_MIN_CHARS, client_module.MAX_ITEMS_PER_JOB) == (
        protocol.SERVICE_NAME, protocol.TOKEN_MIN_CHARS, protocol.MAX_ITEMS_PER_JOB)
    assert client_module.LOOPBACK_HOST == protocol.HOST == '127.0.0.1'
    source = (ROOT / 'src' / 'controlplane' / 'infrastructure' / 'production_ports' / 'imagegen_client.py').read_text(encoding='utf-8')
    modules = {node.module for node in ast.walk(ast.parse(source)) if isinstance(node, ast.ImportFrom)}
    modules |= {alias.name for node in ast.walk(ast.parse(source)) if isinstance(node, ast.Import) for alias in node.names}
    assert not {name for name in modules if name.split('.')[0] in ('tools', 'imagegen', 'src', 'requests', 'urllib')}
    lowered = source.lower()
    assert 'os.environ' not in source and 'mo' + 'ck' not in lowered and 'fa' + 'ke' not in lowered
