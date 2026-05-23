import json
import re
from contextlib import asynccontextmanager
from typing import Literal, Self, override

from bs4 import BeautifulSoup, Tag
from bs4.element import NavigableString
from fastapi import FastAPI
from httpx import AsyncClient
from pydantic import BaseModel, Field


@asynccontextmanager
async def lifespan(app: FastAPI):
    with open('cookies.json', 'r') as file:
        cookies = json.load(file)

    async with AsyncClient(cookies=cookies) as client:
        app.state.client = client
        yield

app = FastAPI(lifespan=lifespan)


def get_text(element):
    parts = []
    for child in element.children:
        if isinstance(child, NavigableString):
            parts.append(child.string)
        elif child.name == 'br':
            parts.append('\n')
        else:
            parts.append(get_text(child))
    return ''.join(parts).strip()


class BaseShiwen(BaseModel):
    href: str | None = None
    title: str | None = None

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        shiwen = cls()
        if timu := tag.select_one('.timu'):
            if (timu.parent and 'href' in timu.parent.attrs
                    and type(timu.parent.attrs['href']) == str):
                shiwen.href = timu.parent.attrs['href']
            shiwen.title = get_text(timu)
        return shiwen


class Shiwen(BaseShiwen):
    source: str | None = None
    content: list[str] = Field(default_factory=list)

    @override
    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        shiwen = super().from_tag(tag)
        if source := tag.select_one('.source'):
            shiwen.source = get_text(source)
        if contson := tag.select_one('.contson'):
            shiwen.content = [
                get_text(tag)
                for tag in contson.select('p') or [contson]
            ]
        return shiwen


class Mingju(BaseModel):
    href: str | None = None
    content: str | None = None
    source: str | None = None
    source_href: str | None = None

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        mingju = cls()
        if content := tag.select_one('a.mingjuContent'):
            if 'href' in content.attrs and type(content.attrs['href']) == str:
                mingju.href = content.attrs['href']
            mingju.content = get_text(content)
        if source := tag.select_one('a.mingjuSource'):
            if 'href' in source.attrs and type(source.attrs['href']) == str:
                mingju.source_href = source.attrs['href']
            mingju.source = get_text(source)
        return mingju


class Book(BaseShiwen):
    alias: str | None = None
    mingju_count: int | None = None
    tags: set[str] = Field(default_factory=set)

    @override
    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        book = super().from_tag(tag)
        if beiming := tag.select_one('.bieming2'):
            book.alias = get_text(beiming)
        if (img := tag.select_one('img[src="../img/book/mingjuBefor.png"]')) \
                and (node := img.parent):
            if count := re.match(r'\d+', get_text(node)):
                book.mingju_count = int(count.group(0).strip())
            if parent := node.parent:
                book.tags = set(
                    text
                    for child in parent.children
                    if (text := get_text(child))
                    and not text == f'{book.mingju_count}条名句'
                )
        return book


class Page[T](BaseModel):
    data: list[T] = Field(default_factory=list)
    more: bool = False


def make_params(**kwargs) -> dict:
    return {
        key: value
        for key, value in kwargs.items()
        if value is not None
    }


async def search_soup(
    keyword: str,
        type: Literal['shiwen', 'mingju', 'book', 'author'] | None = None,
        page: int | None = None
):
    client: AsyncClient = app.state.client
    url = 'https://www.guwendao.net/search.aspx'
    resp = await client.get(url, params=make_params(value=keyword, type=type, page=page))
    soup = BeautifulSoup(resp.text, 'lxml')
    return soup


@app.get('/search/shiwen')
async def search_shiwen(keyword: str, page: int | None = None) -> Page[Shiwen]:
    tag = await search_soup(keyword, 'shiwen', page)
    result = Page(more=tag.select_one('a.amore') is not None)
    result.data = list(map(Shiwen.from_tag, tag.select('.zongheShiwen')))
    return result


@app.get('/search/mingju')
async def search_mingju(keyword: str, page: int | None = None) -> Page[Mingju]:
    tag = await search_soup(keyword, 'mingju', page)
    result = Page()
    result.data = list(map(Mingju.from_tag, tag.select('.mingju-item')))
    return result


@app.get('/search/book')
async def search_book(keyword: str, page: int | None = None) -> Page[Book]:
    tag = await search_soup(keyword, 'book', page)
    result = Page(more=tag.select_one('a.amore') is not None)
    result.data = list(map(Book.from_tag, tag.select('.zongheShiwen')))
    return result
