"""TTS-NUMBERS: numbers written with digits reach Kokoro as English words; the script text keeps its digits.

coveredIds: CT-TTS-001

Measured on CP7-11 (02/11/2026): the script "72,000" was spoken "seventy-two, zero zero zero". kokoro-onnx 0.4.9 phonemizes with
espeak-ng through phonemizer(preserve_punctuation=True), which splits '72,000' at the comma before espeak reads it.
The engine is a recording model injected through model_factory and Whisper is faked behind model_factory of the aligner;
the only library run is the espeak-ng g2p of kokoro_onnx.tokenizer (no weights, no network).
"""
from __future__ import annotations

import hashlib
import importlib
import importlib.util
import json
import pathlib

import numpy as np
import pytest

from voice.adapters.real_kokoro_tts import KokoroConfig, RealKokoroTts
from voice.domain.timing_coverage import check_coverage
from voice.domain.tts_invocation import ProviderRouteDecision
from voice.domain.word_timing import validate_word_timing
from voice.ports.script_text import ScriptText

FINGERPRINT = 'b' * 64
RATE = 24000
WEIGHT_FILES = {'kokoro-v1.0.onnx': b'fake-kokoro-model', 'voices-v1.0.bin': b'fake-kokoro-voices'}
ZERO = 'zˈiəɹoʊ'
_NUMBERS_TEST = pathlib.Path(__file__).with_name('test_adapt_e_aligner_numbers.py')


def spoken_module():
    return importlib.import_module('voice.domain.spoken_numbers')


def speakable(text: str) -> str:
    return spoken_module().speakable_english(text)


def aligner_helpers():
    spec = importlib.util.spec_from_file_location('adapt_e_aligner_numbers_for_tts_numbers', _NUMBERS_TEST)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize('text, spoken', [
    ('The prize was 72,000 dollars.', 'The prize was seventy-two thousand dollars.'),
    ('1,250,000 people', 'one million two hundred fifty thousand people'),
    ('Pi is 3.14 and 0.5 is half.', 'Pi is three point one four and zero point five is half.'),
    ('It grew 1.5% and 5–10% more.', 'It grew one point five percent and five to ten percent more.'),
    ('A $1.5 billion deal, €20m and £3.2bn.', 'A one point five billion dollars deal, twenty million euros and three point two billion pounds.'),
    ('It cost $4.99, $0.50 or $1.', 'It cost four dollars and ninety-nine cents, fifty cents or one dollar.'),
    ('In 1999, 1905, 1900, 2005 and 2024.', 'In nineteen ninety-nine, nineteen oh five, nineteen hundred, two thousand five and twenty twenty-four.'),
    ('From 2020–2024, 2020-24 and a 66-45 win.', 'From twenty twenty to twenty twenty-four, twenty twenty to twenty-four and a sixty-six to forty-five win.'),
    ('The 21st title, the 100th race, the 1,000th fan.', 'The twenty-first title, the one hundredth race, the one thousandth fan.'),
    ('It was 50°C, then -5°C and 1°.', 'It was fifty degrees Celsius, then minus five degrees Celsius and one degree.'),
    ('A 3km run, 2.5 kg, 1 km, 60 mph.', 'A three kilometers run, two point five kilograms, one kilometer, sixty miles per hour.'),
    ('It fell to -12 overnight.', 'It fell to minus twelve overnight.'),
    ("The 1990s, the '80s and the 2000s.", 'The nineteen nineties, the eighties and the two thousands.'),
    ('At 8:30pm, 10:05 and 9:00.', "At eight thirty pm, ten oh five and nine o'clock."),
    ('Agent 007.', 'Agent zero zero seven.'),
])
def test_numbers_become_english_words(text, spoken):
    assert speakable(text) == spoken


@pytest.mark.parametrize('text, spoken', [
    ('Nothing numeric here, just words.', 'Nothing numeric here, just words.'),
    ('3D, 5G, MP3 and 24/7 stay as written.', '3D, 5G, MP3 and 24/7 stay as written.'),
    ('COVID-19 and the F-35.', 'COVID-nineteen and the F-thirty-five.'),
])
def test_numbers_glued_to_letters_or_slashes_are_left_to_the_engine(text, spoken):
    assert speakable(text) == spoken


def test_word_helpers_cover_large_values_and_ordinals():
    module = spoken_module()
    assert module.cardinal_words(0) == 'zero'
    assert module.cardinal_words(72000) == 'seventy-two thousand'
    assert module.cardinal_words(999_999_999_999_999) == ('nine hundred ninety-nine trillion nine hundred ninety-nine billion nine hundred ninety-nine million '
                                                           'nine hundred ninety-nine thousand nine hundred ninety-nine')
    assert [module.ordinal_words(n) for n in (1, 2, 3, 5, 8, 9, 12, 20, 42, 1000)] == [
        'first', 'second', 'third', 'fifth', 'eighth', 'ninth', 'twelfth', 'twentieth', 'forty-second', 'one thousandth']
    assert module.SPOKEN_NUMBERS_REVISION == 'spoken-en-1'
    with pytest.raises(ValueError):
        module.cardinal_words(10 ** 15)


