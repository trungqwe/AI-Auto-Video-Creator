"""F-14: content gates of the rendered output (CT-QC-001, CT-QC-002, TST-QC-INV-019).

coveredIds: CT-QC-001, CT-QC-002, TST-QC-INV-019
"""
import ast
import dataclasses
import pathlib
import unittest
from types import SimpleNamespace

from render.domain import content_gates as gates
from render.domain.quality_report import GateName, GateStatus, QualityPolicy, build_quality_report
from render.ports import output_inspector as port

ROOT = pathlib.Path(__file__).resolve().parents[3]
GATES_SOURCE = ROOT / 'src' / 'render' / 'domain' / 'content_gates.py'
PASSED, FAILED = GateStatus.PASSED, GateStatus.FAILED
NOT_EVALUATED, NOT_APPLICABLE = GateStatus.NOT_EVALUATED, GateStatus.NOT_APPLICABLE
POLICY = QualityPolicy(revision='fixture-policy-1', thresholds={
    'VISUAL_HOOK_PRESENT': {'min_similarity': 0.8},
    'AUDIO_HOOK_PRESENT': {'min_level_db': -30.0},
    'SUBTITLE_BURNED_IN': {'min_frames_with_text': 10},
    'KARAOKE_TIMING_VALID': {'tolerance_ms': 80},
    'ENGLISH_OUTPUT_VALID': {'required_language': 'en'},
})
EMPTY_POLICY = QualityPolicy(revision='fixture-policy-empty', thresholds={})
EXPECTED = gates.ExpectedLanguageRevisions(script_fingerprint='fp-1', voice_hash='vh-1', subtitle_text_hash='sh-1')
WORDS = ({'start_ms': 0}, {'start_ms': 400}, {'start_ms': 900})
SEGMENTS = (
    {'segment_id': 's1', 'claim_mode': 'source_backed'},
    {'segment_id': 's2', 'claim_mode': 'inference'},
    {'segment_id': 's3', 'claim_mode': 'transition'},
)
LOCALE_FIELDS = ('script_locale', 'voice_locale', 'subtitle_locale', 'title_locale', 'hashtag_locale')


def make(cls, defaults, overrides):
    return cls(**{**defaults, **overrides})


def package(hook=(2000, 5000), thumbnail_ref='thumb-1', revision='out-meta-v1'):
    placement = {'thumbnail_ref': thumbnail_ref}
    if hook is not None:
        placement['hook_time_range'] = {'start_ms': hook[0], 'end_ms': hook[1]}
    return SimpleNamespace(hook_placement=placement, output_metadata_revision=revision)


def visual(**kw):
    return make(port.VisualHookEvidence, dict(evidence_ref='ev-visual', start_ms=2000, end_ms=4500, similarity=0.9), kw)


def audio(**kw):
    return make(port.AudioHookEvidence, dict(evidence_ref='ev-audio', start_ms=2200, end_ms=4800, level_db=-20.0), kw)


def thumb(**kw):
    return make(port.ThumbnailEvidence, dict(evidence_ref='ev-thumb', time_ms=3000, asset_ref='thumb-1'), kw)


def subtitle(**kw):
    return make(port.SubtitleEvidence, dict(evidence_ref='ev-sub', frames_with_text=120), kw)


def karaoke(offsets=(0, 10, -20)):
    marks = [port.KaraokeWordObservation(word_index=i, highlight_ms=WORDS[i]['start_ms'] + o) for i, o in enumerate(offsets)]
    return port.KaraokeEvidence(evidence_ref='ev-karaoke', observations=marks)


def language(**kw):
    base = dict(evidence_ref='ev-lang', script_fingerprint='fp-1', voice_hash='vh-1', subtitle_text_hash='sh-1',
                output_metadata_revision='out-meta-v1', script_locale='en', voice_locale='en-US', subtitle_locale='en',
                title_locale='en', hashtag_locale='en')
    return make(port.LanguageEvidence, base, kw)


def disclosure(*ids):
    marks = [port.DisclosureObservation(segment_id=s, visible=True) for s in ids]
    return port.DisclosureEvidence(evidence_ref='ev-disc', observations=marks)


