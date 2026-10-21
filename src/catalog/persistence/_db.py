'''Helpers over the connection owned by the caller; adapters never open, commit or roll back.'''

import uuid
from typing import Any

from psycopg.rows import tuple_row


def workspace_uuid(workspace_id: str) -> uuid.UUID:
    return uuid.UUID(str(workspace_id))


def fetch_all(connection: Any, sql: str, params: tuple = ()) -> list[tuple]:
    with connection.cursor(row_factory=tuple_row) as cursor:
        cursor.execute(sql, params)
        return cursor.fetchall()


def fetch_one(connection: Any, sql: str, params: tuple = ()) -> tuple | None:
    rows = fetch_all(connection, sql, params)
    return rows[0] if rows else None


def run(connection: Any, sql: str, params: tuple = ()) -> None:
    with connection.cursor() as cursor:
        cursor.execute(sql, params)


def search_terms(text: str) -> list[str]:
    '''Lowercase alphanumeric words of text without duplicates; the same split builds search_text and queries.'''
    words = ''.join(char if char.isalnum() else ' ' for char in text.lower()).split()
    return list(dict.fromkeys(words))


def build_search_text(*texts: str) -> str:
    return ' '.join(search_terms(' '.join(texts)))
