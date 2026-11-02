"""PW-D3-FIX3 (CLOSURE_NOTE CP7/RG-13): không có video chỉ có ảnh nền; chạy offline

coveredIds: CT-AI-006, CT-AI-007, CT-RND-003, DQ-11, OI-ADAPT-10
"""
from __future__ import annotations

import dataclasses
import pathlib

import pytest

from controlplane.api.wiring.render import NO_ILLUSTRATION_AVAILABLE, require_illustration
from controlplane.api.wiring import render as render_wiring
from controlplane.api.wiring.workflow import RenderImage
from creative.domain.asset_selection import (
    HookCandidate,
    ORIGIN_SEED,
    MediaCandidate,
    SafetyRightsPolicy,
    ScoringWeights,
    SelectionRejected,
    ThumbnailCandidate,
    select_creative_assets,
)
from creative.domain.production_plan import (
    SEED_SHARE_MAX_PERCENT,
    PlanRejected,
    build_production_plan,
    seed_share_within_limit,
    seed_time_ms,
)
from creative.domain.script import ScriptSegment, ScriptVersion
from render.adapters.activity_inputs import ActivityInputError
from tests.integration.adapt.e_media.test_adapt_e_media_fix4_rg13 import (
    CLEAN,
    Route,
    World,
    answer,
    choice,
    det,
    run_chain as run_safety,
    sha,
)
from voice.adapters.activity_inputs import MediaArtifact
from voice.domain.processing import ArtifactRef

WS = 'ws-1'
POLICY = SafetyRightsPolicy(revision='safe-v1', allowed_availability=('AVAILABLE',), required_flags=('rights_cleared',), blocked_flags=('unsafe',))
WEIGHTS = ScoringWeights(semantic=0.6, technical=0.4, recent_usage_penalty=0.1)
NUDE = answer({'nudity_sexual': 0.9}, [det('nudity_sexual', 0.9)])


@pytest.fixture(autouse=True)
def pinned_ffmpeg():
    if not pathlib.Path('C:/ffmpeg/bin/ffmpeg.exe').is_file():
        pytest.fail(
            'BLOCKED_EXTERNAL: pinned FFmpeg C:/ffmpeg/bin/ffmpeg.exe is required; no skip and no fallback is permitted.',
            pytrace=False,
        )


# --- Phần 1: chọn tài nguyên -------------------------------------------------------------------------------------


def media(asset_id, origin):
    return MediaCandidate(
        media_asset_id=asset_id,
        rendition_ref=f'{asset_id}-rend',
        artifact_version_ref=f'{asset_id}-av',
        provenance={} if origin is None else {'origin': origin},
        semantic_match_components={'topic': 0.5},
        technical_fitness={'score': 0.5},
        availability='AVAILABLE',
        safety_rights_status={'rights_cleared': True},
        recent_usage_summary={'times_used': 0},
        reason_codes=('topic',),
    )


def ref(ref_type, ref_id, revision_id):
    return {'workspace_id': WS, 'ref_type': ref_type, 'ref_id': ref_id, 'revision_id': revision_id}


def select(candidates, assets):
    return select_creative_assets(
        workspace_id=WS,
        snapshot_ref='snap-1',
        script_ref='sv-1',
        angle_ref='angle-1',
        media_candidates=candidates,
        visual_hook_candidates=[
            HookCandidate(
                hook_kind='visual_hook', hook_id='vh-1', revision_id='vh-1-r1', availability='AVAILABLE',
                safety_rights_status={'rights_cleared': True}, semantic_match_components={}, provenance={'origin': 'hook_library'},
            )
        ],
        audio_hook_candidates=[
            HookCandidate(
                hook_kind='audio_hook', hook_id='ah-1', revision_id='ah-1-r1', availability='AVAILABLE',
                safety_rights_status={'rights_cleared': True}, semantic_match_components={}, provenance={'origin': 'hook_library'},
            )
        ],
        thumbnail_candidates=[
            ThumbnailCandidate(
                thumbnail_id='th-1', revision_id='th-1-r1', subject_refs=('e-1',), crop_focus={'x': 0.5, 'y': 0.4},
                overlay_intent='title', availability='AVAILABLE', safety_rights_status={'rights_cleared': True},
                semantic_match_components={}, provenance={'origin': 'catalog'},
            )
        ],
        proposal={
            'visual_hook': ref('visual_hook', 'vh-1', 'vh-1-r1'),
            'audio_hook': ref('audio_hook', 'ah-1', 'ah-1-r1'),
            'thumbnail': ref('thumbnail', 'th-1', 'th-1-r1'),
            'scenes': [
                {'scene_id': f'sc-{i}', 'ref': ref('media_asset', a, f'{a}-av'), 'rationale': 'shot'}
                for i, a in enumerate(assets, start=1)
            ],
            'music_intents': [],
            'sfx_intents': [],
            'rationale': 'r',
        },
        safety_policy=POLICY,
        music_sfx_policy_revision='music-v1',
        preset_registry_revision='preset-v1',
        weights=WEIGHTS,
    )