def evidence(**kw):
    base = dict(visual_hook=visual(), audio_hook=audio(), thumbnail=thumb(), subtitle=subtitle(), karaoke=karaoke(),
                language=language(), disclosure=disclosure('s2'))
    return port.OutputEvidence(**{**base, **kw})


class GateTestCase(unittest.TestCase):
    def assertNotReady(self, result):
        self.assertIs(result.status, NOT_EVALUATED)
        self.assertTrue(result.reason.startswith(gates.INPUT_NOT_READY), result.reason)

    def assertFailedWith(self, result, reason):
        self.assertIs(result.status, FAILED)
        self.assertTrue(result.reason.startswith(reason), result.reason)


class VisualHookTests(GateTestCase):
    def test_passes_inside_hook_range(self):
        res = gates.check_visual_hook_present(evidence(), package(), POLICY)
        self.assertIs(res.status, PASSED)
        self.assertIs(res.gate, GateName.VISUAL_HOOK_PRESENT)
        self.assertEqual(res.evidence_ref, 'ev-visual')
        self.assertEqual(res.time_range, (2000, 4500))
        self.assertEqual(res.measured_value, 0.9)
        self.assertEqual(res.threshold_revision, 'fixture-policy-1')

    def test_similarity_below_threshold_fails(self):
        res_fail = gates.check_visual_hook_present(evidence(visual_hook=visual(similarity=0.5)), package(), POLICY)
        self.assertFailedWith(res_fail, gates.VISUAL_HOOK_SIMILARITY_LOW)
        res_edge = gates.check_visual_hook_present(evidence(visual_hook=visual(similarity=0.8)), package(), POLICY)
        self.assertIs(res_edge.status, PASSED)

    def test_outside_hook_range_fails(self):
        for ev in (visual(start_ms=0, end_ms=4500), visual(start_ms=2000, end_ms=5001)):
            with self.subTest(ev=ev):
                res = gates.check_visual_hook_present(evidence(visual_hook=ev), package(), POLICY)
                self.assertFailedWith(res, gates.VISUAL_HOOK_OUTSIDE_RANGE)

    def test_not_observed_fails(self):
        res = gates.check_visual_hook_present(evidence(visual_hook=None), package(), POLICY)
        self.assertFailedWith(res, gates.VISUAL_HOOK_NOT_OBSERVED)

    def test_invalid_evidence_fails(self):
        cases = [
            visual(similarity=float('nan')),
            visual(similarity=True),
            visual(start_ms=True),
            visual(evidence_ref=' '),
            visual(start_ms=4600, end_ms=4500),
        ]
        for item in cases:
            with self.subTest(item=item):
                res = gates.check_visual_hook_present(evidence(visual_hook=item), package(), POLICY)
                self.assertFailedWith(res, gates.EVIDENCE_INVALID)

    def test_missing_inputs_not_evaluated(self):
        self.assertNotReady(gates.check_visual_hook_present(evidence(), package(hook=None), POLICY))
        self.assertNotReady(gates.check_visual_hook_present(evidence(), package(), EMPTY_POLICY))
        self.assertNotReady(gates.check_visual_hook_present(None, package(), POLICY))


class AudioHookTests(GateTestCase):
    def test_passes_inside_hook_range(self):
        res = gates.check_audio_hook_present(evidence(), package(), POLICY)
        self.assertIs(res.status, PASSED)
        self.assertIs(res.gate, GateName.AUDIO_HOOK_PRESENT)
        self.assertEqual(res.evidence_ref, 'ev-audio')
        self.assertEqual(res.time_range, (2200, 4800))
        self.assertEqual(res.measured_value, -20.0)
        self.assertEqual(res.threshold_revision, 'fixture-policy-1')

    def test_similarity_below_threshold_fails(self):
        res_fail = gates.check_audio_hook_present(evidence(audio_hook=audio(level_db=-45.0)), package(), POLICY)
        self.assertFailedWith(res_fail, gates.AUDIO_HOOK_LEVEL_LOW)
        res_edge = gates.check_audio_hook_present(evidence(audio_hook=audio(level_db=-30.0)), package(), POLICY)
        self.assertIs(res_edge.status, PASSED)

    def test_outside_hook_range_fails(self):
        for ev in (audio(start_ms=1000), audio(end_ms=5001)):
            with self.subTest(ev=ev):
                res = gates.check_audio_hook_present(evidence(audio_hook=ev), package(), POLICY)
                self.assertFailedWith(res, gates.AUDIO_HOOK_OUTSIDE_RANGE)

    def test_not_observed_fails(self):
        res = gates.check_audio_hook_present(evidence(audio_hook=None), package(), POLICY)
        self.assertFailedWith(res, gates.AUDIO_HOOK_NOT_OBSERVED)

    def test_invalid_evidence_fails(self):
        for item in (audio(level_db=float('nan')), audio(level_db=True)):
            with self.subTest(item=item):
                res = gates.check_audio_hook_present(evidence(audio_hook=item), package(), POLICY)
                self.assertFailedWith(res, gates.EVIDENCE_INVALID)

    def test_missing_inputs_not_evaluated(self):
        self.assertNotReady(gates.check_audio_hook_present(evidence(), package(hook=None), POLICY))
        self.assertNotReady(gates.check_audio_hook_present(evidence(), package(), EMPTY_POLICY))
        self.assertNotReady(gates.check_audio_hook_present(None, package(), POLICY))