def test_espeak_reads_the_spoken_form_without_digit_by_digit_zeros():
    from kokoro_onnx.tokenizer import Tokenizer

    tokenizer = Tokenizer()
    assert ZERO in tokenizer.phonemize('72,000', 'en-us')  # the defect, reproduced on the pinned g2p
    for text, word in (('72,000', 'θˈaʊzənd'), ('1,250,000', 'mˈɪliən'), ('$1.5 billion', 'pˈɔɪnt'), ('1.5%', 'pɚsˈɛnt')):
        phonemes = tokenizer.phonemize(speakable(text), 'en-us')
        assert word in phonemes and ZERO not in phonemes and ',' not in phonemes and '.' not in phonemes, (text, phonemes)


class RecordingModel:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def create(self, text: str, voice: str, speed: float, lang: str) -> tuple[np.ndarray, int]:
        self.texts.append(text)
        return np.linspace(-0.5, 0.5, 2400, dtype=np.float32), RATE


def _engine(tmp_path: pathlib.Path, language: str) -> tuple[RealKokoroTts, RecordingModel]:
    root = tmp_path / language
    weights, staging = root / 'weights', root / 'staging'
    weights.mkdir(parents=True)
    staging.mkdir()
    for name, data in WEIGHT_FILES.items():
        (weights / name).write_bytes(data)
    lock = root / 'lock.json'
    entries = [{'name': n, 'group': 'kokoro-onnx', 'sha256': hashlib.sha256(d).hexdigest(), 'status': 'PINNED'} for n, d in WEIGHT_FILES.items()]
    lock.write_text(json.dumps({'schema_version': 1, 'files': entries}), encoding='utf-8')
    config = KokoroConfig(weights_dir=weights, lock_path=lock, staging_dir=staging, voice='af_heart', speed=1.0, language=language, sample_rate=RATE)
    model = RecordingModel()
    return RealKokoroTts(config, model_factory=lambda model_path, voices_path: model), model


def _decision() -> ProviderRouteDecision:
    return ProviderRouteDecision(
        provider_ref='kokoro-local', model_ref='kokoro-v1.0', account_ref='local', route_revision='r1', rationale_codes=('LOCAL',),
        fallback_order=(), capacity_reservation_ref='res-1', credential_acquisition_method='none', estimated_cost_class='free',
    )


def _request() -> dict[str, object]:
    return dict(script_version_id='sv-1', script_fingerprint=FINGERPRINT, voice_profile_ref='vp-1', provider_route_ref='pr-1',
                expected_language='en-US', operation_key='op-1', execution_grant_ref='g-1')


def test_kokoro_receives_spoken_numbers_and_the_script_keeps_its_digits(tmp_path):
    text = 'The prize was 72,000 dollars, up 1.5% since 2024.'
    script = ScriptText('sv-1', text, FINGERPRINT)
    engine, model = _engine(tmp_path, 'en-us')
    result = engine.synthesize(_decision(), script, _request())
    assert model.texts == ['The prize was seventy-two thousand dollars, up one point five percent since twenty twenty-four.']
    assert script.text == text and result.usage_metrics['characters'] == len(text)
    assert ';numbers=spoken-en-1' in result.voice_revision

    other, other_model = _engine(tmp_path, 'fr-fr')
    kept = other.synthesize(_decision(), script, _request())
    assert other_model.texts == [text] and ';numbers=' not in kept.voice_revision


@pytest.mark.parametrize('number', ['72,000', '1.5%', '$1.5 billion', '2020–2024', '50°C', '1999', '1,250,000'])
@pytest.mark.parametrize('whisper', ['spoken words', 'script digits'])
def test_aligner_covers_script_digits_for_the_spoken_audio(tmp_path, number, whisper):
    helpers = aligner_helpers()
    filler = ' '.join(f'w{i}' for i in range(30))
    text = f'{filler} they saw {number} today {filler}.'
    spoken = speakable(text)
    assert spoken != text  # Kokoro reads the spoken form; Whisper may write it back as words or as the digits of the script
    heard_text = spoken if whisper == 'spoken words' else text
    heard = helpers.steps(heard_text.split(), step=0.3)
    result, aligner, payload = helpers.run_align(tmp_path, text, heard, max_ratio=0.05, duration_ms=300 * len(heard) + 1000)
    assert aligner.last_report.missing_script_indices == ()
    assert set(number.split()) <= {w['text'] for w in result.words}  # the subtitle words keep the digits of the script
    assert check_coverage(text, validate_word_timing(payload).words, helpers.POLICY).complete
