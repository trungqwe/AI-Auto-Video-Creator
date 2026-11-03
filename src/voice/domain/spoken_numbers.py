"""English spoken form of the numbers in a narration text, for the TTS engine only (TTS-NUMBERS).

Kokoro (kokoro-onnx 0.4.9) phonemizes with espeak-ng through phonemizer with preserve_punctuation=True, which splits the text
at every ',' '.' ':' before espeak sees it: '72,000' is read 'seventy-two, zero zero zero', '1.5' 'one. five', '$4.99'
'dollar four. ninety-nine', '1990s' 'nineteen hundred ninety z', '2020-2024' '... dash ...'. speakable_english rewrites the
numbers of a text as English words before the text goes to the engine; the script text itself (subtitles, aligner, coverage)
keeps the digits the script wrote. Pure: stdlib only, no I/O. A text without an ASCII digit is returned unchanged.
"""
from __future__ import annotations

import re

SPOKEN_NUMBERS_REVISION = 'spoken-en-1'
MAX_SPOKEN_VALUE = 10 ** 15 - 1

_ONES = ('zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen')
_TENS = ('', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty', 'seventy', 'eighty', 'ninety')
_SCALES = ((10 ** 12, 'trillion'), (10 ** 9, 'billion'), (10 ** 6, 'million'), (10 ** 3, 'thousand'))
_ORDINAL_WORDS = {'one': 'first', 'two': 'second', 'three': 'third', 'five': 'fifth', 'eight': 'eighth', 'nine': 'ninth', 'twelve': 'twelfth'}
_SCALE_SUFFIXES = {'k': 'thousand', 'K': 'thousand', 'm': 'million', 'M': 'million', 'mn': 'million', 'b': 'billion', 'B': 'billion', 'bn': 'billion', 'tn': 'trillion',
                   'thousand': 'thousand', 'million': 'million', 'billion': 'billion', 'trillion': 'trillion'}
# symbol: (singular, plural, minor singular, minor plural); a currency without a minor unit reads its decimals with 'point'.
_CURRENCIES = {'$': ('dollar', 'dollars', 'cent', 'cents'), '€': ('euro', 'euros', 'cent', 'cents'), '£': ('pound', 'pounds', 'penny', 'pence'), '¥': ('yen', 'yen', None, None)}
_UNITS = {
    'km/h': ('kilometer per hour', 'kilometers per hour'), 'kWh': ('kilowatt hour', 'kilowatt hours'), 'km': ('kilometer', 'kilometers'),
    'kg': ('kilogram', 'kilograms'), 'cm': ('centimeter', 'centimeters'), 'mm': ('millimeter', 'millimeters'), 'mg': ('milligram', 'milligrams'),
    'ml': ('milliliter', 'milliliters'), 'mph': ('mile per hour', 'miles per hour'), 'kph': ('kilometer per hour', 'kilometers per hour'),
    'GB': ('gigabyte', 'gigabytes'), 'MB': ('megabyte', 'megabytes'), 'TB': ('terabyte', 'terabytes'), 'kW': ('kilowatt', 'kilowatts'),
    'MW': ('megawatt', 'megawatts'), 'GW': ('gigawatt', 'gigawatts'), 'ft': ('foot', 'feet'), 'lbs': ('pound', 'pounds'), 'lb': ('pound', 'pounds'),
    'mi': ('mile', 'miles'),
}
_DEGREE_SCALES = {'C': 'Celsius', 'F': 'Fahrenheit'}

_NUM = r'(?:[0-9]{1,3}(?:,[0-9]{3})+|[0-9]+)(?:\.[0-9]+)?'
_END = r'(?![A-Za-z0-9_])'
_FREE = r'(?<![A-Za-z0-9_.,/])'
_SPOKEN_RE = re.compile(
    rf"""
    (?P<cur>[$€£¥])\s?(?P<cnum>{_NUM})(?:(?P<cabbr>k|K|mn|m|M|bn|b|B|tn)|\s(?P<cword>thousand|million|billion|trillion)){{0,1}}{_END}
  | {_FREE}(?P<hh>[0-9]{{1,2}}):(?P<mm>[0-5][0-9])(?![0-9:])
  | {_FREE}(?P<ra>{_NUM})(?:\s?[–—]\s?|-)(?P<rb>{_NUM})(?P<rpct>\s?%)?(?!-[0-9]){_END}
  | {_FREE}(?P<dneg>[-−])?(?P<dnum>{_NUM})\s?°\s?(?P<dscale>[CF])?{_END}
  | {_FREE}(?P<unum>{_NUM})\s?(?P<unit>km/h|kWh|km|kg|cm|mm|mg|ml|mph|kph|GB|MB|TB|kW|MW|GW|ft|lbs|lb|mi)(?![A-Za-z0-9_/])
  | {_FREE}(?P<pneg>[-−])?(?P<pnum>{_NUM})\s?%
  | {_FREE}(?P<onum>[0-9]{{1,3}}(?:,[0-9]{{3}})+|[0-9]+)(?P<osuf>st|nd|rd|th){_END}
  | {_FREE}(?P<dec4>1[1-9][0-9]0|20[0-9]0)s{_END}
  | (?<![A-Za-z0-9_])['’]?(?P<dec2>[1-9]0)s{_END}
  | (?<![A-Za-z0-9_)\]])(?P<nneg>[-−])(?P<nnum>{_NUM})(?![A-Za-z0-9_/]|[.,][0-9])
  | {_FREE}(?P<num>{_NUM})(?![A-Za-z0-9_/]|[.,][0-9])
    """,
    re.VERBOSE,
)


def _below_thousand(value: int) -> list[str]:
    words: list[str] = []
    if value >= 100:
        words += [_ONES[value // 100], 'hundred']
        value %= 100
    if value >= 20:
        words.append(_TENS[value // 10] + (f'-{_ONES[value % 10]}' if value % 10 else ''))
    elif value or not words:
        words.append(_ONES[value])
    return words


def _digits(text: str) -> str:
    return ' '.join(_ONES[int(ch)] for ch in text)


def cardinal_words(value: int) -> str:
    """English cardinal of 0 <= value <= MAX_SPOKEN_VALUE: 72000 = 'seventy-two thousand', 1500 = 'one thousand five hundred' (no 'and')."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_SPOKEN_VALUE:
        raise ValueError('value must be an int in [0, MAX_SPOKEN_VALUE]')
    if value == 0:
        return 'zero'
    words: list[str] = []
    for size, name in _SCALES:
        if value >= size:
            words += [*_below_thousand(value // size), name]
            value %= size
    if value:
        words += _below_thousand(value)
    return ' '.join(words)


def ordinal_words(value: int) -> str:
    """English ordinal: 1 = 'first', 21 = 'twenty-first', 100 = 'one hundredth', 1000 = 'one thousandth'."""
    head, _, last = cardinal_words(value).rpartition(' ')
    stem, dash, tail = last.rpartition('-')
    if tail in _ORDINAL_WORDS:
        tail = _ORDINAL_WORDS[tail]
    elif tail.endswith('y'):
        tail = tail[:-1] + 'ieth'
    else:
        tail += 'th'
    return f'{head} {stem}{dash}{tail}'.strip() if head else f'{stem}{dash}{tail}'


def year_words(value: int) -> str:
    """Year reading of 1100..1999 and 2010..2099 (1999 = 'nineteen ninety-nine', 1905 = 'nineteen oh five', 1900 = 'nineteen hundred', 2024 = 'twenty twenty-four'); other values read as cardinals."""
    high, low = divmod(value, 100)
    if not (1100 <= value <= 1999 or 2010 <= value <= 2099):
        return cardinal_words(value)
    if low == 0:
        return f'{cardinal_words(high)} hundred'
    if low < 10:
        return f'{cardinal_words(high)} oh {cardinal_words(low)}'
    return f'{cardinal_words(high)} {cardinal_words(low)}'


def _plural(words: str) -> str:
    """'nineteen ninety' -> 'nineteen nineties', 'nineteen hundred' -> 'nineteen hundreds'."""
    return words[:-1] + 'ies' if words.endswith('y') else words + 's'


def _whole(text: str) -> int | None:
    value = int(text.replace(',', ''))
    return value if value <= MAX_SPOKEN_VALUE else None


def number_words(text: str, *, years: bool = False) -> str:
    """Words of one number written as digits: '72,000', '3.14', '007'; with years=True a plain four-digit 1100..2099 reads as a year."""
    whole, _, fraction = text.partition('.')
    value = _whole(whole)
    if value is None:
        return _digits(whole.replace(',', '')) + (f' point {_digits(fraction)}' if fraction else '')
    if fraction:
        return f'{cardinal_words(value)} point {_digits(fraction)}'
    if len(whole) > 1 and whole[0] == '0':
        return _digits(whole)
    if years and len(whole) == 4:
        return year_words(value)
    return cardinal_words(value)


def _is_one(text: str) -> bool:
    return text.replace(',', '') in ('1', '1.0', '1.00')


def _money(symbol: str, amount: str, scale: str | None) -> str:
    one, many, minor_one, minor_many = _CURRENCIES[symbol]
    if scale:
        return f'{number_words(amount)} {scale} {many}'
    whole, _, cents = amount.partition('.')
    if minor_one and len(cents) == 2:
        value, minor = _whole(whole), int(cents)
        if value is not None:
            parts = [] if value == 0 and minor else [f'{cardinal_words(value)} {one if value == 1 else many}']
            if minor:
                parts.append(f'{cardinal_words(minor)} {minor_one if minor == 1 else minor_many}')
            return ' and '.join(parts)
    return f'{number_words(amount)} {one if _is_one(amount) else many}'


def _spoken(match: re.Match[str]) -> str:
    g = match.groupdict()
    minus = 'minus ' if (g['dneg'] or g['pneg'] or g['nneg']) else ''
    if g['cur']:
        scale = _SCALE_SUFFIXES.get(g['cabbr'] or g['cword'] or '')
        return _money(g['cur'], g['cnum'], scale)
    if g['hh'] is not None:
        hour, minute = int(g['hh']), int(g['mm'])
        if hour > 23:
            return match.group(0)
        gap = ' ' if match.string[match.end():match.end() + 1].isalpha() else ''
        if minute == 0:
            return (f"{cardinal_words(hour)} o'clock" if hour <= 12 else f'{cardinal_words(hour)} hundred') + gap
        return f'{cardinal_words(hour)} {"oh " if minute < 10 else ""}{cardinal_words(minute)}{gap}'
    if g['ra'] is not None:
        tail = ' percent' if g['rpct'] else ''
        return f'{number_words(g["ra"], years=True)} to {number_words(g["rb"], years=True)}{tail}'
    if g['dnum'] is not None:
        degrees = 'degree' if _is_one(g['dnum']) and not minus else 'degrees'
        scale = f' {_DEGREE_SCALES[g["dscale"]]}' if g['dscale'] else ''
        return f'{minus}{number_words(g["dnum"])} {degrees}{scale}'
    if g['unum'] is not None:
        one, many = _UNITS[g['unit']]
        return f'{number_words(g["unum"])} {one if _is_one(g["unum"]) else many}'
    if g['pnum'] is not None:
        return f'{minus}{number_words(g["pnum"])} percent'
    if g['onum'] is not None:
        value = _whole(g['onum'])
        return match.group(0) if value is None or value == 0 else ordinal_words(value)
    if g['dec4'] is not None:
        return _plural(year_words(int(g['dec4'])) if int(g['dec4']) >= 2010 or int(g['dec4']) < 2000 else 'two thousand')
    if g['dec2'] is not None:
        return _plural(cardinal_words(int(g['dec2'])))
    if g['nnum'] is not None:
        return f'{minus}{number_words(g["nnum"])}'
    return number_words(g['num'], years=True)


def speakable_english(text: str) -> str:
    """Text for an English TTS engine: every number written with digits becomes English words (cardinals, decimals, money, percent, degrees, units, ranges, clock times, ordinals, decades, negatives, years); every other character is kept."""
    if not isinstance(text, str):
        raise TypeError('text must be str')
    if not any('0' <= ch <= '9' for ch in text):
        return text
    return _SPOKEN_RE.sub(_spoken, text)


__all__ = ('MAX_SPOKEN_VALUE', 'SPOKEN_NUMBERS_REVISION', 'cardinal_words', 'number_words', 'ordinal_words', 'speakable_english', 'year_words')
