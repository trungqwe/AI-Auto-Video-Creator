"""HOOK-QC: render không dựng hook giữ chỗ (FR-HOOK-008) và VISUAL_HOOK_PRESENT không cho hook giữ chỗ qua.

Kết nối giả trả dòng hook như cp_hook_revisions (không PostgreSQL): hook sinh từ công thức của hooks.json (khoá recipe_template)
bị từ chối với INPUT_NOT_READY hook_placeholder:<id>, kể cả khi thumbnail lấy khung từ hook đó; hook thật (hook_license) đi tiếp
tới bước tìm version đã kiểm.

coveredIds: FR-HOOK-008
"""
from __future__ import annotations

import json
from contextlib import contextmanager
from types import SimpleNamespace

import pytest

from controlplane.api.wiring import render as render_wiring
from render.adapters.activity_inputs import ActivityInputError
from render.domain import content_gates as gates
from render.domain.quality_report import GateStatus, QualityPolicy
from render.ports import output_inspector as port

WORKSPACE = '00000000-0000-4000-8000-000000000001'
SHA = 'a' * 64
PLACEHOLDER = [['width', '1080'], ['height', '1920'], ['fps', '30'], ['duration_ms', '3000'], ['media_sha256', SHA], ['recipe_template', 'lavfi_gradient_pulse_v1'], ['seed_rights_status', 'SELF_GENERATED']]
LICENSED = [['width', '1280'], ['height', '720'], ['fps', '30'], ['duration_ms', '4000'], ['media_sha256', SHA], ['hook_source', 'pixabay'], ['hook_license', 'Pixabay Content License']]
POLICY = QualityPolicy(revision='hook-qc-policy', thresholds={'VISUAL_HOOK_PRESENT': {'min_similarity': 0.8}})


class Connection:
    def __init__(self, hooks):
        self.hooks = hooks
        self.sql = []

    def execute(self, sql, params=()):
        self.sql.append(sql)
        row = None
        if 'cp_hook_revisions' in sql:
            metadata = self.hooks.get(params[1])
            row = None if metadata is None else (json.dumps({'technical_metadata': metadata}),)
        return SimpleNamespace(fetchone=lambda: row, fetchall=lambda: [])


class Manager:
    def __init__(self, hooks):
        self.connection = Connection(hooks)

    @contextmanager
    def borrow_connection(self):
        yield self.connection


def sources(hooks):
    manager = Manager(hooks)
    return manager, render_wiring.ProductionRenderSources(manager, WORKSPACE, profile=None, runtime=SimpleNamespace(staging_root='C:/unused'), clock=lambda: None)


def reason_of(call):
    with pytest.raises(ActivityInputError) as caught:
        call()
    assert caught.value.code == 'INPUT_NOT_READY'
    return str(caught.value).split(': ', 1)[1]


def test_render_refuses_a_placeholder_hook_with_input_not_ready():
    manager, render_sources = sources({'vh-01': PLACEHOLDER, 'ah-01': PLACEHOLDER})
    assert render_wiring.HOOK_PLACEHOLDER_REASON == 'hook_placeholder'
    assert reason_of(lambda: render_sources._hook_source('vh-01')) == 'hook_placeholder:vh-01'
    assert reason_of(lambda: render_sources._hook_source('ah-01')) == 'hook_placeholder:ah-01'
    assert not [sql for sql in manager.connection.sql if 'cp_artifact_versions' in sql]


def test_thumbnail_from_a_placeholder_hook_frame_is_refused():
    _, render_sources = sources({'vh-02': PLACEHOLDER})
    assert reason_of(lambda: render_sources._thumbnail_source('thumb:vh-02', {}, None)) == 'hook_placeholder:vh-02'


def test_licensed_hook_goes_on_to_the_verified_version_lookup():
    assert render_wiring.HOOK_PLACEHOLDER_REASON == 'hook_placeholder'
    manager, render_sources = sources({'pxb-101': LICENSED})
    assert reason_of(lambda: render_sources._hook_source('pxb-101')) == 'hook_version_not_verified:pxb-101'
    assert [sql for sql in manager.connection.sql if 'cp_artifact_versions' in sql]
    _, missing = sources({})
    assert missing._hook_source('pxb-404') is None


def evidence():
    return port.OutputEvidence(visual_hook=port.VisualHookEvidence(evidence_ref='ev-visual', start_ms=0, end_ms=3000, similarity=0.99))


def package(**extra):
    return SimpleNamespace(hook_placement={'hook_time_range': {'start_ms': 0, 'end_ms': 4000}, **extra})


def test_visual_hook_gate_fails_a_package_marked_as_placeholder():
    failed = gates.check_visual_hook_present(evidence(), package(visual_hook_placeholder=True), POLICY)
    assert failed.status is GateStatus.FAILED and failed.reason == gates.VISUAL_HOOK_PLACEHOLDER == 'visual_hook_placeholder'
    assert gates.check_visual_hook_present(None, package(visual_hook_placeholder=True), POLICY).reason == 'visual_hook_placeholder'
    for value in (False, 'true', 1, None):
        assert gates.check_visual_hook_present(evidence(), package(visual_hook_placeholder=value), POLICY).status is GateStatus.PASSED
