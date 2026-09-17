"""Mounted SSE route with an explicit missing framing capability."""

from fastapi import APIRouter, Request

router = APIRouter()


class SseStreamPresenter:
    def frames(self, *, workspace_id: str, connection: object) -> object:
        raise NotImplementedError("P7B_SSE_FRAMING_NOT_IMPLEMENTED")


@router.get("/v1/operations/stream")
def stream(request: Request) -> object:
    identity = request.state.identity
    with request.app.state.manager.borrow_connection() as connection:
        return request.app.state.sse_presenter.frames(
            workspace_id=identity["workspace_id"], connection=connection,
        )
