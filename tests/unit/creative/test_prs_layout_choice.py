"""PRS-LAYOUT-PLAN: AI chọn một trong năm bố cục trong kế hoạch sản xuất (FR-PRS-002..005), có tập đủ điều kiện, trần 40% mỗi lô,
validator và dự phòng xác định có ghi lý do; preset của kế hoạch là preset ghép với bố cục đã chọn.

coveredIds: FR-PRS-002, FR-PRS-003, FR-PRS-004, FR-PRS-005
"""
from __future__ import annotations

import dataclasses
import hashlib
import inspect

import pytest

from creative.application import pipeline as pipeline_module
from creative.application.prompts import DEFAULT_PROMPTS, PREVIOUS_DEFAULT_PROMPT_HASHES
from creative.application.roles import ROLE_PLAN
from creative.domain import layout_choice as lc
from creative.domain.production_plan import INPUT_NOT_READY, PlanRejected, ProductionPlan, build_production_plan
from creative.persistence.codec import decode_record, encode_record
from tests.unit.creative.test_d10_production_plan import _raw, _script, _selection

PRESETS = {'HERO_STRIP': 'bold-yellow', 'MOSAIC_GRID': 'news-red', 'FULL_BLEED_INSET': 'soft-shadow', 'SPLIT_STACK': 'clean-white', 'DATA_CARD': 'neon-cyan'}
HEAD_PLAN_PROMPT_SHA256 = 'b077e48b48d00e8f1cc8edab7904d12f976c37c5008e098cd8c0aa4c8a6cdd5b'


def selection_with(origins):
    base = _selection()
    first = base.assignments[0]
    items = tuple(dataclasses.replace(first, order=i, scene_id=f'sc-{i + 1}', media_asset_id=f'm-{i + 1}', origin=o) for i, o in enumerate(origins))
    return dataclasses.replace(base, assignments=items)


def test_eligible_layouts_follow_the_pictures_and_the_numbers():
    words = _script('Prices rose sharply')
    figures = _script('Prices rose 50 percent')
    cases = [
        (['article', 'article'], words, ('HERO_STRIP', 'SPLIT_STACK')),
        (['article'] * 4, figures, ('HERO_STRIP', 'MOSAIC_GRID', 'SPLIT_STACK', 'DATA_CARD')),
        (['article', 'ai_generated'], words, ('HERO_STRIP', 'FULL_BLEED_INSET', 'SPLIT_STACK')),
        (['article'], figures, ('FULL_BLEED_INSET', 'DATA_CARD')),
        (['seed', 'seed'], words, ('FULL_BLEED_INSET',)),
        ([None, None, None], words, ('HERO_STRIP', 'MOSAIC_GRID', 'SPLIT_STACK')),
    ]
    for origins, script, wanted in cases:
        assert lc.eligible_layouts(lc.layout_features(selection_with(origins), script)) == wanted, origins
    assert lc.layout_features(selection_with(['article', 'article']), _script('Two million people')).has_number


def test_batch_cap_keeps_every_layout_at_or_under_forty_percent():
    everything = lc.LAYOUT_KEYS
    assert lc.capped_layouts(everything, {'HERO_STRIP': 4}, 10) == ('MOSAIC_GRID', 'FULL_BLEED_INSET', 'SPLIT_STACK', 'DATA_CARD')
    assert lc.capped_layouts(('HERO_STRIP', 'DATA_CARD'), {'HERO_STRIP': 4, 'DATA_CARD': 4}, 10) == ('HERO_STRIP',)
    assert lc.capped_layouts(('DATA_CARD', 'HERO_STRIP'), {'HERO_STRIP': 5, 'DATA_CARD': 4}, 10) == ('DATA_CARD',)
    assert lc.capped_layouts(everything, {'HERO_STRIP': 9}, 0) == everything
    used = {}
    for _ in range(10):
        options = lc.capped_layouts(everything, used, 10)
        choice = lc.choose_layout({'key': 'HERO_STRIP', 'reason': 'default'}, options=options, presets=PRESETS, segment_ids=['s1'])
        used[choice.layout_key] = used.get(choice.layout_key, 0) + 1
    assert max(used.values()) <= 4 and sum(used.values()) == 10