class ThumbnailTests(GateTestCase):
    def test_passes_inside_hook_range(self):
        res = gates.check_thumbnail_present(evidence(), package(), POLICY)
        self.assertIs(res.status, PASSED)
        self.assertEqual(res.time_range, (3000, 3000))
        self.assertEqual(res.measured_value, 3000)
        self.assertEqual(res.evidence_ref, 'ev-thumb')
        self.assertEqual(res.threshold_revision, 'fixture-policy-1')
        res_no_policy = gates.check_thumbnail_present(evidence(), package())
        self.assertIs(res_no_policy.status, PASSED)
        self.assertIsNone(res_no_policy.threshold_revision)

    def test_not_hardcoded_to_first_three_seconds(self):
        self.assertIs(gates.check_thumbnail_present(evidence(thumbnail=thumb(time_ms=4900)), package(), POLICY).status, PASSED)
        self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=thumb(time_ms=1000)), package(), POLICY), gates.THUMBNAIL_OUTSIDE_HOOK_RANGE)
        self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=thumb(time_ms=5001)), package(), POLICY), gates.THUMBNAIL_OUTSIDE_HOOK_RANGE)
        self.assertIs(gates.check_thumbnail_present(evidence(thumbnail=thumb(time_ms=2000)), package(), POLICY).status, PASSED)
        self.assertIs(gates.check_thumbnail_present(evidence(thumbnail=thumb(time_ms=5000)), package(), POLICY).status, PASSED)

    def test_asset_mismatch_fails(self):
        self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=thumb(asset_ref='other')), package(), POLICY), gates.THUMBNAIL_ASSET_MISMATCH)

    def test_not_observed_fails(self):
        self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=None), package(), POLICY), gates.THUMBNAIL_NOT_OBSERVED)

    def test_invalid_evidence_fails(self):
        for t in (True, -1, '3000'):
            with self.subTest(time_ms=t):
                bad = make(port.ThumbnailEvidence, dict(evidence_ref='ev-thumb', time_ms=3000, asset_ref='thumb-1'), {'time_ms': t})
                self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=bad), package(), POLICY), gates.EVIDENCE_INVALID)
        self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=thumb(evidence_ref='')), package(), POLICY), gates.EVIDENCE_INVALID)
        self.assertFailedWith(gates.check_thumbnail_present(evidence(thumbnail=thumb(asset_ref=' ')), package(), POLICY), gates.EVIDENCE_INVALID)

    def test_missing_inputs_not_evaluated(self):
        self.assertNotReady(gates.check_thumbnail_present(evidence(), package(hook=None), POLICY))
        self.assertNotReady(gates.check_thumbnail_present(evidence(), package(thumbnail_ref=' '), POLICY))
        self.assertNotReady(gates.check_thumbnail_present(None, package(), POLICY))


