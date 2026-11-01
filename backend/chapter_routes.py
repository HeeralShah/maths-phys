from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from .chapter_editions import ChapterRepository
from .contracts.chapter_v2 import ChapterPackage, CheckInV2
from .store import Store


class ScopeIn(BaseModel):
    scope_kind: str
    title: str
    ordinal: int = Field(ge=0)
    start_locator: dict
    end_locator: dict
    detection_method: str = "learner_confirmed"
    parent_scope_id: str | None = None


def build_router(store: Store) -> APIRouter:
    router = APIRouter(tags=["chapter-editions-v2"])
    repository = ChapterRepository(store)

    @router.post("/sources/{source_id}/scopes", status_code=201)
    def create_scope(source_id: str, body: ScopeIn):
        try:
            return repository.create_scope(source_id, body.scope_kind, body.title, body.ordinal,
                                           body.start_locator, body.end_locator, body.detection_method,
                                           body.parent_scope_id)
        except KeyError as error:
            raise HTTPException(404, str(error))
        except ValueError as error:
            raise HTTPException(400, str(error))

    @router.get("/sources/{source_id}/scopes")
    def list_scopes(source_id: str):
        try:
            return repository.list_scopes(source_id)
        except KeyError as error:
            raise HTTPException(404, str(error))

    @router.post("/source-scopes/{scope_id}/editions/publish", status_code=201)
    def publish_chapter(scope_id: str, body: ChapterPackage):
        try:
            return repository.publish(scope_id, body)
        except KeyError as error:
            raise HTTPException(404, str(error))
        except ValueError as error:
            raise HTTPException(409, str(error))

    @router.get("/source-scopes/{scope_id}/editions/latest")
    def latest_chapter(scope_id: str):
        try:
            result = repository.latest(scope_id)
        except KeyError as error:
            raise HTTPException(404, str(error))
        if not result:
            raise HTTPException(404, "complete chapter edition not found")
        return result

    @router.get("/chapter-editions/{edition_id}")
    def read_chapter(edition_id: str):
        result = repository.get_edition(edition_id)
        if not result:
            raise HTTPException(404, "chapter edition not found")
        return result

    @router.post("/checkable-items/{item_id}/checks", status_code=201)
    def record_check(item_id: str, body: CheckInV2):
        try:
            return repository.record_check(item_id, body.understood, body.reconfirmation_reason,
                                           body.carried_from_check_id)
        except KeyError as error:
            raise HTTPException(404, str(error))
        except ValueError as error:
            raise HTTPException(409, str(error))

    return router

