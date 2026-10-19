"""OutputMetadata value object (CT-AI-009, capability D).

coveredIds: CT-AI-009

FilenameSanitizerPort is a TEMPORARY D-local port: the storage contract of capability I has no binding yet (CONV-D-07).
"""

from dataclasses import dataclass, replace
from typing import Protocol, runtime_checkable


class OutputMetadataError(ValueError):
    """Raised when OutputMetadata or its filename-safe representation violates CT-AI-009."""


OUTPUT_LANGUAGE = 'en'
MIN_HASHTAGS = 3
MAX_HASHTAGS = 4


def _validate_hashtag(tag: object) -> None:
    if not isinstance(tag, str) or len(tag) < 2 or not tag.startswith('#'):
        raise OutputMetadataError("hashtag must be a string starting with '#' followed by text")
    body = tag[1:]
    if '#' in body or any(ch.isspace() for ch in body):
        raise OutputMetadataError("hashtag must not contain whitespace or a second '#'")


@runtime_checkable
class FilenameSanitizerPort(Protocol):
    """Temporary D-local port for the storage-contract sanitizer of capability I; D defines no filename rule."""

    def sanitize(self, value: str) -> str: ...


@dataclass(frozen=True, slots=True)
class FilenameSafeRepresentation:
    """Filename-safe strings produced only by the sanitizer port."""

    title: str
    caption: str
    hashtags: tuple[str, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title:
            raise OutputMetadataError('filename-safe title must be a non-empty string')
        if not isinstance(self.caption, str) or not self.caption:
            raise OutputMetadataError('filename-safe caption must be a non-empty string')
        if not isinstance(self.hashtags, tuple) or not all(isinstance(tag, str) and tag for tag in self.hashtags):
            raise OutputMetadataError('filename-safe hashtags must be a tuple of non-empty strings')


@dataclass(frozen=True, slots=True)
class OutputMetadata:
    """Immutable CT-AI-009 output; title, caption and hashtags are the original display representation."""

    title: str
    caption: str
    hashtags: tuple[str, ...]
    language: str
    source_job_ref: str
    source_output_refs: tuple[str, ...]
    metadata_revision: int
    filename_safe: FilenameSafeRepresentation | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.title, str) or not self.title.strip():
            raise OutputMetadataError('title must be a non-empty string')
        if not isinstance(self.caption, str) or not self.caption.strip():
            raise OutputMetadataError('caption must be a non-empty string')
        if not isinstance(self.hashtags, tuple) or not MIN_HASHTAGS <= len(self.hashtags) <= MAX_HASHTAGS:
            raise OutputMetadataError(f'hashtags must be a tuple of {MIN_HASHTAGS} to {MAX_HASHTAGS} items')
        for tag in self.hashtags:
            _validate_hashtag(tag)
        if len({tag.casefold() for tag in self.hashtags}) != len(self.hashtags):
            raise OutputMetadataError('hashtags must be distinct ignoring case')
        if self.language != OUTPUT_LANGUAGE:
            raise OutputMetadataError(f'language must be {OUTPUT_LANGUAGE!r}')
        if not isinstance(self.source_job_ref, str) or not self.source_job_ref:
            raise OutputMetadataError('source_job_ref must be a non-empty string')
        if (
            not isinstance(self.source_output_refs, tuple)
            or not self.source_output_refs
            or not all(isinstance(ref, str) and ref for ref in self.source_output_refs)
        ):
            raise OutputMetadataError('source_output_refs must be a non-empty tuple of non-empty strings')
        if isinstance(self.metadata_revision, bool) or not isinstance(self.metadata_revision, int) or self.metadata_revision < 1:
            raise OutputMetadataError('metadata_revision must be a positive integer')
        if self.filename_safe is not None and not isinstance(self.filename_safe, FilenameSafeRepresentation):
            raise OutputMetadataError('filename_safe must be a FilenameSafeRepresentation or None')

    def with_filename_safe(self, sanitizer: FilenameSanitizerPort) -> 'OutputMetadata':
        """Return a copy whose filename-safe strings come only from the port; display fields stay untouched."""
        safe = FilenameSafeRepresentation(
            title=sanitizer.sanitize(self.title),
            caption=sanitizer.sanitize(self.caption),
            hashtags=tuple(sanitizer.sanitize(tag) for tag in self.hashtags),
        )
        return replace(self, filename_safe=safe)
