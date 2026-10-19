"""J-02: redaction sâu, SecretValue và quét canary (CT-SEC-003 điều 6, INV-012).

coveredIds: TST-SEC-INV-012, CT-SEC-003, QR-SEC-002
"""
import copy
import dataclasses
import json
import pickle

import pytest

from controlplane.infrastructure.security import redaction, secret_redaction
from controlplane.infrastructure.security.secret_redaction import (
    SecretValue, find_canaries, redact_exception, redact_value,
)

C_PASSWORD = 'CANARY-J02-PASSWORD-7f3a91'
C_NESTED = 'CANARY-J02-NESTED-b21c40'
C_HEADER = 'CANARY-J02-HEADER-55d0e2'
C_SK = 'sk-CANARYJ02SK1234567890'
C_AIZA = 'AIza' + ('CANARYJ02' + '0123456789abcdefghijklmnopqrstuvwxyz')[:35]
C_JWT = 'eyJCQU5BUlk.eyJKMDJQQVlMT0FE.CANARYJ02SIG'
C_YA29 = 'ya29.CANARYJ02OAUTHTOKEN'
C_URL_TOKEN = 'CANARY-J02-URLTOKEN-91ab'
C_URL_KEY = 'CANARY-J02-URLKEY-62cd'
C_URL_UPLOAD = 'CANARY-J02-UPLOAD-33ef'
C_URL_SIG = 'CANARY-J02-SIG-84aa'
C_EXC = 'CANARY-J02-EXC-1d2e3f'
ALL_CANARIES = [
    C_PASSWORD, C_NESTED, C_HEADER, C_SK, C_AIZA, C_JWT, C_YA29,
    C_URL_TOKEN, C_URL_KEY, C_URL_UPLOAD, C_URL_SIG,
]
URL = (
    f'https://example.invalid/upload?upload_id={C_URL_UPLOAD}&signature={C_URL_SIG}'
    f'&token={C_URL_TOKEN}&key={C_URL_KEY}&keep=1'
)
KEY_CASES = (
    list(secret_redaction.SENSITIVE_KEYS)
    + [name.upper() for name in secret_redaction.SENSITIVE_KEYS]
    + ['Api_Key', 'X-Api-Key', 'db_password', 'Proxy-Authorization']
)


def _payload() -> dict:
    return {
        'model': 'gemini',
        'max_tokens': 10,
        'password': C_PASSWORD,
        'outer': [{'inner': ({'Client_Secret': C_NESTED},)}],
        'headers': {'Authorization': f'Bearer {C_HEADER}'},
        'text': [
            f'Authorization: Bearer {C_HEADER}', f'password={C_PASSWORD}',
            C_SK, C_AIZA, C_JWT, C_YA29, URL,
        ],
        'ids': {C_SK, C_AIZA},
    }


def test_control_unredacted_payload_exposes_every_canary():
    assert sorted(find_canaries(ALL_CANARIES, _payload())) == sorted(ALL_CANARIES)


def test_redact_value_removes_every_canary_and_does_not_mutate_input():
    payload = _payload()
    snapshot = copy.deepcopy(payload)
    redacted = redact_value(payload)
    assert find_canaries(ALL_CANARIES, redacted) == []
    assert payload == snapshot


def test_redact_value_keeps_non_sensitive_data_and_container_types():
    redacted = redact_value(_payload())
    assert redacted['model'] == 'gemini'
    assert redacted['max_tokens'] == 10
    assert isinstance(redacted['outer'][0]['inner'], tuple)
    assert redacted['outer'][0]['inner'][0]['Client_Secret'] == '[REDACTED]'
    assert redacted['headers'] == {'Authorization': '[REDACTED]'}
    assert isinstance(redacted['ids'], set)
    assert redacted['ids'] == {'[REDACTED]'}


def test_sensitive_key_names_match_acceptance_list():
    assert set(secret_redaction.SENSITIVE_KEYS) == {
        'password', 'secret', 'token', 'api_key', 'apikey', 'authorization', 'credential',
        'private_key', 'client_secret', 'refresh_token', 'access_token', 'session_uri', 'upload_session',
    }


@pytest.mark.parametrize('key', KEY_CASES)
def test_sensitive_keys_are_redacted_case_insensitively_at_any_depth(key):
    redacted = redact_value({'a': [{key: C_NESTED}]})
    assert redacted == {'a': [{key: '[REDACTED]'}]}
    assert find_canaries([C_NESTED], redacted) == []


def test_sensitive_key_with_none_stays_none():
    assert redact_value({'token': None}) == {'token': None}


@pytest.mark.parametrize('canary', [C_SK, C_AIZA, C_JWT, C_YA29])
def test_token_shaped_strings_are_redacted_in_free_text(canary):
    redacted = redact_value(f'upstream said {canary} twice')
    assert find_canaries([canary], redacted) == []
    assert redacted.startswith('upstream said ')


def test_token_patterns_do_not_touch_short_or_embedded_lookalikes():
    assert redact_value('sk-short') == 'sk-short'
    assert redact_value('task-abcdefghij') == 'task-abcdefghij'


