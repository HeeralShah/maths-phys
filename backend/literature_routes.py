from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .contracts.literature_v2 import LiteratureMapPackage
from .literature import LiteratureRepository
from .store import Store


def build_router(store: Store) -> APIRouter:
    router = APIRouter(tags=["literature-maps-v2"])
    repository = LiteratureRepository(store)

    @router.post("/literature-maps/publish", status_code=201)
    def publish_map(body: LiteratureMapPackage):
        try:
            return repository.publish(body)
        except KeyError as error:
            raise HTTPException(404, str(error))
        except ValueError as error:
            raise HTTPException(409, str(error))

    @router.get("/literature-maps/{map_id}")
    def read_map(map_id: str):
        result = repository.get_map(map_id)
        if not result:
            raise HTTPException(404, "literature map not found")
        return result

    @router.get("/works")
    def list_works():
        return repository.list_works()

    @router.get("/works/{work_id}/literature-maps/latest")
    def latest_map(work_id: str):
        try:
            result = repository.latest(work_id)
        except KeyError as error:
            raise HTTPException(404, str(error))
        if not result:
            raise HTTPException(404, "complete literature map not found")
        return result

    return router

