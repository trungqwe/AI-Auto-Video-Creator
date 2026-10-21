"""SQL helpers shared by the PostgreSQL adapters."""
from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any

ConnectionProvider = Callable[[], Any]


def uuid_text(value: str, field: str = 'workspace_id') -> str:
    if not isinstance(value, str):
        raise ValueError(f'{field} must be a UUID')
    try:
        return str(uuid.UUID(value))
    except (ValueError, AttributeError, TypeError):
        raise ValueError(f'{field} must be a UUID') from None


def dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


@contextmanager
def savepoint(connection: Any) -> Iterator[None]:
    """Explicit SQL savepoint so unique constraint errors don't poison the UoW transaction.

    Never commits; doesn't use connection.transaction() which would commit the outer block.
    """
    connection.execute('SAVEPOINT persist_a_sp')
    try:
        yield
    except BaseException:
        connection.execute('ROLLBACK TO SAVEPOINT persist_a_sp')
        connection.execute('RELEASE SAVEPOINT persist_a_sp')
        raise
    else:
        connection.execute('RELEASE SAVEPOINT persist_a_sp')


def violated_constraint(exc: BaseException) -> str | None:
    diag = getattr(exc, 'diag', None)
    if diag is not None:
        return getattr(diag, 'constraint_name', None)
    return None