def test_url_query_secrets_are_redacted_and_rest_of_url_is_kept():
    redacted = redact_value(URL)
    assert find_canaries(ALL_CANARIES, redacted) == []
    assert redacted.startswith('https://example.invalid/upload?')
    assert redacted.endswith('&keep=1')
    for name in ('upload_id', 'signature', 'token', 'key'):
        assert f'{name}=[REDACTED]' in redacted


def test_scalars_bytes_and_frozenset_are_handled():
    assert redact_value(5) == 5
    assert redact_value(None) is None
    assert redact_value(True) is True
    assert find_canaries([C_SK], redact_value(f'x {C_SK}'.encode())) == []
    result = redact_value(frozenset({C_SK}))
    assert isinstance(result, frozenset)
    assert result == frozenset({'[REDACTED]'})


def test_redaction_depth_overflow_fails_closed():
    deep = []
    for _ in range(100):
        deep = [deep]
    assert redact_value(deep) == '[REDACTED]'


class _BrokenStr(Exception):
    def __str__(self):
        raise RuntimeError(C_EXC)


def _boom(_text):
    raise RuntimeError(C_EXC)


def test_redact_exception_returns_class_name_and_redacted_message():
    exc = ValueError(
        f'rejected password={C_EXC} url=https://h.invalid/x?token={C_URL_TOKEN} Bearer {C_HEADER} {C_SK}'
    )
    text = redact_exception(exc)
    assert text.startswith('ValueError: rejected ')
    assert find_canaries([C_EXC, C_URL_TOKEN, C_HEADER, C_SK], text) == []


def test_redact_exception_without_message_returns_class_name_only():
    assert redact_exception(KeyError()) == 'KeyError'


def test_redact_exception_fails_closed_when_message_cannot_be_rendered():
    assert redact_exception(_BrokenStr()) == '[REDACTED]'


def test_redaction_failure_returns_redacted_never_original(monkeypatch):
    monkeypatch.setattr(secret_redaction, 'redact_text', _boom)
    assert redact_value(C_SK) == '[REDACTED]'
    assert redact_value({'a': [C_SK]}) == '[REDACTED]'
    assert redact_exception(ValueError(C_SK)) == '[REDACTED]'


def test_module_reuses_redact_text_from_redaction_module():
    assert secret_redaction.redact_text is redaction.redact_text


def test_find_canaries_checks_str_repr_and_json_of_outputs():
    class Odd:
        def __repr__(self):
            return f'Odd({C_EXC})'

        def __str__(self):
            return 'plain'

    assert find_canaries([C_EXC], Odd()) == [C_EXC]
    assert find_canaries([C_EXC], {'k': [C_EXC]}) == [C_EXC]
    assert find_canaries([C_EXC], C_EXC.encode()) == [C_EXC]
    assert find_canaries([C_EXC], 'clean', {'k': 1}) == []


def test_find_canaries_ignores_empty_dedupes_and_accepts_single_string():
    assert find_canaries('', 'abc') == []
    assert find_canaries([C_EXC, C_EXC, ''], C_EXC, 'x') == [C_EXC]
    assert find_canaries(C_EXC, 'x') == []
    assert find_canaries([C_NESTED, C_EXC], f'{C_EXC} {C_NESTED}') == [C_NESTED, C_EXC]
    assert find_canaries([C_EXC]) == []


@dataclasses.dataclass
class _Holder:
    name: str
    token: SecretValue


def test_secret_value_never_renders_value():
    secret = SecretValue(C_PASSWORD)
    assert repr(secret) == '[REDACTED]'
    assert str(secret) == '[REDACTED]'
    assert format(secret) == '[REDACTED]'
    assert format(secret, '>30') == '[REDACTED]'
    assert f'{secret}' == '[REDACTED]'
    assert f'{secret!r}' == '[REDACTED]'
    assert '%s|%r' % (secret, secret) == '[REDACTED]|[REDACTED]'


def test_reveal_returns_original_value():
    assert SecretValue(C_PASSWORD).reveal() == C_PASSWORD


def test_dataclass_repr_and_redact_value_do_not_leak_secret_value():
    holder = _Holder('x', SecretValue(C_PASSWORD))
    assert find_canaries([C_PASSWORD], repr(holder), str(holder), {'h': holder}) == []
    assert redact_value(SecretValue(C_PASSWORD)) == '[REDACTED]'
    assert find_canaries([C_PASSWORD], redact_value({'note': [SecretValue(C_PASSWORD)]})) == []


def test_secret_value_rejects_json_and_pickle():
    secret = SecretValue(C_PASSWORD)
    with pytest.raises(TypeError):
        json.dumps(secret)
    with pytest.raises(TypeError):
        json.dumps({'k': [secret]})
    for protocol in range(pickle.HIGHEST_PROTOCOL + 1):
        with pytest.raises(TypeError):
            pickle.dumps(secret, protocol)
    with pytest.raises(TypeError):
        pickle.dumps(_Holder('x', secret))


def test_secret_value_copy_returns_same_instance():
    secret = SecretValue(C_PASSWORD)
    assert copy.copy(secret) is secret
    assert copy.deepcopy(_Holder('x', secret)).token is secret
