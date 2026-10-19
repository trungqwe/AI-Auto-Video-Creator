# B?o c?o b?ng ch?ng I-03

## M?i tr??ng

- Interpreter kho?: `C:/Users/Admin/orca/workspaces/AI-Auto-Video-Creator/DAG-implement-plan/.local-tools/temp/m2-controlplane-locked-venv-31315/Scripts/python.exe`
- Baseline: `4f956426cf8a28182acd5cba47ceebe368f9908f`
- Ngu?n quy?n: IMPL-PLAN-I Auditor PASS, slice I-03 trong `docs/implementation/i/slices.md`, binding `docs/parallel-delivery/bindings/i-artifact-version.json`.

## RED

- L?nh th?c thi: `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` (ch?y v?i stub ? b??c 1)
- Exit code th?c t?: 1
- D?ng t?m t?t nguy?n v?n: `81 failed, 8 passed, 7 subtests passed in 0.32s`
- Chi ti?t c?c test FAILED/SUBFAILED k?m th?ng ?i?p AssertionError nguy?n v?n:
  - `SUBFAILED(expected_sha256=None) tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_sha256='') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_sha256='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_sha256='aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_size_bytes=None) tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_size_bytes=-1) tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_size_bytes=True) tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(expected_size_bytes='1') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_invalid_expected_values_raise_value_error`: `AssertionError: ValueError not raised`
  - `SUBFAILED(missing='observed_sha256') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_only_all_four_signals_verify`: `AssertionError: unexpectedly identical: <ArtifactLocationState.VERIFIED: 'VERIFIED'>`
  - `SUBFAILED(missing='observed_size_bytes') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_only_all_four_signals_verify`: `AssertionError: unexpectedly identical: <ArtifactLocationState.VERIFIED: 'VERIFIED'>`
  - `SUBFAILED(missing='evidence_ref') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_only_all_four_signals_verify`: `AssertionError: unexpectedly identical: <ArtifactLocationState.VERIFIED: 'VERIFIED'>`
  - `FAILED tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_only_all_four_signals_verify`: `AssertionError: unexpectedly identical: <ArtifactLocationState.VERIFIED: 'VERIFIED'>`
  - `SUBFAILED(case='size match only, no hash') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='hash mismatch') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.CORRUPT: 'CORRUPT'>`
  - `SUBFAILED(case='size mismatch') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.CORRUPT: 'CORRUPT'>`
  - `SUBFAILED(case='object absent') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.MISSING: 'MISSING'>`
  - `SUBFAILED(case='object absent with full fields') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.MISSING: 'MISSING'>`
  - `SUBFAILED(case='presence unknown') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='presence truthy non-bool') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='evidence None') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='evidence empty') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='evidence blank') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='size missing') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='hash uppercase is not valid evidence') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='hash malformed') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='size is bool') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `SUBFAILED(case='size negative') tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_table`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `FAILED tests/unit/storage/test_storage_verification.py::EvaluateIntegrityTests::test_upload_response_without_hash_is_never_verified`: `AssertionError: <ArtifactLocationState.VERIFIED: 'VERIFIED'> is not <ArtifactLocationState.OUTCOME_UNKNOWN: 'OUTCOME_UNKNOWN'>`
  - `ApplyIntegrityOutcomeTests::test_edge_table_has_no_recovery_edge`: 39 subtest FAILED v?i `AssertionError: ForbiddenTransitionError not raised` cho c?c chuy?n ??i kh?ng h?p l? t? state hi?n t?i sang outcome.
  - `ApplyIntegrityOutcomeTests::test_evaluated_outcome_flows_into_transition`: 3 subtest FAILED v?i `AssertionError` khi ki?m tra k?t qu? tr? v? kh?p outcome ??nh gi? ???c.
  - `FAILED tests/unit/storage/test_storage_verification.py::ApplyIntegrityOutcomeTests::test_expected_revision_equals_current_revision`: `AssertionError: expected call not found` (spy ch?a ???c g?i trong stub).
  - `ApplyIntegrityOutcomeTests::test_non_integrity_outcome_is_rejected`: 7 subtest FAILED v?i `AssertionError: ValueError not raised` khi truy?n state ngo?i b? outcome integrity.
  - `ApplyIntegrityOutcomeTests::test_recovery_edges_to_verified_are_forbidden`: 3 subtest FAILED v?i `AssertionError: ForbiddenTransitionError not raised` khi chuy?n t? MISSING, CORRUPT ho?c OUTCOME_UNKNOWN sang VERIFIED.
- X?c nh?n: To?n b? l?i FAILED/SUBFAILED ??u l? AssertionError t? stub; ho?n to?n kh?ng c? ImportError, ModuleNotFoundError, NameError, TypeError, AttributeError hay l?i collection (c?c test frozen contract fields, transition verifying->verified h?p l? v? case full match PASS).

## GREEN

- L?nh th?c thi: `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider`
- Exit code th?c t?: 0
- D?ng t?m t?t nguy?n v?n: `11 passed, 85 subtests passed in 0.05s`

## Thay ??i

- `src/controlplane/domain/storage_meta/verification.py`: ??nh ngh?a dataclass frozen `IntegrityObservation` (v?i 4 tr??ng `object_present: bool | None`, `observed_sha256: str | None`, `observed_size_bytes: int | None`, `evidence_ref: str | None`), h?m `evaluate_integrity(expected_sha256, expected_size_bytes, observation) -> ArtifactLocationState` (ki?m tra hex th??ng 64 k? t?, size kh?ng ?m; `object_present is False` ? `MISSING`; `object_present` kh?c True, thi?u/r?ng `evidence_ref`, thi?u ho?c sai ??nh d?ng hash/size ? `OUTCOME_UNKNOWN`; l?ch hash ho?c size ? `CORRUPT`; kh?p ?? ? `VERIFIED`), v? h?m `apply_integrity_outcome(current_state, current_revision, outcome) -> TransitionResult` (g?i `transition_artifact_location` v?i `expected_revision=current_revision`, t? ch?i outcome ngo?i b? 4 outcome integrity; kh?ng th?m recovery edge n?o).
- `tests/unit/storage/test_storage_verification.py`: B? ki?m th? ??n v? d?ng b?ng g?m 2 l?p test: `EvaluateIntegrityTests` (`test_table` v?i 16 case bao qu?t, `test_only_all_four_signals_verify`, `test_upload_response_without_hash_is_never_verified` lo?i tr? ph?n v? d? response 200 thi?u hash, `test_observation_is_frozen_with_contract_fields`, `test_invalid_expected_values_raise_value_error`) v? `ApplyIntegrityOutcomeTests` (`test_recovery_edges_to_verified_are_forbidden` lo?i tr? ph?n v? d? recovery t? MISSING/CORRUPT/OUTCOME_UNKNOWN sang VERIFIED, `test_verifying_to_verified_is_admitted`, `test_edge_table_has_no_recovery_edge` ki?m tra ma tr?n m?i state ? outcome, `test_expected_revision_equals_current_revision` spy ki?m tra expected_revision, `test_non_integrity_outcome_is_rejected`, `test_evaluated_outcome_flows_into_transition`).

## L?nh ki?m

| # | L?nh | Exit code | K?t qu? |
|---|---|---|---|
| 1 | `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` (RED) | 1 | 81 failed, 8 passed, 7 subtests passed in 0.32s |
| 2 | `python -m pytest tests/unit/storage/test_storage_verification.py -q -p no:cacheprovider` (GREEN) | 0 | 11 passed, 85 subtests passed in 0.05s |
| 3 | `git diff --check` | 0 | PASS (kh?ng output, kh?ng trailing whitespace, kh?ng l?i ??nh d?ng diff) |
| 4 | `python -c "import pathlib; fs=['src/controlplane/domain/storage_meta/verification.py','tests/unit/storage/test_storage_verification.py','docs/delivery-evidence/i-03/report.md']; data={f: pathlib.Path(f).read_bytes() for f in fs}; bad=[(f,i) for f in fs for i,l in enumerate(data[f].decode('utf-8').split('
'),1) if l.rstrip('')!=l.rstrip()]; assert not bad, bad; assert all(d.endswith(b'
') and not d.startswith(b'ï»¿') for d in data.values()); print('OK')"` | 0 | OK (UTF-8 kh?ng BOM, kh?ng trailing whitespace, k?t th?c LF) |

