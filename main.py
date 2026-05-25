import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from httpx import AsyncClient

from search import SearchResult, SearchParams, SearchType


@asynccontextmanager
async def lifespan(app: FastAPI):
    with open('cookies.json', 'r') as file:
        cookies = json.load(file)

    async with AsyncClient(
        base_url='https://www.guwendao.net',
        cookies=cookies
    ) as client:
        app.state.client = client
        yield


app = FastAPI(lifespan=lifespan)


@app.get('/search')
async def search(
    keyword: str,
    type: SearchType | None = None,
    page: int | None = None
) -> SearchResult:
    params = SearchParams(keyword=keyword, type=type, page=page)
    return await params.search(app.state.client)