class SubtitleTests(GateTestCase):
    def test_passes_with_enough_frames(self):
        res = gates.check_subtitle_burned_in(evidence(), POLICY)
        self.assertIs(res.status, PASSED)
        self.assertEqual(res.evidence_ref, 'ev-sub')
        self.assertEqual(res.measured_value, 120)
        self.assertEqual(res.threshold_revision, 'fixture-policy-1')
        self.assertIs(gates.check_subtitle_burned_in(evidence(subtitle=subtitle(frames_with_text=10)), POLICY).status, PASSED)

    def test_too_few_frames_fails(self):
        for count in (9, 0):
            with self.subTest(frames=count):
                self.assertFailedWith(gates.check_subtitle_burned_in(evidence(subtitle=subtitle(frames_with_text=count)), POLICY), gates.SUBTITLE_FRAMES_BELOW_THRESHOLD)

    def test_not_observed_fails(self):
        self.assertFailedWith(gates.check_subtitle_burned_in(evidence(subtitle=None), POLICY), gates.SUBTITLE_NOT_OBSERVED)

    def test_invalid_evidence_fails(self):
        for f in (True, -1, 1.5):
            with self.subTest(frames=f):
                bad = make(port.SubtitleEvidence, dict(evidence_ref='ev-sub', frames_with_text=10), {'frames_with_text': f})
                self.assertFailedWith(gates.check_subtitle_burned_in(evidence(subtitle=bad), POLICY), gates.EVIDENCE_INVALID)
        self.assertFailedWith(gates.check_subtitle_burned_in(evidence(subtitle=subtitle(evidence_ref='')), POLICY), gates.EVIDENCE_INVALID)

    def test_missing_inputs_not_evaluated(self):
        self.assertNotReady(gates.check_subtitle_burned_in(evidence(), EMPTY_POLICY))
        self.assertNotReady(gates.check_subtitle_burned_in(evidence(), QualityPolicy(revision='p', thresholds={'SUBTITLE_BURNED_IN': {'min_frames_with_text': 0}})))
        self.assertNotReady(gates.check_subtitle_burned_in(None, POLICY))


class KaraokeTests(GateTestCase):
    def test_passes_within_tolerance(self):
        res = gates.check_karaoke_timing_valid(evidence(karaoke=karaoke()), WORDS, POLICY)
        self.assertIs(res.status, PASSED)
        self.assertEqual(res.measured_value, 20)
        self.assertEqual(res.evidence_ref, 'ev-karaoke')
        self.assertEqual(res.threshold_revision, 'fixture-policy-1')
        self.assertIs(gates.check_karaoke_timing_valid(evidence(karaoke=karaoke((0, 80, -80))), WORDS, POLICY).status, PASSED)

    def test_deviation_over_tolerance_fails(self):
        res1 = gates.check_karaoke_timing_valid(evidence(karaoke=karaoke((0, 81, 0))), WORDS, POLICY)
        self.assertFailedWith(res1, gates.KARAOKE_OUT_OF_TOLERANCE)
        self.assertEqual(res1.measured_value, 81)
        res2 = gates.check_karaoke_timing_valid(evidence(karaoke=karaoke((-200, 0, 0))), WORDS, POLICY)
        self.assertFailedWith(res2, gates.KARAOKE_OUT_OF_TOLERANCE)

    def test_missing_observations_not_evaluated(self):
        for k in (None, port.KaraokeEvidence(evidence_ref='e', observations=[])):
            with self.subTest(k=k):
                res = gates.check_karaoke_timing_valid(evidence(karaoke=k), WORDS, POLICY)
                self.assertIs(res.status, NOT_EVALUATED)
                self.assertEqual(res.reason, gates.KARAOKE_OBSERVATION_MISSING)

    def test_missing_word_timings_not_evaluated(self):
        for wt in ((), None, 'abc', [{'start_ms': True}], [{'start_ms': -1}], [1]):
            with self.subTest(wt=wt):
                self.assertNotReady(gates.check_karaoke_timing_valid(evidence(), wt, POLICY))

    def test_partial_observations_fail(self):
        self.assertFailedWith(gates.check_karaoke_timing_valid(evidence(karaoke=karaoke((0, 0))), WORDS, POLICY), gates.KARAOKE_WORD_NOT_OBSERVED)

    def test_invalid_observations_fail(self):
        dup = port.KaraokeEvidence(evidence_ref='ev-karaoke', observations=(port.KaraokeWordObservation(word_index=0, highlight_ms=0), port.KaraokeWordObservation(word_index=0, highlight_ms=10)))
        self.assertFailedWith(gates.check_karaoke_timing_valid(evidence(karaoke=dup), WORDS, POLICY), gates.KARAOKE_OBSERVATION_INVALID)
        idx3 = port.KaraokeEvidence(evidence_ref='ev-karaoke', observations=(port.KaraokeWordObservation(word_index=3, highlight_ms=0),))
        self.assertFailedWith(gates.check_karaoke_timing_valid(evidence(karaoke=idx3), WORDS, POLICY), gates.KARAOKE_OBSERVATION_INVALID)
        bool_idx = port.KaraokeEvidence(evidence_ref='ev-karaoke', observations=(port.KaraokeWordObservation(word_index=True, highlight_ms=0),))
        self.assertFailedWith(gates.check_karaoke_timing_valid(evidence(karaoke=bool_idx), WORDS, POLICY), gates.KARAOKE_OBSERVATION_INVALID)
        str_ms = port.KaraokeEvidence(evidence_ref='ev-karaoke', observations=(port.KaraokeWordObservation(word_index=0, highlight_ms='1'),))
        self.assertFailedWith(gates.check_karaoke_timing_valid(evidence(karaoke=str_ms), WORDS, POLICY), gates.KARAOKE_OBSERVATION_INVALID)

    def test_invalid_tolerance_not_evaluated(self):
        for tol in (-1, 1.5, True):
            pol = QualityPolicy(revision='p', thresholds={'KARAOKE_TIMING_VALID': {'tolerance_ms': tol}})
            with self.subTest(tol=tol):
                self.assertNotReady(gates.check_karaoke_timing_valid(evidence(), WORDS, pol))
        self.assertNotReady(gates.check_karaoke_timing_valid(evidence(), WORDS, EMPTY_POLICY))

    def test_evidence_none_not_evaluated(self):
        self.assertNotReady(gates.check_karaoke_timing_valid(None, WORDS, POLICY))
        blank_ev = port.KaraokeEvidence(evidence_ref=' ', observations=karaoke().observations)
        self.assertFailedWith(gates.check_karaoke_timing_valid(evidence(karaoke=blank_ev), WORDS, POLICY), gates.EVIDENCE_INVALID)


