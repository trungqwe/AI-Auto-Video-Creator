"""IMGGEN-LABEL: câu Includes AI-generated illustrations. trong caption khi kế hoạch dùng ảnh AI; chạy chuỗi D-14 trong bộ nhớ, không DB, không mạng.

coveredIds: OI-CP7-11-Q2
"""
from __future__ import annotations

import dataclasses
import re
from types import MappingProxyType, SimpleNamespace

import creative.application.pipeline as pipeline_module
from creative.domain.output_metadata import OutputMetadata
from tests.integration.creative.test_d14_creative_pipeline import SCRIPT_ARGS, Rig, _asset_inputs, _ctx, _prepare

SENTENCE = 'Includes AI-generated illustrations.'
MODEL_CAPTION = 'Ships are set to move again this week.'


class LowerSanitizer:
    def sanitize(self, value):
        return re.sub(r'[^a-z0-9]+', '_', value.lower()).strip('_')


def with_origin(inputs, origins):
    media = [dataclasses.replace(c, provenance={**c.provenance, 'origin': origins[c.media_asset_id]}) if c.media_asset_id in origins else c for c in inputs['media_candidates']]
    return {**inputs, 'media_candidates': media}


def metadata_for(origins):
    rig = Rig()
    pipeline = rig.pipeline
    _prepare(rig)
    pipeline.generate_script(context=_ctx(4), idempotency_key='k-script', **SCRIPT_ARGS)
    selection = pipeline.select_creative_assets(context=_ctx(5), idempotency_key='k-select', snapshot_id='snap-1', script_version_id='script-1', set_id='set-1', angle_id='angle-a', **with_origin(_asset_inputs(), origins))
    pipeline.build_production_plan(context=_ctx(6), idempotency_key='k-plan', snapshot_id='snap-1', script_version_id='script-1', selection=selection.output, production_plan_id='plan-1', preset_revision_ref='preset-v1')
    result = pipeline.generate_output_metadata(context=_ctx(8), idempotency_key='k-meta', snapshot_id='snap-1', source_job_ref='job-1', source_output_refs=('plan-1',), metadata_revision=1, sanitizer=LowerSanitizer())
    return rig, result.output


def test_a_plan_with_an_ai_generated_image_gets_the_sentence_after_the_model_caption():
    for origins in ({'m-1': 'ai_generated'}, {'m-2': 'ai_generated'}):
        rig, metadata = metadata_for(origins)
        assert metadata.caption == MODEL_CAPTION + ' ' + SENTENCE
        assert metadata.title == 'Port Strike Ends After Three Days'
        assert metadata.hashtags == ('#Port', '#Strike', '#Shipping')
        assert rig.uow.output_metadata.latest('job-1').record.caption == metadata.caption
        assert pipeline_module._uses_ai_illustration([rig.uow.plans.latest('plan-1').record]) is True
        assert (pipeline_module.AI_ILLUSTRATION_NOTE, pipeline_module.ORIGIN_AI_GENERATED) == (SENTENCE, 'ai_generated')


def test_a_plan_without_an_ai_generated_image_keeps_the_model_caption():
    for origins in ({}, {'m-1': 'article', 'm-2': 'article'}, {'m-1': 'seed', 'm-2': 'seed', 'm-3': 'seed'}):
        rig, metadata = metadata_for(origins)
        assert metadata.caption == MODEL_CAPTION
        assert 'illustrations' not in metadata.filename_safe.caption
        assert pipeline_module._uses_ai_illustration([rig.uow.plans.latest('plan-1').record]) is False


def test_the_filename_safe_caption_carries_the_sentence_too():
    _, metadata = metadata_for({'m-1': 'ai_generated'})
    assert metadata.filename_safe.caption == 'ships_are_set_to_move_again_this_week_includes_ai_generated_illustrations'
    assert metadata.filename_safe.title == 'port_strike_ends_after_three_days'
    assert metadata.filename_safe.hashtags == ('port', 'strike', 'shipping')


def metadata(caption):
    return OutputMetadata(title='T', caption=caption, hashtags=('#a', '#b', '#c'), language='en', source_job_ref='job-1', source_output_refs=('plan-1',), metadata_revision=1)


def plan_of(*scenes):
    return SimpleNamespace(timeline={'segments': [{'visuals': list(visuals)} for visuals in scenes]})


def test_the_sentence_is_added_once_and_only_to_the_caption():
    base = metadata('Ships move.   ')
    once = pipeline_module._with_illustration_note(base)
    assert once.caption == 'Ships move. ' + SENTENCE
    assert once.caption.count(SENTENCE) == 1
    assert dataclasses.replace(once, caption=base.caption) == base
    assert once.filename_safe is None
    assert pipeline_module._with_illustration_note(once).caption == once.caption
    already = metadata('Ships move. ' + SENTENCE)
    middle = metadata(SENTENCE + ' Ships move.')
    for x in (already, middle):
        assert pipeline_module._with_illustration_note(x).caption == x.caption


def test_only_a_visual_with_the_ai_generated_origin_counts():
    uses = pipeline_module._uses_ai_illustration
    assert uses([plan_of([{'origin': 'ai_generated'}])]) is True
    assert uses([plan_of([{'origin': 'seed'}, {'origin': 'ai_generated'}])]) is True
    assert uses([plan_of([{}], [{'origin': 'ai_generated'}])]) is True
    assert uses([plan_of([{'origin': 'seed'}]), plan_of([{'origin': 'ai_generated'}])]) is True
    assert uses([SimpleNamespace(timeline=MappingProxyType({'segments': ({'visuals': (MappingProxyType({'origin': 'ai_generated'}),)},)}))]) is True
    assert uses([]) is False
    for plan in (
        plan_of([{'origin': 'seed'}]),
        plan_of([{}]),
        plan_of([{'origin': 'AI_GENERATED'}]),
        plan_of([{'artifact_version_ref': 'ai_illustration', 'media_asset_id': 'ai_generated'}]),
        plan_of(),
        SimpleNamespace(timeline={}),
        SimpleNamespace(timeline={'segments': 'x'}),
        SimpleNamespace(timeline={'segments': [{'visuals': 'x'}]}),
    ):
        assert uses([plan]) is False
