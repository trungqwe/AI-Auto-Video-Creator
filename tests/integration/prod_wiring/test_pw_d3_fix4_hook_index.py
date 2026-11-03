"""PW-D3-FIX4: hook giữ chỗ (gradient, tiếng quét) không còn là ứng viên ở production; hook có giấy phép được qua quyền; AI thấy chỉ mục nội dung của hook.

Kho hook trong bộ nhớ (HookHistory của C), không DB, không mạng.

coveredIds: FR-HOOK-004, FR-HOOK-005, FR-HOOK-008
"""
from __future__ import annotations

import ast
import contextlib
import datetime
import pathlib

import pytest

from catalog.application.hooks import HookHistory, import_hook
from catalog.domain.hooks import HookKind
from creative.adapters.hook_candidates import PostgresHookCandidates
from creative.domain.asset_selection import SafetyRightsPolicy, SelectionRejected

ROOT = pathlib.Path(__file__).resolve().parents[3]
LAUNCHER = ROOT / 'tools' / 'launcher' / 'launcher.py'
POLICY = SafetyRightsPolicy(revision='safe-r1', allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',))


def clock():
    return datetime.datetime(2026, 11, 3, tzinfo=datetime.timezone.utc)


def placeholder(history, hook_id, kind):
    technical = (('duration_ms', '3000'), ('media_sha256', 'a' * 64), ('recipe_template', 'lavfi_gradient_pulse_v1'), ('seed_rights_status', 'SELF_GENERATED'))
    import_hook(history, hook_id=hook_id, kind=kind, artifact_version_ref=f'seed:{hook_id}:sha256:' + 'a' * 64,
                tags=('seed', kind.value, hook_id), description='Seed hook ' + hook_id, technical_metadata=technical)


def licensed(history, hook_id, kind, license_code, *, author='maker', attribution='Video by maker from Pixabay', tags=('police', 'night', 'siren')):
    technical = (('duration_ms', '4000'), ('width', '1280'), ('height', '720'), ('media_sha256', 'b' * 64), ('hook_source', 'pixabay'),
                 ('hook_license', license_code), ('hook_author', author), ('hook_attribution', attribution), ('hook_page_url', 'https://pixabay.com/videos/x-1/'))
    import_hook(history, hook_id=hook_id, kind=kind, artifact_version_ref=f'stock:{hook_id}:sha256:' + 'b' * 64, tags=tags,
                description='police car lights at night in the rain', technical_metadata=technical)


def port(history, **kwargs):
    return PostgresHookCandidates(lambda workspace_id: contextlib.nullcontext(history), safety_policy_revision='safe-r1', **kwargs)


@pytest.fixture
def library():
    history = HookHistory(clock=clock)
    for n in range(1, 3):
        placeholder(history, f'vh-0{n}', HookKind.VISUAL_HOOK)
        placeholder(history, f'ah-0{n}', HookKind.AUDIO_HOOK)
    licensed(history, 'pxb-11', HookKind.VISUAL_HOOK, 'Pixabay Content License')
    licensed(history, 'fs-21', HookKind.AUDIO_HOOK, 'CC-BY-4.0', attribution='"Siren" by rec licensed under CC-BY-4.0', tags=('siren', 'alarm'))
    return history


def test_production_port_drops_placeholders_and_keeps_licensed_hooks(library) -> None:
    hooks = port(library, exclude_placeholders=True)
    visual = hooks.visual_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')
    audio = hooks.audio_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')
    assert [item.hook_id for item in visual] == ['pxb-11'] and [item.hook_id for item in audio] == ['fs-21']
    assert dict(visual[0].safety_rights_status) == {'rights_status': 'Pixabay Content License', 'rights_cleared': True}
    assert dict(audio[0].safety_rights_status) == {'rights_status': 'CC-BY-4.0', 'rights_cleared': True}
    assert all(POLICY.allows(item.availability, item.safety_rights_status) for item in visual + audio)
    assert visual[0].provenance['placeholder'] is False


def test_every_candidate_carries_the_content_index_for_the_ai(library) -> None:
    item = port(library, exclude_placeholders=True).visual_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')[0]
    index = item.provenance['index']
    assert index['tags'] == ['police', 'night', 'siren'] and index['description'] == 'police car lights at night in the rain'
    assert index['source'] == 'pixabay' and index['license'] == 'Pixabay Content License'
    assert index['author'] == 'maker' and index['attribution'] == 'Video by maker from Pixabay' and index['page_url'] == 'https://pixabay.com/videos/x-1/'


@pytest.mark.parametrize('method, kind', [('visual_hook_candidates', 'visual_hook'), ('audio_hook_candidates', 'audio_hook')])
def test_only_placeholders_is_refused_with_a_clear_reason(method, kind) -> None:
    history = HookHistory(clock=clock)
    placeholder(history, 'vh-01', HookKind.VISUAL_HOOK)
    placeholder(history, 'ah-01', HookKind.AUDIO_HOOK)
    with pytest.raises(SelectionRejected) as caught:
        getattr(port(history, exclude_placeholders=True), method)(workspace_id='ws', snapshot_ref='snap-1')
    assert (caught.value.code, caught.value.reason, caught.value.field) == ('INPUT_NOT_READY', f'only_placeholder_{kind}_candidates', kind)


def test_empty_library_keeps_the_old_reason() -> None:
    with pytest.raises(SelectionRejected) as caught:
        port(HookHistory(clock=clock), exclude_placeholders=True).visual_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')
    assert caught.value.reason == 'no_visual_hook_candidates'


def test_default_port_keeps_placeholders_marked(library) -> None:
    visual = port(library).visual_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')
    by_id = {item.hook_id: item for item in visual}
    assert sorted(by_id) == ['pxb-11', 'vh-01', 'vh-02']
    assert by_id['vh-01'].provenance['placeholder'] is True
    assert dict(by_id['vh-01'].safety_rights_status) == {'rights_status': 'SELF_GENERATED', 'rights_cleared': True}


@pytest.mark.parametrize('license_code, author, attribution', [
    ('CC-BY-4.0', 'rec', ''), ('CC-BY-3.0', '', 'x by y'), ('CC-BY-NC-4.0', 'rec', 'x'), ('Unknown', 'rec', 'x')])
def test_unclear_rights_are_not_cleared(license_code, author, attribution) -> None:
    history = HookHistory(clock=clock)
    licensed(history, 'fs-9', HookKind.AUDIO_HOOK, license_code, author=author, attribution=attribution)
    item = port(history, exclude_placeholders=True).audio_hook_candidates(workspace_id='ws', snapshot_ref='snap-1')[0]
    assert item.safety_rights_status['rights_cleared'] is False and not POLICY.allows(item.availability, item.safety_rights_status)


def test_exclude_placeholders_must_be_a_bool() -> None:
    assert port(HookHistory(clock=clock), exclude_placeholders=False) is not None
    with pytest.raises(TypeError):
        port(HookHistory(clock=clock), exclude_placeholders='yes')


def test_production_launcher_builds_the_port_without_placeholders() -> None:
    text = LAUNCHER.read_text(encoding='utf-8')
    calls = [node for node in ast.walk(ast.parse(text)) if isinstance(node, ast.Call) and getattr(node.func, 'id', None) == 'PostgresHookCandidates']
    assert len(calls) == 1
    keywords = {kw.arg: kw.value for kw in calls[0].keywords}
    assert isinstance(keywords.get('exclude_placeholders'), ast.Constant) and keywords['exclude_placeholders'].value is True
