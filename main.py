import json
from contextlib import asynccontextmanager

from bs4 import BeautifulSoup
from fastapi import FastAPI
from httpx import AsyncClient

from search import SearchResult, SearchType
from utils import make_params
from zici import ZiciSearchResult


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
    page: int | None = None,
) -> SearchResult:
    client: AsyncClient = app.state.client
    params = make_params(value=keyword, type=type, page=page)
    resp = await client.get('/search.aspx', params=params)
    soup = BeautifulSoup(resp.text, 'lxml')
    return SearchResult.from_tag(soup, type=type)


@app.get('/word/{word}')
async def word(word: str) -> ZiciSearchResult:
    client: AsyncClient = app.state.client
    params = make_params(value=word)
    resp = await client.get('/zici/search.aspx', params=params)
    soup = BeautifulSoup(resp.text, 'lxml')
    return ZiciSearchResult.from_tag(soup)
