"""PW-I1: MaterializeArtifactSet, ReconcileStorage và RequestCleanupEvaluation trên PostgreSQL thật, tệp trong tmp_path.

coveredIds: PW-I1-01, CT-STO-004, CT-STO-006, CT-STO-007
"""
from __future__ import annotations

import hashlib
import inspect
import uuid
from types import SimpleNamespace

import pytest

from controlplane.application.orchestration.workflows.activities import ActivityRejected
from controlplane.application.storage_meta.handlers import STAGED_HOOK_EXTENSIONS, materialize_artifact_set_handler, reconcile_storage_handler, register_staged_artifact, request_cleanup_evaluation_handler, verified_version_for_sha
from controlplane.application.storage_meta.materialization import RenderInputNotVerifiedError, release_for_render
from controlplane.application.storage_meta.reconciliation import CloudObjectObservation
from controlplane.domain.statemachine import ArtifactLocationState as S
from controlplane.infrastructure.db.storage_meta import PostgresStorageMetaRepository
from controlplane.infrastructure.db.uow import TransactionManager
from controlplane.infrastructure.production_ports.artifact_source import StagingArtifactSource

CLAIMS = SimpleNamespace(recovery_epoch='epoch-1')
STEPS = (S.MATERIALIZING, S.AVAILABLE_UNVERIFIED, S.VERIFYING, S.VERIFIED)


@pytest.fixture
def manager(pw_database):
    pool = TransactionManager(pw_database.dsn, pool_max_size=2)
    try:
        yield pool
    finally:
        pool.close()


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(root, name, data):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def request(refs, key='op-1'):
    return {'video_job_id': 'job-1', 'operation_key': key, 'input_refs': [{'ref_type': kind, 'ref_id': ref} for kind, ref in refs]}


def request_refs(refs, key='op-1'):
    return {'video_job_id': 'job-1', 'operation_key': key, 'input_refs': list(refs)}


def stage_image(manager, ws, root, data=b'image-bytes'):
    digest = sha(data)
    write(root, f'media/{digest}.png', data)
    version = register_staged_artifact(manager, workspace_id=ws, staging_root=root, owner_ref='job-1', relative_ref=f'media/{digest}.png', retention_ref='durable')
    return digest, version


def rows(db, sql, params=()):
    with db.connect() as conn:
        return conn.execute(sql, params).fetchall()


def count(db, table):
    return rows(db, f'SELECT count(*) FROM controlplane.{table}')[0][0]


def new_version(repo, ws, artifact_id, data=b'x', retention='per_video'):
    return repo.insert_version(str(uuid.uuid4()), {'workspace_id': ws, 'artifact_id': artifact_id, 'sha256_hash': sha(data), 'size_bytes': len(data), 'mime_type': 'audio/wav', 'artifact_kind': 'voice_track', 'owner_ref': 'job-1', 'retention_ref': retention, 'sensitivity_ref': 'internal'})


def new_location(repo, ws, version, backend='local-staging', namespace='staging', object_ref=None):
    ref = object_ref or version.artifact_version_id
    return repo.insert_location(str(uuid.uuid4()), {'workspace_id': ws, 'artifact_version_id': version.artifact_version_id, 'backend_ref': backend, 'provider_namespace_ref': namespace, 'provider_object_ref': ref, 'logical_locator': ref})


def walk(repo, location, target, evidence='ev', observed=None):
    done = STEPS.index(location.state) + 1 if location.state in STEPS else 0
    for step in STEPS[done:]:
        if location.state is target:
            break
        values = observed if step is S.VERIFIED and observed else (None, None)
        location = repo.update_location(location, location.revision, step, evidence, *values)
    return location


