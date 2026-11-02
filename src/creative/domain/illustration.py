"""IMGGEN-ROUTE: pure rules for the illustration role: shot plan with one style card, caption message and caption check by code; no I/O, no model call, no clock."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

MIN_CAPTION_WORDS = 80
MAX_CAPTION_WORDS = 350
BANNED_WORDS = ('logo', 'brand', 'trademark', 'watermark', 'lettering', 'inscription', 'signage', 'headline', 'caption', 'text')
SHOT_KINDS = ('wide', 'medium', 'close_detail', 'object', 'aftermath')
STYLE_CARD_FIELDS = ('palette', 'light', 'contrast', 'grain', 'lens', 'depth_of_field', 'weather', 'mood')
TARGET_CANVAS = 'TARGET CANVAS: 9:16'
MIN_SHOTS = 1
MAX_SHOTS = 5
MAX_LINE_CHARS = 400
CAPTION_RULES = (
    'Write one plain English paragraph of 100 to 250 words that describes a single photograph. '
    'Describe only what a camera records: subjects, materials, positions, scale, colors, light and weather. '
    'Keep every surface plain and unmarked, so each object shows only its natural shape and color. '
    'Refer to people and places by neutral descriptions such as the man in the gray coat or the harbor at dusk. '
    'Follow the style card for palette, light, contrast, grain, lens, depth of field, weather and mood. '
    'Fill the vertical 9:16 frame with a clear foreground, middle ground and background.'
)


class IllustrationPlanError(ValueError):
    def __init__(self, code: str, field: str = '') -> None:
        self.code = code
        self.field = field
        super().__init__(f'{code}: {field}' if field else code)


@dataclass(frozen=True, slots=True)
class StyleCard:
    palette: str
    light: str
    contrast: str
    grain: str
    lens: str
    depth_of_field: str
    weather: str
    mood: str


@dataclass(frozen=True, slots=True)
class ShotRequest:
    shot: str
    scene_intent: str
    description: str


@dataclass(frozen=True, slots=True)
class IllustrationPlan:
    style_card: StyleCard
    requests: tuple[ShotRequest, ...]


@dataclass(frozen=True, slots=True)
class CaptionProblem:
    code: str
    detail: str


def _line(value: object, field: str) -> str:
    if value is None:
        raise IllustrationPlanError('missing', field)
    if not isinstance(value, str) or not value.strip():
        raise IllustrationPlanError('invalid_text', field)
    line = value.strip()
    if '\n' in line or '\r' in line:
        raise IllustrationPlanError('multiline', field)
    if len(line) > MAX_LINE_CHARS:
        raise IllustrationPlanError('too_long', field)
    return line


def parse_plan(payload: object, count: int) -> IllustrationPlan:
    if isinstance(count, bool) or not isinstance(count, int) or not MIN_SHOTS <= count <= MAX_SHOTS:
        raise ValueError('count must be an integer from 1 to 5')
    if not isinstance(payload, Mapping):
        raise IllustrationPlanError('plan_not_object', 'payload')
    card = payload.get('style_card')
    if not isinstance(card, Mapping):
        raise IllustrationPlanError('missing' if card is None else 'invalid_object', 'style_card')
    values = {name: _line(card.get(name), 'style_card.' + name) for name in STYLE_CARD_FIELDS}
    items = payload.get('requests')
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise IllustrationPlanError('missing' if items is None else 'invalid_list', 'requests')
    if len(items) != count:
        raise IllustrationPlanError('request_count', 'requests')
    requests = []
    seen = set()
    for index, item in enumerate(items):
        where = f'requests[{index}]'
        if not isinstance(item, Mapping):
            raise IllustrationPlanError('invalid_object', where)
        shot = _line(item.get('shot'), where + '.shot').lower().replace(' ', '_').replace('-', '_')
        if shot not in SHOT_KINDS:
            raise IllustrationPlanError('unknown_shot', where + '.shot')
        if shot in seen:
            raise IllustrationPlanError('duplicate_shot', where + '.shot')
        seen.add(shot)
        requests.append(ShotRequest(shot, _line(item.get('scene_intent'), where + '.scene_intent'), _line(item.get('description'), where + '.description')))
    return IllustrationPlan(StyleCard(**values), tuple(requests))


def caption_message(request: ShotRequest, style_card: StyleCard, retry_reason: str | None = None) -> str:
    if retry_reason is not None and not isinstance(retry_reason, str):
        raise ValueError('retry_reason must be a string or None')
    lines = [
        TARGET_CANVAS,
        f'SHOT: {request.shot}',
        f'SCENE INTENT: {request.scene_intent}',
        f'DESCRIPTION: {request.description}',
        'STYLE CARD:',
        *(f'- {name}: {getattr(style_card, name)}' for name in STYLE_CARD_FIELDS),
        CAPTION_RULES,
    ]
    if retry_reason is not None and retry_reason.strip():
        lines.append('RETRY REASON: ' + ' '.join(retry_reason.split()))
    return '\n'.join(lines)


_QUOTES = '"' + chr(0x201c) + chr(0x201d) + chr(0x201e) + chr(0xab) + chr(0xbb)
_BANNED = re.compile(r'\b(' + '|'.join(BANNED_WORDS) + r')(?:s|es|ed|ing)?\b', re.IGNORECASE)
_TOKEN = re.compile(r'[^\W\d_]+')
_MAX_NON_ASCII_RATIO = 0.02
_MIN_FUNCTION_RATIO = 0.20
_SHORT_NAME_CHARS = 3
_FUNCTION_WORDS = frozenset(
    'a an the and or but of in on at to with by for from as is are was were be it its this that these those '
    'his her their he she they there into over under near behind above through across along between while'.split()
)


def _looks_english(caption: str) -> bool:
    tokens = _TOKEN.findall(caption.lower())
    if not tokens:
        return True
    letters = ''.join(tokens)
    if sum(1 for ch in letters if ord(ch) > 127) / len(letters) > _MAX_NON_ASCII_RATIO:
        return False
    return sum(1 for token in tokens if token in _FUNCTION_WORDS) / len(tokens) >= _MIN_FUNCTION_RATIO


def _entity_pattern(name: str) -> re.Pattern[str]:
    flags = 0 if len(name) <= _SHORT_NAME_CHARS else re.IGNORECASE
    return re.compile(r'(?<!\w)' + re.escape(name) + r'(?!\w)', flags)


def check_caption(caption: str, entity_names: Sequence[str] = ()) -> tuple[CaptionProblem, ...]:
    if not isinstance(caption, str):
        raise ValueError('caption must be a string')
    if isinstance(entity_names, (str, bytes, bytearray)) or not isinstance(entity_names, Sequence):
        raise ValueError('entity_names must be a sequence of strings')
    if not all(isinstance(name, str) for name in entity_names):
        raise ValueError('entity_names must be a sequence of strings')
    problems = []
    words = len(caption.split())
    if words < MIN_CAPTION_WORDS:
        problems.append(CaptionProblem('too_short', str(words)))
    elif words > MAX_CAPTION_WORDS:
        problems.append(CaptionProblem('too_long', str(words)))
    if not _looks_english(caption):
        problems.append(CaptionProblem('not_english', 'non-ASCII letters or too few English function words'))
    if any(ch in _QUOTES for ch in caption):
        problems.append(CaptionProblem('double_quote', 'double quotation marks'))
    found = {match.group(1).lower() for match in _BANNED.finditer(caption)}
    problems.extend(CaptionProblem('banned_word', word) for word in BANNED_WORDS if word in found)
    seen = []
    for name in entity_names:
        name = name.strip()
        if name and name not in seen:
            seen.append(name)
            if _entity_pattern(name).search(caption):
                problems.append(CaptionProblem('entity_name', name))
    return tuple(problems)


def _plain(detail: str) -> str:
    return ''.join(ch for ch in detail if ch not in _QUOTES)


def explain(problems: Sequence[CaptionProblem]) -> str:
    sentences = []
    for problem in problems:
        detail = _plain(problem.detail)
        if problem.code == 'too_short':
            sentences.append(f'Write at least {MIN_CAPTION_WORDS} words; the last attempt had {detail}.')
        elif problem.code == 'too_long':
            sentences.append(f'Write at most {MAX_CAPTION_WORDS} words; the last attempt had {detail}.')
        elif problem.code == 'not_english':
            sentences.append('Write the paragraph in plain English using ordinary English words and letters.')
        elif problem.code == 'double_quote':
            sentences.append('Replace every double quotation mark with plain narrative wording.')
        elif problem.code == 'banned_word':
            sentences.append(f'Replace the word {detail} with a plain visual description of the object itself.')
        elif problem.code == 'entity_name':
            sentences.append(f'Replace the name {detail} with a neutral description such as the man in the gray coat.')
        else:
            sentences.append(f'Fix the problem {_plain(problem.code)}.')
    return ' '.join(sentences)


__all__ = [
    'BANNED_WORDS', 'CAPTION_RULES', 'MAX_CAPTION_WORDS', 'MIN_CAPTION_WORDS', 'SHOT_KINDS', 'STYLE_CARD_FIELDS', 'TARGET_CANVAS',
    'CaptionProblem', 'IllustrationPlan', 'IllustrationPlanError', 'ShotRequest', 'StyleCard',
    'caption_message', 'check_caption', 'explain', 'parse_plan',
]
