import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient

from search import SearchResult, SearchType


@asynccontextmanager
async def lifespan(app: FastAPI):
    with open('cookies.json', 'r') as file:
        cookies = json.load(file)

    async with AsyncClient(cookies=cookies) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get('/search')
async def search(
    keyword: str,
    type: SearchType = None,
    page: int | None = None
) -> SearchResult:
    result = SearchResult(keyword=keyword, type=type, page=page)
    return await result.search(app.state.client)
