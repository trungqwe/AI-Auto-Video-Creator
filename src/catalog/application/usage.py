"""Record MediaUsage inside the completion unit of work owned by G (phần C của TST-WF-INV-010, TST-WF-INV-017).

The recorder only stages rows through ``repository_factory(uow)``; G owns commit and rollback.
"""

from collections.abc import Callable, Mapping

from catalog.ports.usage import MediaUsageRecord, MediaUsageRepository, UsageKind
from controlplane.domain.interfaces.uow import IUnitOfWork

MISSING_REQUIRED = "missing_required"
WRONG_TYPE = "wrong_type"
INVALID_VALUE = "invalid_value"
_OPTIONAL_FIELDS = ("rendition_ref", "artifact_version_ref", "selection_rationale")


class UsageContractError(ValueError):
    def __init__(self, code: str, field: str) -> None:
        super().__init__(f"{code}: {field}")
        self.code = code
        self.field = field


def _text(value: object, field: str) -> str:
    if not isinstance(value, str):
        raise UsageContractError(WRONG_TYPE, field)
    if not value:
        raise UsageContractError(INVALID_VALUE, field)
    return value


def _required(mapping: Mapping, key: str, field: str) -> object:
    if mapping.get(key) is None:
        raise UsageContractError(MISSING_REQUIRED, field)
    return mapping[key]


class MediaUsageRecorder:
    def __init__(self, repository_factory: Callable[[IUnitOfWork], MediaUsageRepository]) -> None:
        self._repository_factory = repository_factory

    def record_production_usage(self, uow: IUnitOfWork, completion_id: str, request: Mapping) -> int:
        """Stage one row per new manifest element; replay of the same completion_id returns 0."""
        records = self._parse(completion_id, request)
        repository = self._repository_factory(uow)
        added = 0
        for record in records:
            if not repository.exists(record.completion_id, record.media_asset_id, record.role, record.usage_kind):
                repository.add(record)
                added += 1
        return added

    def record_technical_usage(self, uow: IUnitOfWork, record: MediaUsageRecord) -> bool:
        """Stage one technical row; False when it already exists. Never counts as production."""
        if not isinstance(record, MediaUsageRecord):
            raise UsageContractError(WRONG_TYPE, "record")
        if record.usage_kind is not UsageKind.technical:
            raise UsageContractError(INVALID_VALUE, "usage_kind")
        repository = self._repository_factory(uow)
        if repository.exists(record.completion_id, record.media_asset_id, record.role, record.usage_kind):
            return False
        repository.add(record)
        return True

    @staticmethod
    def _parse(completion_id: object, request: object) -> list[MediaUsageRecord]:
        completion_id = _text(completion_id, "completion_id")
        if not isinstance(request, Mapping):
            raise UsageContractError(WRONG_TYPE, "request")
        video_job_id = _text(_required(request, "video_job_id", "video_job_id"), "video_job_id")
        manifest = _required(request, "media_usage_manifest", "media_usage_manifest")
        if not isinstance(manifest, (list, tuple)):
            raise UsageContractError(WRONG_TYPE, "media_usage_manifest")
        records = []
        for index, element in enumerate(manifest):
            prefix = f"media_usage_manifest[{index}]"
            if not isinstance(element, Mapping):
                raise UsageContractError(WRONG_TYPE, prefix)
            asset = _text(_required(element, "media_asset_id", f"{prefix}.media_asset_id"), f"{prefix}.media_asset_id")
            role = _text(_required(element, "role", f"{prefix}.role"), f"{prefix}.role")
            optional = {k: _text(element[k], f"{prefix}.{k}") for k in _OPTIONAL_FIELDS if element.get(k) is not None}
            records.append(MediaUsageRecord(completion_id, video_job_id, asset, role, UsageKind.production, **optional))
        return records
