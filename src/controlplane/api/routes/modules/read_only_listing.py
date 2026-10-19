"""Router liệt kê chỉ đọc cho route module (H-08, CT-API-001, CT-API-002, CT-API-010).

workspace_id luôn lấy từ request.state.identity, không bao giờ từ query. Router chỉ có GET và không đọc body.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Mapping, Sequence
from typing import Any

from fastapi import APIRouter, Request

from controlplane.api.routes.modules.problem_detail import problem_response
from controlplane.application.projections.list_query import ListQueryError, Page, parse_list_query

VERSION_PREFIX = '/v1/'


def build_listing_router(*, prefix: str, fetch_page: Callable[[Request, str, Any], Page], allowed_sorts: Sequence[str], allowed_filters: Collection[str], default_limit: int, max_limit: int, fetch_one: Callable[[Request, str, str], Mapping[str, object] | None] | None = None) -> APIRouter:
    if not isinstance(prefix, str) or not prefix.startswith(VERSION_PREFIX):
        raise ValueError('prefix_must_be_versioned')
    limits = {'allowed_sorts': allowed_sorts, 'allowed_filters': allowed_filters, 'default_limit': default_limit, 'max_limit': max_limit}
    parse_list_query({}, **limits)
    router = APIRouter()

    def list_items(request: Request) -> Any:
        workspace_id = request.state.identity['workspace_id']
        try:
            query = parse_list_query(dict(request.query_params), **limits)
        except ListQueryError as exc:
            return problem_response(request, 'VALIDATION_FAILED', field_errors={exc.field: exc.code})
        page = fetch_page(request, workspace_id, query)
        return {'items': list(page.items), 'next_cursor': page.next_cursor}

    router.add_api_route(prefix, list_items, methods=['GET'], response_model=None)
    if fetch_one is not None:

        def get_item(request: Request, item_id: str) -> Any:
            workspace_id = request.state.identity['workspace_id']
            item = fetch_one(request, workspace_id, item_id)
            if item is None:
                return problem_response(request, 'NOT_FOUND')
            return dict(item)

        router.add_api_route(prefix + '/{item_id}', get_item, methods=['GET'], response_model=None)
    return router