def test_a_seed_scene_is_refused_while_an_article_image_is_eligible():
    with pytest.raises(SelectionRejected) as caught:
        select([media('img-a', 'article'), media('s-1', 'seed')], ['img-a', 's-1'])
    assert (caught.value.code, caught.value.reason, caught.value.field) == (
        'invalid_proposal', 'seed_scene_while_illustration_eligible', 'scenes[1].ref',
    )


def test_an_ai_generated_image_counts_as_an_illustration():
    candidates = [media('img-ai', 'ai_generated'), media('s-1', 'seed')]
    result = select(candidates, ['img-ai', 'img-ai'])
    assert [a.origin for a in result.assignments] == ['ai_generated', 'ai_generated']
    with pytest.raises(SelectionRejected) as caught:
        select(candidates, ['s-1'])
    assert caught.value.reason == 'seed_scene_while_illustration_eligible'


def test_a_candidate_without_origin_counts_as_an_illustration_and_its_payload_has_no_origin_key():
    candidates = [media('img-x', None), media('s-1', 'seed')]
    result = select(candidates, ['img-x'])
    assert result.assignments[0].origin is None
    assert 'origin' not in result.assignments[0].to_payload()
    with pytest.raises(SelectionRejected) as caught:
        select(candidates, ['s-1'])
    assert caught.value.reason == 'seed_scene_while_illustration_eligible'


def test_seed_scenes_are_allowed_when_no_candidate_has_another_origin():
    result = select([media('s-1', 'seed'), media('s-2', 'seed')], ['s-1', 's-2'])
    assert [a.origin for a in result.assignments] == ['seed', 'seed']


# --- Phần 2: kế hoạch sản xuất -----------------------------------------------------------------------------------


def script():
    return ScriptVersion(
        script_version_id='sv-1',
        language='en',
        hook_intent='hook',
        thumbnail_transition='fade',
        segments=(
            ScriptSegment(
                segment_id='s1', order=0, text='Hello world', claim_mode='transition', scene_intent='scene 1',
                source_refs=(), disclosure=None, word_count=2, estimated_seconds=1.0,
            ),
        ),
        pronunciation_hints=(),
        speech_rate=2.0,
        estimated_duration_seconds=1.0,
    )


def plan_raw(scenes):
    segments = []
    for scene_id, visuals in scenes:
        segments.append({
            'scene_id': scene_id,
            'start_ms': visuals[0][1],
            'end_ms': visuals[-1][2],
            'transition_intent': 'hard cut',
            'visuals': [
                {'media_asset_id': m, 'start_ms': s, 'end_ms': e, 'crop_intent': 'center', 'overlay_intent': 'none', 'effect_intent': 'none'}
                for m, s, e in visuals
            ],
        })
    return {
        'timeline': {'segments': segments},
        'hook_placement': {'hook_time_range': {'start_ms': 0, 'end_ms': 5000}, 'thumbnail_time_range': {'start_ms': 1200, 'end_ms': 2400}},
        'voice_profile_intent': {'direction': 'warm', 'pace': 'steady', 'emotion': 'curious'},
        'music_cues': [],
        'sfx_cues': [],
        'subtitle_style_intent': {'style': 'bold', 'karaoke': True, 'highlight_intent': 'active word'},
        'allowed_fallbacks': [],
        'output_metadata_requirement': 'english title, caption and 3-4 hashtags (CT-AI-009)',
    }


def plan(selection, scenes):
    return build_production_plan(
        plan_raw(scenes), production_plan_id='pp-1', script=script(), selection=selection, preset_revision_ref='preset-r1',
    )


def test_one_article_image_fills_six_scenes_and_the_plan_has_no_seed_time():
    selection = select([media('img-a', 'article'), media('s-1', 'seed')], ['img-a'] * 6)
    assert all(a.origin == 'article' for a in selection.assignments)
    built = plan(selection, [(f'sc-{i}', [('img-a', (i - 1) * 10000, i * 10000)]) for i in range(1, 7)])
    timeline = built.timeline
    assert seed_time_ms(timeline['segments'], lambda v: v.get('origin') == 'seed') == (0, 60000)
    assert all(v['origin'] == 'article' for scene in timeline['segments'] for v in scene['visuals'])