def test_choice_is_validated_and_falls_back_with_a_reason():
    options = ('HERO_STRIP', 'FULL_BLEED_INSET', 'SPLIT_STACK')
    ids = ['s1', 's2']

    def pick(raw, opts=options):
        return lc.choose_layout(raw, options=opts, presets=PRESETS, segment_ids=ids)

    assert pick(None).fallback_reason == 'layout_missing' and pick(None).layout_key == 'HERO_STRIP'
    assert pick('SPLIT_STACK').fallback_reason == 'layout_invalid'
    assert pick({'key': 'CAROUSEL'}).fallback_reason == 'layout_unknown'
    assert pick({'key': 'MOSAIC_GRID'}).fallback_reason == 'layout_not_eligible'
    assert pick({'key': 'SPLIT_STACK', 'contrast_pair': ['s1', 's1']}).fallback_reason == 'contrast_pair_invalid'
    assert pick({'key': 'SPLIT_STACK', 'contrast_pair': ['s1', 's9']}).layout_key == 'HERO_STRIP'
    good = pick({'key': 'SPLIT_STACK', 'reason': ' inside  versus outside ', 'contrast_pair': ['s1', 's2'], 'title': 'Hackers heat freezers to 50C'})
    assert (good.layout_key, good.preset_key, good.fallback_reason, good.contrast_pair) == ('SPLIT_STACK', 'clean-white', None, ('s1', 's2'))
    assert good.reason == 'inside versus outside' and good.title == 'Hackers heat freezers to 50C'
    assert pick({'key': 'HERO_STRIP', 'title': 'x' * 49}).title is None
    assert pick({'key': 'MOSAIC_GRID'}, ('FULL_BLEED_INSET', 'DATA_CARD')).layout_key == 'FULL_BLEED_INSET'
    assert [item['key'] for item in lc.layout_prompt_data(('DATA_CARD', 'HERO_STRIP'))] == ['HERO_STRIP', 'DATA_CARD']


def plan(raw, layout_options=None, layout_presets=None):
    """What CreativePipeline.build_production_plan does after the model call: choose_layout on raw['layout'], then the D-10 builder."""
    preset, choice = 'bold-yellow', None
    if layout_presets is not None:
        picked = lc.choose_layout(raw.get('layout'), options=layout_options, presets=layout_presets, segment_ids=['s1'])
        preset, choice = picked.preset_key, picked.to_payload()
    return build_production_plan(raw, production_plan_id='pp-1', script=_script(), selection=_selection(), preset_revision_ref=preset, layout_choice=choice)


def test_plan_takes_the_preset_of_the_chosen_layout_and_records_the_choice():
    raw = _raw()
    raw['layout'] = {'key': 'SPLIT_STACK', 'reason': 'two sides', 'contrast_pair': ['s1', 's1']}
    chosen = plan(raw, layout_options=('HERO_STRIP', 'SPLIT_STACK'), layout_presets=PRESETS)
    assert chosen.preset_revision_ref == 'bold-yellow' and chosen.layout_choice['fallback_reason'] == 'contrast_pair_invalid'
    raw['layout'] = {'key': 'DATA_CARD', 'reason': 'one figure leads'}
    chosen = plan(raw, layout_options=('HERO_STRIP', 'DATA_CARD'), layout_presets=PRESETS)
    assert chosen.preset_revision_ref == 'neon-cyan'
    assert chosen.to_payload()['layout_choice'] == {'layout_key': 'DATA_CARD', 'preset_key': 'neon-cyan', 'reason': 'one figure leads', 'fallback_reason': None, 'contrast_pair': None, 'title': None}
    plain = plan(_raw())
    assert plain.layout_choice is None and 'layout_choice' not in plain.to_payload()
    assert plan(raw).plan_fingerprint == plain.plan_fingerprint
    assert chosen.plan_fingerprint != plain.plan_fingerprint
    for bad in ({'layout_key': 'DATA_CARD', 'preset_key': 'news-red'}, {'layout_key': 'DATA_CARD'}, 'DATA_CARD'):
        with pytest.raises(PlanRejected) as caught:
            build_production_plan(_raw(), production_plan_id='pp-1', script=_script(), selection=_selection(), preset_revision_ref='neon-cyan', layout_choice=bad)
        assert (caught.value.code, caught.value.reason) == (INPUT_NOT_READY, 'invalid_layout_choice')
    assert lc.valid_presets(PRESETS)
    for bad in ({'HERO_STRIP': 'bold-yellow'}, {**PRESETS, 'DATA_CARD': ''}, ['bold-yellow'], {**PRESETS, 'EXTRA': 'x'}):
        assert not lc.valid_presets(bad)


def test_plans_stored_before_the_layout_choice_still_decode():
    raw = _raw()
    raw['layout'] = {'key': 'HERO_STRIP', 'reason': 'default'}
    chosen = plan(raw, layout_options=('HERO_STRIP',), layout_presets=PRESETS)
    stored = encode_record(chosen)
    assert decode_record(ProductionPlan, stored).layout_choice['layout_key'] == 'HERO_STRIP'
    legacy = encode_record(plan(_raw()))
    del legacy['layout_choice']
    assert decode_record(ProductionPlan, legacy).layout_choice is None


def test_plan_prompt_offers_the_layouts_and_the_old_prompt_is_upgraded():
    text = DEFAULT_PROMPTS[ROLE_PLAN]
    assert 'layout_options' in text and 'contrast_pair' in text and '48 characters' in text
    assert HEAD_PLAN_PROMPT_SHA256 in PREVIOUS_DEFAULT_PROMPT_HASHES[ROLE_PLAN]
    assert hashlib.sha256(text.encode('utf-8')).hexdigest() not in PREVIOUS_DEFAULT_PROMPT_HASHES[ROLE_PLAN]
    params = inspect.signature(pipeline_module.CreativePipeline.build_production_plan).parameters
    assert params['layout_options'].default is None and params['layout_presets'].default is None
