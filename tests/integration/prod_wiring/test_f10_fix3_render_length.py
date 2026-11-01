"""F-10-FIX3 (R36): render_plan lấy -t đầu ra từ voice_duration_ms của word timing, không lấy cuối timeline kế hoạch.

cp_word_timings có UNIQUE(timing_artifact_ref) và trigger append-only nên không có revision 2 cùng ref; test chèn revision 1 với voice_duration_ms mong muốn trước build_world (insert_timing của PW-F3 dùng ON CONFLICT DO NOTHING nên bỏ qua).

coveredIds: CT-RND-004
"""
from __future__ import annotations

import json
from typing import Any

import pytest

from render.adapters.activity_inputs import ActivityInputError
from render.domain.resolve_package import resolve_render_package
from tests.integration.prod_wiring.test_pw_f3_render_inputs import (  # noqa: F401
    TIMING_REF,
    build_world,
    manager,
    pinned,
    service,
    timing_payload,
)


def seed_timing(db: Any, **changes: Any) -> None:
    payload = {key: value for key, value in {**timing_payload(), **changes}.items() if value is not None}
    with db.connect() as conn:
        conn.execute(
            'INSERT INTO controlplane.cp_word_timings (workspace_id, record_key, revision, payload, timing_artifact_ref) VALUES (%s::uuid, %s, 1, %s::jsonb, %s)',
            (db.workspace_id, TIMING_REF, json.dumps(payload), TIMING_REF),
        )


def resolved(db, manager, pinned, tmp_path):
    world = build_world(db, manager, pinned, tmp_path)
    return world, resolve_render_package(world.sources.resolve_inputs(world.refs), world.plan_port)


def output_t(argv):
    shortest = argv.index('-shortest')
    assert argv[shortest + 1] == '-t'
    return argv[shortest + 2]


@pytest.mark.parametrize('voice_ms,expected', [(5250, '5.250'), (3950, '3.950')])
def test_render_plan_output_length_is_the_measured_voice_duration(pw_database, manager, pinned, tmp_path, voice_ms, expected):
    seed_timing(pw_database, voice_duration_ms=voice_ms)
    world, record = resolved(pw_database, manager, pinned, tmp_path)
    assert record.timeline['duration_ms'] == 4000
    plan = world.sources.render_plan(record, 'render:att:1')
    assert output_t(plan.command_spec.argv) == expected


def test_render_plan_without_voice_duration_ms_is_input_not_ready(pw_database, manager, pinned, tmp_path):
    seed_timing(pw_database, voice_duration_ms=None)
    world, record = resolved(pw_database, manager, pinned, tmp_path)
    with pytest.raises(ActivityInputError) as info:
        world.sources.render_plan(record, 'render:att:1')
    assert info.value.code == 'INPUT_NOT_READY'
    assert 'voice_duration_missing' in str(info.value)