def test_the_plan_rejects_more_than_15_percent_seed_time_and_accepts_exactly_15():
    base = select([media('img-a', 'article'), media('s-1', 'seed')], ['img-a', 'img-a'])
    seed = dataclasses.replace(
        base.assignments[1], media_asset_id='s-1', rendition_ref='s-1-rend', artifact_version_ref='s-1-av', origin='seed',
    )
    selection = dataclasses.replace(base, assignments=(base.assignments[0], seed))
    ok = plan(selection, [('sc-1', [('img-a', 0, 10000)]), ('sc-2', [('img-a', 10000, 17000), ('s-1', 17000, 20000)])])
    assert seed_time_ms(ok.timeline['segments'], lambda v: v.get('origin') == 'seed') == (3000, 20000)
    with pytest.raises(PlanRejected) as caught:
        plan(selection, [('sc-1', [('img-a', 0, 10000)]), ('sc-2', [('img-a', 10000, 16000), ('s-1', 16000, 20000)])])
    assert (caught.value.code, caught.value.reason, caught.value.field) == ('seed_share_exceeded', 'seed_share_above_max', 'timeline.segments')


def test_a_selection_of_seed_images_only_is_not_limited_by_the_plan():
    selection = select([media('s-1', 'seed'), media('s-2', 'seed')], ['s-1', 's-2'])
    built = plan(selection, [('sc-1', [('s-1', 0, 10000)]), ('sc-2', [('s-2', 10000, 20000)])])
    assert seed_time_ms(built.timeline['segments'], lambda v: v.get('origin') == 'seed') == (20000, 20000)


def test_seed_time_ms_merges_overlapping_visuals_and_clips_them_to_their_scene():
    segments = [
        {'start_ms': 0, 'end_ms': 10000, 'visuals': [
            {'start_ms': 0, 'end_ms': 6000, 'seed': True}, {'start_ms': 4000, 'end_ms': 8000, 'seed': True},
        ]},
        {'start_ms': 10000, 'end_ms': 20000, 'visuals': [{'start_ms': 9000, 'end_ms': 12000, 'seed': True}]},
    ]
    assert seed_time_ms(segments, lambda v: v['seed']) == (10000, 20000)
    assert seed_share_within_limit(15, 100) is True
    assert seed_share_within_limit(16, 100) is False
    assert seed_share_within_limit(0, 0) is True


def test_wiring_render_seed_rule_matches_creative():
    assert render_wiring._SEED_ORIGIN == ORIGIN_SEED
    assert render_wiring._SEED_SHARE_MAX_PERCENT == SEED_SHARE_MAX_PERCENT
    segments = [
        {'start_ms': 0, 'end_ms': 10000, 'visuals': [
            {'start_ms': 0, 'end_ms': 6000, 'seed': True}, {'start_ms': 4000, 'end_ms': 8000, 'seed': True},
        ]},
        {'start_ms': 10000, 'end_ms': 20000, 'visuals': [{'start_ms': 9000, 'end_ms': 12000, 'seed': True}]},
        {'start_ms': 20000, 'end_ms': 30000, 'visuals': [{'start_ms': 20000, 'end_ms': 30000, 'seed': False}]},
    ]
    assert render_wiring.seed_time_ms(segments, lambda v: v.get('seed')) == seed_time_ms(segments, lambda v: v.get('seed'))
    for seed_ms, timeline_ms in [(0, 0), (15, 100), (16, 100), (3000, 20000), (20000, 20000)]:
        assert render_wiring.seed_share_within_limit(seed_ms, timeline_ms) == seed_share_within_limit(seed_ms, timeline_ms)


# --- Phần 3: E lấy ảnh khác của job cho ảnh bị loại --------------------------------------------------------------


def seeds(world, count):
    world.seeds = [
        MediaArtifact(ArtifactRef(f'art-seed-{i}', sha(f'seed-{i}'.encode())), 'png', 'image/png', 1) for i in range(count)
    ]


def test_an_excluded_image_takes_the_image_of_another_selected_media_before_any_seed(tmp_path):
    world = World(tmp_path, Route())
    a = world.add_image('a', 160, 120, CLEAN)
    b = world.add_image('b', 160, 120, NUDE)
    c = world.add_image('c', 160, 120, CLEAN)
    seeds(world, 2)
    chain = run_safety(world, [a, b, c])
    picked = choice(world, chain, b)
    assert picked.reason == 'image_fallback'
    assert picked.artifact == world.items['media-a'][0]
    assert picked.artifact not in [seed.ref for seed in world.seeds]


