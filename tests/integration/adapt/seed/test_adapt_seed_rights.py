from __future__ import annotations

'''ADAPT-SEED-FIX3: kiểm khối rights của hooks.json và _require_rights của import_seed theo quyết định của user về ảnh bài (OI-ADAPT-10 ngày 25/10/2026, CLOSURE_NOTE CP7/RG-13 ngày 02/11/2026); không CSDL, mạng hay ffmpeg.

coveredIds: OI-ADAPT-10, OI-PW-03
'''

import importlib.util
import json
from pathlib import Path
import re
import sys
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[4]
PROD = ROOT / 'tools' / 'launcher' / 'prod'
HOOKS_PATH = PROD / 'hooks.json'
SEED_PATH = PROD / 'seed' / 'import_seed.py'
DECIDED_REFS = ['OI-ADAPT-10 25/10/2026', 'CLOSURE_NOTE CP7/RG-13 02/11/2026']


def load_tool():
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec = importlib.util.spec_from_file_location('adapt_seed_rights_import_seed', SEED_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


TOOL = load_tool()


def real_hooks():
    return json.loads(HOOKS_PATH.read_text(encoding='utf-8'))


def decided_rights():
    return {
        'seed_rights_status': 'SELF_GENERATED',
        'article_image_rights_status': 'UNVERIFIED',
        'article_images_in_sample_video': True,
        'article_image_decision_refs': list(DECIDED_REFS),
    }


def old_rights():
    return {
        'seed_rights_status': 'SELF_GENERATED',
        'article_image_rights_status': 'UNVERIFIED',
        'article_images_in_sample_video': False,
        'pending_user_checkpoint': 'OI-ADAPT-10',
    }


def hooks_with(changes, removed=()):
    rights = decided_rights()
    rights.update(changes)
    for key in removed:
        del rights[key]
    return {'rights': rights}


def test_hooks_json_records_the_article_image_decisions():
    rights = real_hooks()['rights']
    assert rights['seed_rights_status'] == 'SELF_GENERATED'
    assert rights['article_image_rights_status'] == 'UNVERIFIED'
    assert rights['article_images_in_sample_video'] is True
    assert 'pending_user_checkpoint' not in rights
    assert rights['article_image_decision_refs'] == DECIDED_REFS
    assert TOOL.ARTICLE_IMAGE_DECISION_REFS == ('OI-ADAPT-10', 'CLOSURE_NOTE CP7/RG-13')
    TOOL._require_rights(real_hooks())


def test_require_rights_accepts_the_decided_block_and_rejects_the_old_one():
    TOOL._require_rights({'rights': decided_rights()})
    with pytest.raises(TOOL.SeedError, match='allowed in the sample video'):
        TOOL._require_rights({'rights': old_rights()})
    with pytest.raises(TOOL.SeedError, match='pending_user_checkpoint must be removed'):
        TOOL._require_rights(hooks_with({'pending_user_checkpoint': 'OI-ADAPT-10'}))


def test_require_rights_rejects_a_missing_rights_block():
    for hooks in ({}, {'rights': None}, {'rights': []}, {'rights': 'UNVERIFIED'}):
        with pytest.raises(TOOL.SeedError, match='must declare a rights block'):
            TOOL._require_rights(hooks)


MALFORMED_CASES = [
    ('wrong_label', {'article_image_rights_status': 'VERIFIED'}, (), 'must keep the UNVERIFIED label'),
    ('missing_label', {}, ('article_image_rights_status',), 'must keep the UNVERIFIED label'),
    ('label_checked_before_flag', {'article_image_rights_status': 'VERIFIED', 'article_images_in_sample_video': False}, (), 'must keep the UNVERIFIED label'),
    ('flag_false', {'article_images_in_sample_video': False}, (), 'must be allowed in the sample video'),
    ('flag_missing', {}, ('article_images_in_sample_video',), 'must be allowed in the sample video'),
    ('flag_string', {'article_images_in_sample_video': 'true'}, (), 'must be allowed in the sample video'),
    ('flag_integer', {'article_images_in_sample_video': 1}, (), 'must be allowed in the sample video'),
    ('flag_checked_before_pending', {'article_images_in_sample_video': False, 'pending_user_checkpoint': 'OI-ADAPT-10'}, (), 'must be allowed in the sample video'),
    ('pending_text', {'pending_user_checkpoint': 'OI-ADAPT-10'}, (), 'pending_user_checkpoint must be removed'),
    ('pending_null', {'pending_user_checkpoint': None}, (), 'pending_user_checkpoint must be removed'),
    ('refs_missing', {}, ('article_image_decision_refs',), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
    ('refs_empty', {'article_image_decision_refs': []}, (), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
    ('refs_not_a_list', {'article_image_decision_refs': 'OI-ADAPT-10 CLOSURE_NOTE CP7/RG-13'}, (), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
    ('refs_non_string_item', {'article_image_decision_refs': DECIDED_REFS + [7]}, (), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
    ('refs_without_closure_note', {'article_image_decision_refs': DECIDED_REFS[:1]}, (), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
    ('refs_without_decision', {'article_image_decision_refs': DECIDED_REFS[1:]}, (), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
    ('refs_code_not_at_start', {'article_image_decision_refs': ['see OI-ADAPT-10', 'see CLOSURE_NOTE CP7/RG-13']}, (), 'must cite OI-ADAPT-10 and CLOSURE_NOTE CP7/RG-13'),
]


@pytest.mark.parametrize('name, changes, removed, message', MALFORMED_CASES, ids=[case[0] for case in MALFORMED_CASES])
def test_require_rights_rejects_a_malformed_block(name, changes, removed, message):
    TOOL._require_rights({'rights': decided_rights()})
    with pytest.raises(TOOL.SeedError, match=re.escape(message)):
        TOOL._require_rights(hooks_with(changes, removed))


def test_import_seed_checks_the_rights_before_it_touches_the_database(tmp_path):
    config = SimpleNamespace(mode='production')
    seed_dir = tmp_path / 'empty-seed'
    seed_dir.mkdir()
    with pytest.raises(TOOL.SeedError, match='missing seed media'):
        TOOL.import_seed(None, config, seed_dir)
    old = real_hooks()
    old['rights'] = old_rights()
    old_path = tmp_path / 'hooks-old.json'
    old_path.write_text(json.dumps(old), encoding='utf-8')
    with pytest.raises(TOOL.SeedError, match='allowed in the sample video'):
        TOOL.import_seed(None, config, seed_dir, hooks_path=old_path)
