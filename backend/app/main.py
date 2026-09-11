import logging
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .models.search import HotQueriesResponse, SearchResponse
from .services.search_service import create_search_service
from .services.basket import BasketRequest, optimize_basket

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
app = FastAPI(title="DTU Grocery Price Compare")
app.add_middleware(CORSMiddleware, allow_origins=[settings.frontend_origin], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])
search_service = create_search_service()


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/search/hot", response_model=HotQueriesResponse)
async def hot_searches():
    return HotQueriesResponse(queries=search_service.cache.hottest(limit=8))


@app.get("/api/search", response_model=SearchResponse)
async def search(q: str = Query(..., min_length=2, max_length=100), location: str = Query("DTU")):
    try:
        return await search_service.search(q, location)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


@app.post("/api/basket/optimize")
async def basket(request: BasketRequest):
    try:
        return optimize_basket(request)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