def test_excluded_images_take_the_usable_ones_in_turn(tmp_path):
    world = World(tmp_path, Route())
    a = world.add_image('a', 160, 120, CLEAN)
    b = world.add_image('b', 160, 120, CLEAN)
    c = world.add_image('c', 160, 120, NUDE)
    d = world.add_image('d', 160, 120, NUDE)
    e = world.add_image('e', 160, 120, NUDE)
    chain = run_safety(world, [a, b, c, d, e])
    got = {name: choice(world, chain, item) for name, item in (('a', a), ('b', b), ('c', c), ('d', d), ('e', e))}
    assert got['c'].artifact == world.items['media-a'][0]
    assert got['d'].artifact == world.items['media-b'][0]
    assert got['e'].artifact == world.items['media-a'][0]
    assert {got[name].reason for name in 'cde'} == {'image_fallback'}
    assert got['a'].artifact == world.items['media-a'][0] and got['a'].reason != 'image_fallback'
    assert got['b'].artifact == world.items['media-b'][0] and got['b'].reason != 'image_fallback'


def test_without_a_usable_image_the_seed_of_the_same_rank_is_taken_else_nothing(tmp_path):
    world = World(tmp_path, Route())
    first = world.add_image('a', 160, 120, NUDE)
    second = world.add_image('b', 160, 120, NUDE)
    seeds(world, 2)
    chain = run_safety(world, [first, second])
    one, two = choice(world, chain, first), choice(world, chain, second)
    assert (one.reason, one.artifact) == ('seed_fallback', world.seeds[0].ref)
    assert (two.reason, two.artifact) == ('seed_fallback', world.seeds[1].ref)

    (tmp_path / 'bare').mkdir()
    bare = World(tmp_path / 'bare', Route())
    first = bare.add_image('a', 160, 120, NUDE)
    seeds(bare, 0)
    chain = run_safety(bare, [first])
    none = choice(bare, chain, first)
    assert none.artifact is None and none.reason == 'reject_category'


# --- Phần 4: cổng trước render -----------------------------------------------------------------------------------


def scene(sid, start, end, visuals):
    out = []
    for media_id, s, e, origin in visuals:
        visual = {'media_asset_id': media_id, 'start_ms': s, 'end_ms': e}
        if origin is not None:
            visual['origin'] = origin
        out.append(visual)
    return {'scene_id': sid, 'start_ms': start, 'end_ms': end, 'visuals': out}


def img(media_id, reason):
    return RenderImage(media_id, f'ver-{media_id}', reason)


def test_a_timeline_made_only_of_seed_images_fails_with_no_illustration_available():
    timeline = {'segments': [scene('sc-1', 0, 10000, [('m-1', 0, 10000, None)])]}
    with pytest.raises(ActivityInputError) as caught:
        require_illustration(timeline, {'m-1': img('m-1', 'seed_fallback')})
    assert caught.value.code == 'no_illustration_available' == NO_ILLUSTRATION_AVAILABLE
    assert isinstance(caught.value, ValueError)
    by_origin = {'segments': [scene('sc-1', 0, 10000, [('m-1', 0, 10000, 'seed')])]}
    with pytest.raises(ActivityInputError) as caught:
        require_illustration(by_origin, None)
    assert caught.value.code == NO_ILLUSTRATION_AVAILABLE


def test_the_seed_share_limit_is_15_percent_of_the_timeline():
    images = {'m-1': img('m-1', 'original'), 'm-2': img('m-2', 'seed_fallback')}
    exact = {'segments': [scene('sc-1', 0, 20000, [('m-1', 0, 17000, None), ('m-2', 17000, 20000, None)])]}
    require_illustration(exact, images)
    over = {'segments': [scene('sc-1', 0, 20000, [('m-1', 0, 16000, None), ('m-2', 16000, 20000, None)])]}
    with pytest.raises(ActivityInputError) as caught:
        require_illustration(over, images)
    assert caught.value.code == NO_ILLUSTRATION_AVAILABLE


def test_an_image_fallback_is_not_a_seed_and_no_plan_or_images_is_not_limited():
    timeline = {'segments': [scene('sc-1', 0, 10000, [('m-1', 0, 10000, None)])]}
    require_illustration(timeline, {'m-1': img('m-1', 'image_fallback')})
    require_illustration({}, None)
    require_illustration({'duration_ms': 1}, {})
    require_illustration(timeline, None)
