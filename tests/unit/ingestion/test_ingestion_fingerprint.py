"""B-2: exact fingerprint and near-duplicate detection driven by the dedup policy revision (D8-B-01)."""
import hashlib
import pathlib
import re
import unicodedata

import pytest

from ingestion.domain.fingerprint import exact_fingerprint, is_near_duplicate, jaccard, shingles

ROOT = pathlib.Path(__file__).resolve().parents[3]
FINGERPRINT_SOURCE = ROOT / 'src' / 'ingestion' / 'domain' / 'fingerprint.py'
POLICY = {'dedup_policy_revision': 'dedup-policy-r1', 'near_duplicate_jaccard': 0.90, 'shingle_size': 5}
VIETNAMESE = 'Hà Nội mưa lớn, người dân đội mũ bảo hiểm khi đi xe máy'
VIETNAMESE_SHA256 = hashlib.sha256(VIETNAMESE.encode('utf-8')).hexdigest()
SHA256_ABC = 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'
WORDS = 'Sáng nay trung tâm khí tượng quốc gia cảnh báo mưa lớn diện rộng'.split()
BASE = ' '.join(WORDS)
EXACTLY_090 = ' '.join(WORDS[:13])
BELOW_090 = ' '.join(WORDS[:12])


def test_exact_fingerprint_is_sha256_hex_of_normalized_text() -> None:
    assert exact_fingerprint('abc') == SHA256_ABC
    assert exact_fingerprint('  abc \n') == SHA256_ABC
    assert re.fullmatch(r'[0-9a-f]{64}', exact_fingerprint(VIETNAMESE))


def test_nfc_and_nfd_vietnamese_share_fingerprint() -> None:
    nfd = unicodedata.normalize('NFD', VIETNAMESE)
    assert nfd != VIETNAMESE
    assert exact_fingerprint(nfd) == exact_fingerprint(VIETNAMESE) == VIETNAMESE_SHA256


def test_whitespace_and_control_characters_do_not_change_fingerprint() -> None:
    noisy = '  Hà\tNội\n\nmưa lớn, người dân\x00 đội mũ bảo hiểm khi đi xe máy ​'
    assert exact_fingerprint(noisy) == VIETNAMESE_SHA256


def test_different_text_changes_fingerprint() -> None:
    assert exact_fingerprint(VIETNAMESE) != exact_fingerprint(VIETNAMESE + ' hôm nay')


def test_fingerprint_is_deterministic_across_runs() -> None:
    first = exact_fingerprint(VIETNAMESE)
    assert len(first) == 64
    assert exact_fingerprint(VIETNAMESE) == first
    assert is_near_duplicate(BASE, EXACTLY_090, POLICY) is is_near_duplicate(BASE, EXACTLY_090, POLICY) is True


def test_shingles_use_requested_size_on_normalized_words() -> None:
    assert shingles(' a  b\tc d ', 2) == frozenset({('a', 'b'), ('b', 'c'), ('c', 'd')})
    assert shingles('a b', 5) == frozenset({('a', 'b')})
    assert shingles(' \n ', 5) == frozenset()
    assert len(WORDS) == 14
    assert len(shingles(BASE, 5)) == 10
    assert shingles(unicodedata.normalize('NFD', VIETNAMESE), 5) == shingles(VIETNAMESE, 5)


def test_shingle_size_must_be_positive_integer() -> None:
    for size in (0, -1, 2.5, True, '5', None):
        with pytest.raises(ValueError):
            shingles(BASE, size)


def test_jaccard_ratio() -> None:
    assert jaccard({1, 2, 3}, {2, 3, 4}) == 0.5
    assert jaccard({1}, {1}) == 1.0
    assert jaccard(set(), set()) == 0.0
    assert jaccard({1}, set()) == 0.0


def test_boundary_exactly_090_is_near_duplicate() -> None:
    assert jaccard(shingles(BASE, 5), shingles(EXACTLY_090, 5)) == 0.9
    assert is_near_duplicate(BASE, EXACTLY_090, POLICY) is True
    assert is_near_duplicate(EXACTLY_090, BASE, POLICY) is True


def test_below_090_is_not_near_duplicate() -> None:
    assert jaccard(shingles(BASE, 5), shingles(BELOW_090, 5)) == 0.8
    assert is_near_duplicate(BASE, BELOW_090, POLICY) is False


def test_threshold_is_read_from_policy() -> None:
    assert is_near_duplicate(BASE, BELOW_090, {**POLICY, 'near_duplicate_jaccard': 0.80}) is True
    assert is_near_duplicate(BASE, EXACTLY_090, {**POLICY, 'near_duplicate_jaccard': 0.95}) is False


def test_shingle_size_is_read_from_policy() -> None:
    reordered = ' '.join(reversed(WORDS))
    assert is_near_duplicate(BASE, reordered, {**POLICY, 'shingle_size': 1}) is True
    assert is_near_duplicate(BASE, reordered, POLICY) is False


def test_missing_or_invalid_policy_values_fail_closed() -> None:
    with pytest.raises(KeyError):
        is_near_duplicate(BASE, BASE, {'shingle_size': 5})
    with pytest.raises(KeyError):
        is_near_duplicate(BASE, BASE, {'near_duplicate_jaccard': 0.90})
    for threshold in (0, -0.1, 1.5, True, '0.90', None):
        with pytest.raises(ValueError):
            is_near_duplicate(BASE, BASE, {**POLICY, 'near_duplicate_jaccard': threshold})
    with pytest.raises(ValueError):
        is_near_duplicate(BASE, BASE, {**POLICY, 'shingle_size': 0})


def test_fingerprint_module_has_no_hard_coded_policy_values() -> None:
    source = FINGERPRINT_SOURCE.read_text(encoding='utf-8')
    assert not re.search(r'0\.9|\b5\b|dedup-policy-r1', source)
