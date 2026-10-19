"""I-11: cấp phát folder và tên tệp output (CT-STO-011, D8-I-07, D8-I-08)."""
from __future__ import annotations

import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date

HASH_REPLACEMENT = '_hash_'
MIN_HASHTAGS = 3
MAX_HASHTAGS = 4

_FORBIDDEN = frozenset('<>:"/' + chr(92) + '|?*')
_RESERVED = frozenset(
    {'CON', 'PRN', 'AUX', 'NUL'}
    | {f'{prefix}{n}' for prefix in ('COM', 'LPT') for n in range(1, 10)}
)
_ZWJ = chr(0x200D)
_FALLBACK_STEM = '_'


def _width(text: str) -> int:
    """Độ dài theo đơn vị UTF-16, đúng giới hạn tên tệp của NTFS."""
    return sum(2 if ord(char) > 0xFFFF else 1 for char in text)


def _is_joiner(char: str) -> bool:
    return (
        unicodedata.category(char).startswith('M')
        or char == _ZWJ
        or 0x1F3FB <= ord(char) <= 0x1F3FF
    )


def _truncate(text: str, limit: int) -> str:
    used = 0
    cut = 0
    for index, char in enumerate(text):
        used += _width(char)
        if used > limit:
            break
        cut = index + 1
    else:
        return text
    while cut > 0 and (_is_joiner(text[cut]) or text[cut - 1] == _ZWJ):
        cut -= 1
    return text[:cut]


def _strip_tail(text: str) -> str:
    return text.rstrip(' .')


def _clean(text: str, supports_hash: bool) -> str:
    kept = (
        char
        for char in unicodedata.normalize('NFC', text)
        if unicodedata.category(char) != 'Cc'
    )
    cleaned = ''.join('_' if char in _FORBIDDEN else char for char in kept)
    return cleaned if supports_hash else cleaned.replace('#', HASH_REPLACEMENT)


def _guard_reserved(stem: str) -> str:
    head, dot, tail = stem.partition('.')
    if head.rstrip(' ').upper() in _RESERVED:
        return f'{head}_{dot}{tail}'
    return stem


def _fit_stem(stem: str, budget: int) -> str:
    for limit in range(budget, 0, -1):
        candidate = _guard_reserved(_strip_tail(_truncate(stem, limit)))
        if candidate and _width(candidate) <= budget:
            return candidate
    raise ValueError('max_filename_length quá nhỏ cho tên, hậu tố trùng tên và phần mở rộng')


def _collision_key(name: str) -> str:
    return unicodedata.normalize('NFC', name).casefold()


@dataclass(frozen=True)
class OutputName:
    sanitized_filename: str
    collision_sequence: int
    display_title: str
    display_hashtags: tuple[str, ...]
    hash_mapping: tuple[tuple[str, str], ...]


def allocate_output_folder(
    session_date: date,
    completed_sessions_before_today: int,
    session_has_completed_video: bool,
) -> str | None:
    if completed_sessions_before_today < 0:
        raise ValueError('completed_sessions_before_today không được âm')
    if not session_has_completed_video:
        return None
    folder = f'{session_date.year % 100:02d}-{session_date.month:02d}-{session_date.day:02d}'
    if completed_sessions_before_today == 0:
        return folder
    return f'{folder} ({completed_sessions_before_today})'


def allocate_output_filename(
    title: str,
    hashtags: Sequence[str],
    extension: str,
    existing_names: Iterable[str],
    supports_hash: bool,
    max_filename_length: int,
) -> OutputName:
    if isinstance(hashtags, str):
        raise ValueError('hashtags phải là dãy chuỗi, không phải một chuỗi')
    tags = tuple(hashtags)
    if not MIN_HASHTAGS <= len(tags) <= MAX_HASHTAGS:
        raise ValueError(f'cần {MIN_HASHTAGS}-{MAX_HASHTAGS} hashtag, nhận {len(tags)}')
    if max_filename_length < 1:
        raise ValueError('max_filename_length phải >= 1')
    head = _guard_reserved(_clean(title, supports_hash))
    parts = [head, *(_clean(tag, supports_hash) for tag in tags)]
    stem = _strip_tail(' '.join(parts)) or _FALLBACK_STEM
    extension_text = _strip_tail(_clean(extension, supports_hash).lstrip('.'))
    extension_part = f'.{extension_text}' if extension_text else ''
    taken = {_collision_key(name) for name in existing_names}
    sequence = 1
    while True:
        collision = '' if sequence == 1 else f' ({sequence})'
        budget = max_filename_length - _width(collision) - _width(extension_part)
        filename = _fit_stem(stem, budget) + collision + extension_part
        if _collision_key(filename) not in taken:
            break
        sequence += 1
    used_hash = not supports_hash and any('#' in part for part in (title, *tags, extension))
    return OutputName(
        sanitized_filename=filename,
        collision_sequence=sequence,
        display_title=title,
        display_hashtags=tags,
        hash_mapping=((HASH_REPLACEMENT, '#'),) if used_hash else (),
    )


__all__ = [
    'HASH_REPLACEMENT',
    'OutputName',
    'allocate_output_filename',
    'allocate_output_folder',
]