class EnglishOutputTests(GateTestCase):
    def test_passes_with_exact_revisions_and_locales(self):
        res = gates.check_english_output_valid(evidence(), package(), EXPECTED, POLICY)
        self.assertIs(res.status, PASSED)
        self.assertEqual(res.evidence_ref, 'ev-lang')
        self.assertEqual(res.threshold_revision, 'fixture-policy-1')

    def test_stale_revision_fails(self):
        cases = [
            ('voice_hash', language(voice_hash='vh-old')),
            ('script_fingerprint', language(script_fingerprint='fp-old')),
            ('subtitle_text_hash', language(subtitle_text_hash='sh-old')),
        ]
        for name, lang in cases:
            with self.subTest(field=name):
                res = gates.check_english_output_valid(evidence(language=lang), package(), EXPECTED, POLICY)
                self.assertFailedWith(res, gates.LANGUAGE_EVIDENCE_REVISION_MISMATCH)
                self.assertIn(name, res.reason)
        res_pkg = gates.check_english_output_valid(evidence(), package(revision='out-meta-v2'), EXPECTED, POLICY)
        self.assertFailedWith(res_pkg, gates.LANGUAGE_EVIDENCE_REVISION_MISMATCH)
        self.assertIn('output_metadata_revision', res_pkg.reason)
        res_none = gates.check_english_output_valid(evidence(language=language(output_metadata_revision=None)), package(), EXPECTED, POLICY)
        self.assertFailedWith(res_none, gates.LANGUAGE_EVIDENCE_REVISION_MISMATCH)

    def test_each_locale_must_equal_required_language(self):
        for name in LOCALE_FIELDS:
            with self.subTest(locale=name, value='fr'):
                res = gates.check_english_output_valid(evidence(language=language(**{name: 'fr'})), package(), EXPECTED, POLICY)
                self.assertFailedWith(res, gates.LANGUAGE_MISMATCH)
                self.assertIn(name, res.reason)
            with self.subTest(locale=name, value=None):
                res = gates.check_english_output_valid(evidence(language=language(**{name: None})), package(), EXPECTED, POLICY)
                self.assertFailedWith(res, gates.LANGUAGE_MISMATCH)
                self.assertIn(name, res.reason)

    def test_self_declared_language_is_not_evidence(self):
        none_locales = {name: None for name in LOCALE_FIELDS}
        res1 = gates.check_english_output_valid(evidence(language=language(**none_locales, declared_language='en')), package(), EXPECTED, POLICY)
        self.assertIs(res1.status, FAILED)
        fr_locales = {name: 'fr' for name in LOCALE_FIELDS}
        res2 = gates.check_english_output_valid(evidence(language=language(**fr_locales, declared_language='en')), package(), EXPECTED, POLICY)
        self.assertIs(res2.status, FAILED)
        res3 = gates.check_english_output_valid(evidence(language=None), package(), EXPECTED, POLICY)
        self.assertFailedWith(res3, gates.LANGUAGE_EVIDENCE_MISSING)

    def test_locale_matching(self):
        pol_en = QualityPolicy(revision='p-en', thresholds={'ENGLISH_OUTPUT_VALID': {'required_language': 'en'}})
        for loc in ('en_US', 'EN-gb'):
            all_loc = {name: loc for name in LOCALE_FIELDS}
            self.assertIs(gates.check_english_output_valid(evidence(language=language(**all_loc)), package(), EXPECTED, pol_en).status, PASSED)
        pol_en_us = QualityPolicy(revision='p-en-us', thresholds={'ENGLISH_OUTPUT_VALID': {'required_language': 'en-US'}})
        all_en = {name: 'en' for name in LOCALE_FIELDS}
        res_sub = gates.check_english_output_valid(evidence(language=language(**all_en)), package(), EXPECTED, pol_en_us)
        self.assertFailedWith(res_sub, gates.LANGUAGE_MISMATCH)
        pol_vi = QualityPolicy(revision='p-vi', thresholds={'ENGLISH_OUTPUT_VALID': {'required_language': 'vi'}})
        res_vi = gates.check_english_output_valid(evidence(), package(), EXPECTED, pol_vi)
        self.assertFailedWith(res_vi, gates.LANGUAGE_MISMATCH)

    def test_missing_inputs_not_evaluated(self):
        self.assertNotReady(gates.check_english_output_valid(evidence(), package(), EXPECTED, EMPTY_POLICY))
        pol_space = QualityPolicy(revision='p', thresholds={'ENGLISH_OUTPUT_VALID': {'required_language': ' '}})
        self.assertNotReady(gates.check_english_output_valid(evidence(), package(), EXPECTED, pol_space))
        self.assertNotReady(gates.check_english_output_valid(evidence(), package(), None, POLICY))
        exp_space = gates.ExpectedLanguageRevisions(script_fingerprint='fp-1', voice_hash=' ', subtitle_text_hash='sh-1')
        self.assertNotReady(gates.check_english_output_valid(evidence(), package(), exp_space, POLICY))
        self.assertNotReady(gates.check_english_output_valid(evidence(), package(revision=' '), EXPECTED, POLICY))
        self.assertNotReady(gates.check_english_output_valid(None, package(), EXPECTED, POLICY))