def test_update_location_writes_measured_observation_only_when_given(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        version = new_version(repo, ws, 'a', b'abc')
        location = walk(repo, new_location(repo, ws, version), S.VERIFYING)
        assert (location.observed_hash, location.observed_size_bytes) == (None, None)
        with pytest.raises(ValueError):
            repo.update_location(location, location.revision, S.VERIFIED, 'ev', 'NOT-A-HASH', 3)
        with pytest.raises(ValueError):
            repo.update_location(location, location.revision, S.VERIFIED, 'ev', sha(b'abc'), 0)
        verified = repo.update_location(location, location.revision, S.VERIFIED, 'ev', sha(b'abc'), 3)
        assert verified.state is S.VERIFIED and (verified.observed_hash, verified.observed_size_bytes) == (sha(b'abc'), 3)
        assert repo.get_location(ws, verified.location_id) == verified


def test_in_transaction_settles_through_the_pool_and_repository_has_no_commit(pw_database, manager):
    ws = pw_database.workspace_id
    with PostgresStorageMetaRepository.in_transaction(manager, ws) as repo:
        new_version(repo, ws, 'kept')
    with pytest.raises(RuntimeError, match='boom'):
        with PostgresStorageMetaRepository.in_transaction(manager, ws) as repo:
            new_version(repo, ws, 'dropped', b'y')
            raise RuntimeError('boom')
    assert rows(pw_database, 'SELECT artifact_id FROM controlplane.cp_artifact_versions') == [('kept',)]
    source = inspect.getsource(inspect.getmodule(PostgresStorageMetaRepository))
    assert '.commit(' not in source and '.rollback(' not in source


def test_release_for_render_rejects_a_location_without_observed_hash(pw_database):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        version = new_version(repo, ws, 'a', b'abc')
        location = walk(repo, new_location(repo, ws, version), S.VERIFIED)
    assert location.state is S.VERIFIED and location.observed_hash is None
    item = {'artifact_version_id': version.artifact_version_id, 'sha256': version.sha256_hash, 'size_bytes': version.size_bytes}
    with pytest.raises(RenderInputNotVerifiedError) as caught:
        release_for_render([item], {version.artifact_version_id: location})
    assert caught.value.reason == 'OBSERVATION_MISMATCH'


def test_materialize_registers_versions_and_verifies_flat_local_copies(pw_database, manager, tmp_path):
    ws = pw_database.workspace_id
    root = tmp_path / 'staging'
    write(root, 'voice/line.wav', b'voice-bytes')
    write(root, 'media/clip.mp4', b'video-bytes-longer')
    service = materialize_artifact_set_handler(manager, workspace_id=ws, staging_root=root)
    result = service(request([('artifact_source', 'voice/line.wav'), ('artifact_source', 'media/clip.mp4')]), CLAIMS)
    assert result['disposition'] == 'succeeded' and result['metrics']['artifact_count'] == 2
    manifest = result['metrics']['materialization_manifest']
    assert {item['sha256'] for item in manifest} == {sha(b'voice-bytes'), sha(b'video-bytes-longer')}
    assert not [path for path in root.iterdir() if path.name.endswith('.part')]
    locations, mimes, kinds = {}, set(), set()
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        for item in manifest:
            vid = item['artifact_version_id']
            assert ':' not in item['local_ref'] and item['local_ref'] == vid
            flat = root / vid
            assert flat.is_file() and sha(flat.read_bytes()) == item['sha256'] and flat.stat().st_size == item['size_bytes']
            with StagingArtifactSource(root).open(vid) as stream:
                assert sha(stream.read()) == item['sha256']
            version = repo.get_version(ws, vid)
            assert (version.sha256_hash, version.size_bytes, version.retention_ref) == (item['sha256'], item['size_bytes'], 'per_video')
            mimes.add(version.mime_type)
            kinds.add(version.artifact_kind)
            location = repo.find_location(ws, 'local-staging', 'staging', vid)
            assert location.state is S.VERIFIED and location.observed_hash == item['sha256'] and location.observed_size_bytes == item['size_bytes']
            locations[vid] = location
    assert mimes == {'audio/wav', 'video/mp4'} and kinds == {'voice_track', 'render_input_media'}
    inputs = [{'artifact_version_id': item['artifact_version_id'], 'sha256': item['sha256'], 'size_bytes': item['size_bytes']} for item in manifest]
    assert [loc.artifact_version_id for loc in release_for_render(inputs, locations)] == [item['artifact_version_id'] for item in manifest]


def test_materialize_replay_is_idempotent(pw_database, manager, tmp_path):
    root = tmp_path / 'staging'
    write(root, 'voice/line.wav', b'voice-bytes')
    service = materialize_artifact_set_handler(manager, workspace_id=pw_database.workspace_id, staging_root=root)
    first = service(request([('artifact_source', 'voice/line.wav')]), CLAIMS)
    second = service(request([('artifact_source', 'voice/line.wav')], key='op-2'), CLAIMS)
    assert second['disposition'] == 'succeeded' and second['metrics']['materialization_manifest'] == first['metrics']['materialization_manifest']
    assert count(pw_database, 'cp_artifact_versions') == 1 and count(pw_database, 'cp_artifact_locations') == 1


def test_materialize_waits_with_artifact_not_ready_for_missing_source(pw_database, manager, tmp_path):
    root = tmp_path / 'staging'
    service = materialize_artifact_set_handler(manager, workspace_id=pw_database.workspace_id, staging_root=root)
    result = service(request([('artifact_source', 'voice/none.wav')]), CLAIMS)
    assert result['disposition'] == 'waiting' and result['problem']['code'] == 'artifact_not_ready' and result['output_refs'] == []
    assert count(pw_database, 'cp_artifact_versions') == 0 and list(root.iterdir()) == []
    unknown = service(request([('artifact_version', str(uuid.uuid4()))]), CLAIMS)
    assert unknown['disposition'] == 'waiting' and unknown['problem']['code'] == 'artifact_not_ready'
    with pytest.raises(ActivityRejected):
        service(request([('artifact_source', '../outside.wav')]), CLAIMS)


def test_materialize_rejects_a_file_changed_after_registration(pw_database, manager, tmp_path):
    ws = pw_database.workspace_id
    root = tmp_path / 'staging'
    write(root, 'voice/line.wav', b'voice-bytes')
    service = materialize_artifact_set_handler(manager, workspace_id=ws, staging_root=root)
    item = service(request([('artifact_source', 'voice/line.wav')]), CLAIMS)['metrics']['materialization_manifest'][0]
    vid = item['artifact_version_id']
    (root / vid).write_bytes(b'tampered-content')
    again = service(request([('artifact_version', vid)], key='op-2'), CLAIMS)
    assert again['disposition'] == 'waiting' and again['problem']['code'] == 'artifact_not_ready' and again['output_refs'] == []
    with pw_database.connect() as conn:
        location = PostgresStorageMetaRepository(conn, ws).find_location(ws, 'local-staging', 'staging', vid)
    assert location.state is S.VERIFIED and location.observed_hash == item['sha256']
    claimed = {'artifact_version_id': vid, 'sha256': sha(b'tampered-content'), 'size_bytes': len(b'tampered-content')}
    with pytest.raises(RenderInputNotVerifiedError) as caught:
        release_for_render([claimed], {vid: location})
    assert caught.value.reason == 'OBSERVATION_MISMATCH'


def test_reconcile_storage_reports_mismatched_and_missing_cloud_locations(pw_database, manager):
    ws = pw_database.workspace_id
    ids, versions = {}, {}
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        for ref, data in (('obj-good', b'good'), ('obj-bad', b'bad'), ('obj-gone', b'gone')):
            version = new_version(repo, ws, ref, data)
            versions[ref] = version
            location = new_location(repo, ws, version, backend='cloud', namespace='drive', object_ref=ref)
            ids[ref] = walk(repo, location, S.VERIFIED, 'cloud-ev', (version.sha256_hash, version.size_bytes)).location_id
    good, bad, gone = versions['obj-good'], versions['obj-bad'], versions['obj-gone']
    seen = {'obj-good': CloudObjectObservation('obj-good', good.sha256_hash, good.size_bytes), 'obj-bad': CloudObjectObservation('obj-bad', sha(b'other'), bad.size_bytes)}
    result = reconcile_storage_handler(manager, workspace_id=ws, observe=seen.get)(request([]), CLAIMS)
    metrics = result['metrics']
    assert result['disposition'] == 'succeeded' and metrics['checked_locations'] == 3 and metrics['finding_count'] == 2
    assert {(item['code'], item['ref']) for item in metrics['findings']} == {('HASH_MISMATCH', ids['obj-bad']), ('CLOUD_OBJECT_MISSING', ids['obj-gone'])}
    assert len(result['warnings']) == 2
    seen['obj-bad'] = CloudObjectObservation('obj-bad', bad.sha256_hash, bad.size_bytes)
    seen['obj-gone'] = CloudObjectObservation('obj-gone', gone.sha256_hash, gone.size_bytes)
    clean = reconcile_storage_handler(manager, workspace_id=ws, observe=seen.get)(request([]), CLAIMS)
    assert clean['metrics']['finding_count'] == 0 and 'warnings' not in clean
    with pytest.raises(ActivityRejected):
        reconcile_storage_handler(manager, workspace_id=ws, observe=seen.get)(request([]), None)


def test_cleanup_evaluation_never_grants_without_a_verified_cloud_copy(pw_database, manager):
    ws = pw_database.workspace_id
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        durable = new_version(repo, ws, 'durable-out', b'durable', 'durable')
        digest = (durable.sha256_hash, durable.size_bytes)
        local = walk(repo, new_location(repo, ws, durable), S.VERIFIED, observed=digest)
        cloud = new_location(repo, ws, durable, backend='cloud', namespace='drive', object_ref='obj-cloud')
        unverified = new_location(repo, ws, new_version(repo, ws, 'clip', b'clip'))
        conn.execute("INSERT INTO controlplane.cp_app_sessions (workspace_id, session_ref, status, recovery_epoch, started_at) VALUES (%s, 'session-1', 'ACTIVE', 'epoch-1', CURRENT_TIMESTAMP)", (ws,))
    service = request_cleanup_evaluation_handler(manager, workspace_id=ws)

    def evaluate(location, epoch='epoch-1', extra=()):
        result = service(request([('artifact_location', location.location_id), *extra]), SimpleNamespace(recovery_epoch=epoch))
        assert result['disposition'] == 'succeeded' and result['metrics']['authorization_issued'] is False
        return result['metrics']['decision'], result['metrics']['reason_codes']

    done = [('video_completion', 'completion-1')]
    assert evaluate(local) == ('forbidden', ['DURABLE_COPY_NOT_VERIFIED'])
    assert evaluate(local, extra=done) == ('forbidden', ['DURABLE_COPY_NOT_VERIFIED'])
    with pw_database.connect() as conn:
        walk(PostgresStorageMetaRepository(conn, ws), cloud, S.VERIFIED, 'cloud-ev', digest)
    assert evaluate(local) == ('deferred', ['NO_COMPLETION_EVIDENCE'])
    assert evaluate(local, extra=done) == ('eligible', [])
    assert evaluate(local, epoch='epoch-0', extra=done) == ('forbidden', ['STALE_RECOVERY_EPOCH'])
    assert evaluate(unverified) == ('forbidden', ['LOCATION_NOT_VERIFIED'])
    assert count(pw_database, 'cp_cleanup_authorizations') == 0
    assert rows(pw_database, 'SELECT state FROM controlplane.cp_artifact_locations WHERE location_id = %s', (local.location_id,)) == [('VERIFIED',)]


def test_register_staged_artifact_places_a_verified_durable_image(pw_database, manager, tmp_path):
    ws = pw_database.workspace_id
    root = tmp_path / 'staging'
    digest, version = stage_image(manager, ws, root)
    assert version.artifact_id == f'media/{digest}.png' and version.retention_ref == 'durable'
    assert (version.mime_type, version.artifact_kind, version.sha256_hash) == ('image/png', 'render_input_media', digest)
    flat = root / version.artifact_version_id
    assert flat.is_file() and sha(flat.read_bytes()) == digest
    with pw_database.connect() as conn:
        location = PostgresStorageMetaRepository(conn, ws).find_location(ws, 'local-staging', 'staging', version.artifact_version_id)
    assert location.state is S.VERIFIED and (location.observed_hash, location.observed_size_bytes) == (digest, len(b'image-bytes'))
    found = verified_version_for_sha(manager, workspace_id=ws, sha256=digest)
    assert found is not None and found.artifact_version_id == version.artifact_version_id
    _, again = stage_image(manager, ws, root)
    assert again.artifact_version_id == version.artifact_version_id
    assert count(pw_database, 'cp_artifact_versions') == 1 and count(pw_database, 'cp_artifact_locations') == 1
    assert verified_version_for_sha(manager, workspace_id=ws, sha256=sha(b'other')) is None
    write(root, 'media/UPPER.PNG', b'upper')
    with pytest.raises(ActivityRejected):
        register_staged_artifact(manager, workspace_id=ws, staging_root=root, owner_ref='job-1', relative_ref='media/UPPER.PNG', retention_ref='durable')
    assert count(pw_database, 'cp_artifact_versions') == 1


def test_verified_version_for_sha_requires_a_verified_local_location(pw_database, manager):
    ws = pw_database.workspace_id
    data = b'jpeg-bytes'
    digest = sha(data)
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        version = new_version(repo, ws, f'media/{digest}.jpg', data)
        location = new_location(repo, ws, version)
    assert verified_version_for_sha(manager, workspace_id=ws, sha256=digest) is None
    with pw_database.connect() as conn:
        walk(PostgresStorageMetaRepository(conn, ws), location, S.VERIFIED, observed=(digest, len(data)))
    found = verified_version_for_sha(manager, workspace_id=ws, sha256=digest)
    assert found is not None and found.artifact_version_id == version.artifact_version_id
    assert verified_version_for_sha(manager, workspace_id=ws, sha256='NOT-A-HASH') is None


def test_materialize_derives_inputs_from_voice_and_selected_media_refs(pw_database, manager, tmp_path):
    ws = pw_database.workspace_id
    root = tmp_path / 'staging'
    voice = b'voice-wav-bytes'
    vdigest = sha(voice)
    voice_name = f'voice-artifact-{vdigest}'
    write(root, f'voice/{voice_name}', voice)
    idigest, image = stage_image(manager, ws, root)
    service = materialize_artifact_set_handler(manager, workspace_id=ws, staging_root=root)
    refs = [{'ref_type': 'voice_artifact', 'ref_id': voice_name}, {'ref_type': 'selected_media', 'ref_id': 'asset-1', 'revision_id': image.artifact_version_id}]
    result = service(request_refs(refs), CLAIMS)
    assert result['disposition'] == 'succeeded' and result['metrics']['artifact_count'] == 2
    manifest = result['metrics']['materialization_manifest']
    assert {item['sha256'] for item in manifest} == {vdigest, idigest}
    assert all(set(item) == {'artifact_version_id', 'local_ref', 'sha256', 'size_bytes'} for item in manifest)
    assert result['output_refs'][0] == {'ref_type': 'artifact_set', 'ref_id': 'op-1'} and len(result['output_refs']) == 3
    linked = {ref['ref_id']: ref['source_ref_id'] for ref in result['output_refs'][1:] if ref['ref_type'] == 'artifact_version'}
    assert sorted(linked.values()) == sorted([f'voice/{voice_name}', f'media/{idigest}.png'])
    assert linked[image.artifact_version_id] == f'media/{idigest}.png'
    voice_id = next(vid for vid, source in linked.items() if source == f'voice/{voice_name}')
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        voice_version = repo.get_version(ws, voice_id)
        image_version = repo.get_version(ws, image.artifact_version_id)
    assert (voice_version.mime_type, voice_version.artifact_kind, voice_version.retention_ref) == ('audio/wav', 'voice_track', 'per_video')
    assert image_version.retention_ref == 'durable'
    again = service(request_refs(refs, key='op-2'), CLAIMS)
    assert again['disposition'] == 'succeeded' and again['metrics']['materialization_manifest'] == manifest
    assert count(pw_database, 'cp_artifact_versions') == 2


def test_materialize_keeps_explicit_refs_and_rejects_unusable_derived_inputs(pw_database, manager, tmp_path):
    ws = pw_database.workspace_id
    root = tmp_path / 'staging'
    _, image = stage_image(manager, ws, root)
    service = materialize_artifact_set_handler(manager, workspace_id=ws, staging_root=root)
    explicit = service(request_refs([{'ref_type': 'artifact_version', 'ref_id': image.artifact_version_id}, {'ref_type': 'voice_artifact', 'ref_id': 'voice-artifact-ignored'}]), CLAIMS)
    assert explicit['disposition'] == 'succeeded' and explicit['metrics']['artifact_count'] == 1
    assert count(pw_database, 'cp_artifact_versions') == 1
    nothing = service(request_refs([{'ref_type': 'script', 'ref_id': 's-1'}]), CLAIMS)
    assert nothing['disposition'] == 'failed' and nothing['problem']['code'] == 'MATERIALIZE_INPUT_MISSING'
    missing = service(request_refs([{'ref_type': 'voice_artifact', 'ref_id': 'voice-artifact-missing'}]), CLAIMS)
    assert missing['disposition'] == 'waiting' and missing['problem']['code'] == 'artifact_not_ready'
    with pytest.raises(ActivityRejected):
        service(request_refs([{'ref_type': 'selected_media', 'ref_id': 'asset-1'}]), CLAIMS)
    with pytest.raises(ActivityRejected):
        service(request_refs([{'ref_type': 'selected_media', 'ref_id': 'asset-1', 'revision_id': 'not-a-uuid'}]), CLAIMS)
    write(root, 'media/nosuffix', b'x')
    with pytest.raises(ActivityRejected):
        service(request([('artifact_source', 'media/nosuffix')]), CLAIMS)
    assert count(pw_database, 'cp_artifact_versions') == 1


def test_verified_version_for_sha_resolves_staged_hook_media_by_extension(pw_database, manager, tmp_path):
    ws = pw_database.workspace_id
    root = tmp_path / 'staging'
    video = b'hook-video-bytes'
    vdigest = sha(video)
    write(root, f'media/{vdigest}.mp4', video)
    mp4 = register_staged_artifact(manager, workspace_id=ws, staging_root=root, owner_ref='job-1', relative_ref=f'media/{vdigest}.mp4', retention_ref='durable')
    assert mp4.artifact_id == f'media/{vdigest}.mp4'
    found_video = verified_version_for_sha(manager, workspace_id=ws, sha256=vdigest, extensions=STAGED_HOOK_EXTENSIONS)
    assert found_video is not None and found_video.artifact_version_id == mp4.artifact_version_id
    assert verified_version_for_sha(manager, workspace_id=ws, sha256=vdigest) is None
    audio = b'hook-audio-bytes'
    adigest = sha(audio)
    write(root, f'media/{adigest}.wav', audio)
    wav = register_staged_artifact(manager, workspace_id=ws, staging_root=root, owner_ref='job-1', relative_ref=f'media/{adigest}.wav', retention_ref='durable')
    found_audio = verified_version_for_sha(manager, workspace_id=ws, sha256=adigest, extensions=STAGED_HOOK_EXTENSIONS)
    assert found_audio is not None and found_audio.artifact_version_id == wav.artifact_version_id
    assert verified_version_for_sha(manager, workspace_id=ws, sha256=adigest) is None
    pdigest, png = stage_image(manager, ws, root)
    found_image = verified_version_for_sha(manager, workspace_id=ws, sha256=pdigest)
    assert found_image is not None and found_image.artifact_version_id == png.artifact_version_id
    assert verified_version_for_sha(manager, workspace_id=ws, sha256=pdigest, extensions=STAGED_HOOK_EXTENSIONS) is None
    udata = b'unverified-clip'
    udigest = sha(udata)
    with pw_database.connect() as conn:
        repo = PostgresStorageMetaRepository(conn, ws)
        version = new_version(repo, ws, f'media/{udigest}.mp4', udata)
        new_location(repo, ws, version)
    assert verified_version_for_sha(manager, workspace_id=ws, sha256=udigest, extensions=STAGED_HOOK_EXTENSIONS) is None