Ghi ch?: `src/controlplane/domain/statemachine/**` v? `src/controlplane/domain/storage_meta/__init__.py` kh?ng b? s?a (ch? import ??c t? `controlplane.domain.statemachine`).

## Quy?t ??nh m?c ??nh (D8)

1. GI? ??NH: Th? t? ??nh gi?: `object_present is False` ? `MISSING`; `None` ho?c kh?ng ph?i bool ? `OUTCOME_UNKNOWN`; r?i thi?u/r?ng `evidence_ref` ? `OUTCOME_UNKNOWN`; hash ho?c size quan s?t thi?u ho?c sai ??nh d?ng ? `OUTCOME_UNKNOWN`; hash ho?c size l?ch ? `CORRUPT`; c?n l?i `VERIFIED`.
2. GI? ??NH: Hash quan s?t vi?t hoa ho?c sai ??nh d?ng kh?ng ph?i b?ng ch?ng h?p l? n?n `OUTCOME_UNKNOWN`, kh?ng ph?i `CORRUPT`.
3. GI? ??NH: `expected_sha256` ho?c `expected_size_bytes` sai ??nh d?ng raise `ValueError`.
4. GI? ??NH: `apply_integrity_outcome` raise `ValueError` n?u `outcome` ngo?i `{VERIFIED, CORRUPT, MISSING, OUTCOME_UNKNOWN}`.
5. GI? ??NH: `object_present is False` tr? `MISSING` b?t k? c?c tr??ng kh?c.