class InferenceDisclosureTests(GateTestCase):
    def test_not_applicable_without_inference_segments(self):
        no_inf = ({'segment_id': 's1', 'claim_mode': 'source_backed'}, {'segment_id': 's3', 'claim_mode': 'transition'})
        for segs in (no_inf, ()):
            for ev in (evidence(), None, evidence(disclosure=None)):
                with self.subTest(segs=len(segs), ev=type(ev)):
                    res = gates.check_inference_disclosure_present(ev, segs)
                    self.assertIs(res.status, NOT_APPLICABLE)
                    self.assertEqual(res.reason, gates.REASON_NOT_APPLICABLE)

    def test_passes_when_inference_segment_disclosed(self):
        res = gates.check_inference_disclosure_present(evidence(disclosure=disclosure('s2')), SEGMENTS)
        self.assertIs(res.status, PASSED)
        self.assertEqual(res.evidence_ref, 'ev-disc')
        self.assertEqual(res.measured_value, 1)

    def test_inference_without_disclosure_fails(self):
        res_none = gates.check_inference_disclosure_present(evidence(disclosure=None), SEGMENTS)
        self.assertFailedWith(res_none, gates.DISCLOSURE_NOT_OBSERVED)
        res_wrong = gates.check_inference_disclosure_present(evidence(disclosure=disclosure('s9')), SEGMENTS)
        self.assertFailedWith(res_wrong, gates.DISCLOSURE_MISSING)
        self.assertIn('s2', res_wrong.reason)

    def test_visibility_must_be_true(self):
        for v in (False, 'yes', 1):
            obs = port.DisclosureEvidence(evidence_ref='ev-disc', observations=(port.DisclosureObservation(segment_id='s2', visible=v),))
            with self.subTest(visible=v):
                self.assertFailedWith(gates.check_inference_disclosure_present(evidence(disclosure=obs), SEGMENTS), gates.DISCLOSURE_MISSING)

    def test_creative_hypothesis_requires_disclosure(self):
        hyp_segs = [{'segment_id': 'c1', 'claim_mode': 'creative_hypothesis'}]
        self.assertFailedWith(gates.check_inference_disclosure_present(evidence(disclosure=disclosure()), hyp_segs), gates.DISCLOSURE_MISSING)
        self.assertIs(gates.check_inference_disclosure_present(evidence(disclosure=disclosure('c1')), hyp_segs).status, PASSED)

    def test_every_applicable_segment_needs_disclosure(self):
        both_segs = ({'segment_id': 's2', 'claim_mode': 'inference'}, {'segment_id': 'c1', 'claim_mode': 'creative_hypothesis'})
        res_part = gates.check_inference_disclosure_present(evidence(disclosure=disclosure('s2')), both_segs)
        self.assertFailedWith(res_part, gates.DISCLOSURE_MISSING)
        self.assertIn('c1', res_part.reason)
        res_both = gates.check_inference_disclosure_present(evidence(disclosure=disclosure('s2', 'c1')), both_segs)
        self.assertIs(res_both.status, PASSED)
        self.assertEqual(res_both.measured_value, 2)

    def test_malformed_segments_not_evaluated(self):
        for s in (None, 'abc', [1], [{'segment_id': 's', 'claim_mode': None}], [{'segment_id': ' ', 'claim_mode': 'inference'}]):
            with self.subTest(segments=s):
                self.assertNotReady(gates.check_inference_disclosure_present(evidence(), s))
        self.assertNotReady(gates.check_inference_disclosure_present(None, SEGMENTS))