## Danh s?ch ch? user (pendingUserCheckpoint)

- PUC-I-01 ? ROADMAP-OPEN-010: th?i h?n retention (original, reusable, temporary, output, log v? evidence) v? placement/quota th?t c?a b?n t?i kho?n Drive. H?n: tr??c unattended cleanup.
- PUC-I-02 ? ROADMAP-OPEN-004: m?i gi? production d?ng cho t?n folder `YY-MM-DD`. H?n: tr??c khi b?t l?ch production.
- PUC-I-03 ? Ng??ng byte c?a working set v? disk reserve tr?n m?y m?c ti?u (?o ? CP7-I-03). H?n: tr??c khi nghi?m thu hi?u n?ng render.
- PUC-I-04 ? User duy?t C-I v? `R2 Media Alpha` (EG-M4-I-6).
- PUC-I-05 ? D5 cho CP7 (t?i kho?n Drive th?t) v? USER-CKPT-D9-D10 tr??c CP-2b.
- PUC-I-06 ? ROADMAP-OPEN-012: ph?m vi backup/restore (G05). H?n: tr??c khi b?t writer/cleanup sau restore.
(Kh?ng m?c n?o ???c coi l? ?? duy?t.)

## Gi?i h?n

- Kh?ng ch?y full suite; kh?ng ch?y tests/m1, tests/m2.
- Kh?ng s?a statemachine, fixture, migration, pyproject.toml, lockfile.
- Kh?ng th?m th? vi?n ngo?i stdlib.
- Kh?ng g?i d?ch v? th?t.
- Kh?ng t?o conftest.py hay __init__.py trong tests/.
- Module `src/controlplane/domain/storage_meta/verification.py` kh?ng th?m recovery edge n?o t? MISSING, CORRUPT ho?c OUTCOME_UNKNOWN sang VERIFIED.
- Kh?ng s?a `src/controlplane/domain/statemachine/**` hay `src/controlplane/domain/storage_meta/__init__.py`.