class FakeInspector:
    def __init__(self, result: port.OutputEvidence) -> None:
        self.result = result
        self.calls: list[tuple[str, object]] = []

    def inspect(self, output_ref: str, package: object) -> port.OutputEvidence:
        self.calls.append((output_ref, package))
        return self.result


class EvaluateContentGatesTests(GateTestCase):
    def test_returns_seven_results_in_gate_order_and_inspects_once(self):
        pkg = package()
        fake = FakeInspector(evidence())
        results = gates.evaluate_content_gates(fake, 'out-1', pkg, POLICY, EXPECTED, WORDS, SEGMENTS)
        self.assertEqual(
            tuple(r.gate for r in results),
            (
                GateName.VISUAL_HOOK_PRESENT,
                GateName.AUDIO_HOOK_PRESENT,
                GateName.THUMBNAIL_PRESENT,
                GateName.SUBTITLE_BURNED_IN,
                GateName.KARAOKE_TIMING_VALID,
                GateName.ENGLISH_OUTPUT_VALID,
                GateName.INFERENCE_DISCLOSURE_PRESENT,
            ),
        )
        for r in results:
            self.assertIs(r.status, PASSED)
        self.assertEqual(fake.calls, [('out-1', pkg)])

    def test_counterexamples_do_not_pass(self):
        fake = FakeInspector(evidence(
            thumbnail=thumb(time_ms=1000),
            language=language(voice_hash='vh-old'),
            disclosure=disclosure(),
            karaoke=karaoke((0, 500, 0)),
        ))
        results = {r.gate: r for r in gates.evaluate_content_gates(fake, 'out-1', package(), POLICY, EXPECTED, WORDS, SEGMENTS)}
        self.assertIs(results[GateName.THUMBNAIL_PRESENT].status, FAILED)
        self.assertIs(results[GateName.ENGLISH_OUTPUT_VALID].status, FAILED)
        self.assertIs(results[GateName.INFERENCE_DISCLOSURE_PRESENT].status, FAILED)
        self.assertIs(results[GateName.KARAOKE_TIMING_VALID].status, FAILED)
        self.assertIs(results[GateName.VISUAL_HOOK_PRESENT].status, PASSED)
        self.assertIs(results[GateName.AUDIO_HOOK_PRESENT].status, PASSED)
        self.assertIs(results[GateName.SUBTITLE_BURNED_IN].status, PASSED)

    def test_feeds_quality_report(self):
        source_segs = ({'segment_id': 's1', 'claim_mode': 'source_backed'},)
        fake = FakeInspector(evidence())
        results = gates.evaluate_content_gates(fake, 'out-1', package(), POLICY, EXPECTED, WORDS, source_segs)
        res_map = {r.gate: r for r in results}
        self.assertIs(res_map[GateName.INFERENCE_DISCLOSURE_PRESENT].status, NOT_APPLICABLE)
        report = build_quality_report(results, {GateName.INFERENCE_DISCLOSURE_PRESENT: False}, policy=POLICY)
        self.assertFalse(report.passed)
        content_gates_set = {
            GateName.VISUAL_HOOK_PRESENT,
            GateName.AUDIO_HOOK_PRESENT,
            GateName.THUMBNAIL_PRESENT,
            GateName.SUBTITLE_BURNED_IN,
            GateName.KARAOKE_TIMING_VALID,
            GateName.ENGLISH_OUTPUT_VALID,
            GateName.INFERENCE_DISCLOSURE_PRESENT,
        }
        self.assertEqual(set(report.blocking_gates) & content_gates_set, set())


class EvidenceShapeTests(unittest.TestCase):
    def test_evidence_dataclasses_are_frozen_and_kw_only(self):
        classes = (
            port.VisualHookEvidence,
            port.AudioHookEvidence,
            port.ThumbnailEvidence,
            port.SubtitleEvidence,
            port.KaraokeWordObservation,
            port.KaraokeEvidence,
            port.LanguageEvidence,
            port.DisclosureObservation,
            port.DisclosureEvidence,
            port.OutputEvidence,
        )
        for cls in classes:
            with self.subTest(cls=cls.__name__):
                self.assertTrue(dataclasses.is_dataclass(cls))
                self.assertTrue(cls.__dataclass_params__.frozen)
                self.assertTrue(cls.__dataclass_params__.kw_only)
        ev = evidence()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            ev.visual_hook = None

    def test_sequences_are_coerced_to_tuples(self):
        self.assertIsInstance(karaoke().observations, tuple)
        self.assertIsInstance(disclosure('s2').observations, tuple)

    def test_output_evidence_defaults_to_none(self):
        out = port.OutputEvidence()
        for f in dataclasses.fields(out):
            self.assertIsNone(getattr(out, f.name))
        self.assertIsNone(port.LanguageEvidence(evidence_ref='x').declared_language)


class SourceHygieneTests(unittest.TestCase):
    def test_no_hardcoded_thresholds_or_language(self):
        tree = ast.parse(GATES_SOURCE.read_text(encoding='utf-8'))
        forbidden_nums = {3, 3000, 61, 70, 61000, 70000, 1080, 1920}
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant):
                if type(node.value) in (int, float) and not isinstance(node.value, bool):
                    self.assertNotIn(node.value, forbidden_nums, f'Found forbidden numeric constant: {node.value}')
                if isinstance(node.value, str):
                    self.assertNotEqual(node.value, 'en', 'Found forbidden literal string "en"')

    def test_gate_sources_do_not_import_other_slices(self):
        tree = ast.parse(GATES_SOURCE.read_text(encoding='utf-8'))
        allowed_roots = ('render.', 'collections.abc', 'dataclasses', '__future__', 'math')
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                mod = node.module or ''
                self.assertTrue(any(mod == root or mod.startswith(root) for root in allowed_roots), f'Forbidden import: {mod}')
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertTrue(any(alias.name == root or alias.name.startswith(root) for root in allowed_roots), f'Forbidden import: {alias.name}')
