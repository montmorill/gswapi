import json
import re
from contextlib import asynccontextmanager
from typing import Literal, Self

from bs4 import BeautifulSoup, Tag
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


def fenlei_selector(fenlei: str) -> str:
    return f'.main3>.left>div:has(img[src="../img/search/{fenlei}.png"])'


SHIWEN_BEFORE_SELECTOR = 'img[src="../img/book/shiwen.png"]'
MINGJU_BEFORE_SELECTOR = 'img[src="../img/book/mingjuBefor.png"]'


def parse_int(text: str) -> int | None:
    match = re.match(r'\d+', text)
    return int(match.group(0)) if match else None


def get_text(element) -> str:
    if isinstance(element, str):
        return element
    parts = []
    for child in element.children:
        if child.name == 'br':
            parts.append('\n')
        else:
            parts.append(get_text(child))
    return ''.join(parts).strip()


class Shiwen(BaseModel):
    href: str | None = None
    title: str | None = None
    source: str | None = None
    content: list[str] = Field(default_factory=list)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        shiwen = cls()
        if timu := tag.select_one('.timu'):
            if (timu.parent and 'href' in timu.parent.attrs
                    and type(timu.parent.attrs['href']) == str):
                shiwen.href = timu.parent.attrs['href']
            shiwen.title = get_text(timu)
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
        if content := tag.select_one('.mingjuContent'):
            if 'href' in content.attrs and type(content.attrs['href']) == str:
                mingju.href = content.attrs['href']
            mingju.content = get_text(content)
        if source := tag.select_one('.mingjuSource'):
            if 'href' in source.attrs and type(source.attrs['href']) == str:
                mingju.source_href = source.attrs['href']
            mingju.source = get_text(source)
        return mingju


class Book(BaseModel):
    href: str | None = None
    title: str | None = None
    alias: str | None = None
    mingju_count: int | None = None
    tags: set[str] = Field(default_factory=set)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        book = cls()
        if timu := tag.select_one('.timu'):
            if (timu.parent and 'href' in timu.parent.attrs
                    and type(timu.parent.attrs['href']) == str):
                book.href = timu.parent.attrs['href']
            book.title = get_text(timu)
        if beiming := tag.select_one('.bieming2'):
            book.alias = get_text(beiming)
        if (img := tag.select_one(MINGJU_BEFORE_SELECTOR)) and img.parent:
            if count := parse_int(mingju_count := get_text(img.parent)):
                book.mingju_count = count
            if parent := img.parent.parent:
                book.tags = set(
                    text
                    for child in parent.children
                    if (text := get_text(child))
                    and not text == mingju_count
                )
        return book


class Author(BaseModel):
    href: str | None = None
    name: str | None = None
    avatar: str | None = None
    content: str | None = None
    shiwen_count: int | None = None
    mingju_count: int | None = None

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        author = cls()
        if avatar := tag.select_one('img'):
            if 'src' in avatar.attrs and type(avatar.attrs['src']) == str:
                author.avatar = avatar.attrs['src']
            if 'alt' in avatar.attrs and type(avatar.attrs['alt']) == str:
                author.name = avatar.attrs['alt']
            if (a := avatar.parent) and 'href' in a.attrs and type(a.attrs['href']) == str:
                author.href = a.attrs['href']
        if (img := tag.select_one(SHIWEN_BEFORE_SELECTOR)):
            if count := parse_int(get_text(img.parent)):
                author.shiwen_count = count
        if (img := tag.select_one(MINGJU_BEFORE_SELECTOR)) and img.parent:
            if count := parse_int(get_text(img.parent)):
                author.mingju_count = count
        if contson := tag.select_one('.contson'):
            author.content = get_text(contson)
        return author


class Zhuanti(BaseModel):
    href: str | None = None
    title: str | None = None
    content: str | None = None

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        zhuanti = cls()
        if timu := tag.select_one('.timu'):
            if (timu.parent and 'href' in timu.parent.attrs
                    and type(timu.parent.attrs['href']) == str):
                zhuanti.href = timu.parent.attrs['href']
            zhuanti.title = get_text(timu)
        if content := tag.select_one('.content'):
            zhuanti.content = get_text(content)
        return zhuanti


class Page[T](BaseModel):
    zhuanti: Zhuanti | None = None
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
    result = Page(more=tag.select_one('.amore') is not None)
    if zhuanti := tag.select_one(fenlei_selector('zhuanti')):
        result.zhuanti = Zhuanti.from_tag(zhuanti)
    result.data = list(map(Shiwen.from_tag, tag.select('.zongheShiwen')))
    return result


@app.get('/search/mingju')
async def search_mingju(keyword: str, page: int | None = None) -> Page[Mingju]:
    tag = await search_soup(keyword, 'mingju', page)
    result = Page()
    if zhuanti := tag.select_one(fenlei_selector('zhuanti')):
        result.zhuanti = Zhuanti.from_tag(zhuanti)
    result.data = list(map(Mingju.from_tag, tag.select('.mingju-item')))
    return result


@app.get('/search/book')
async def search_book(keyword: str, page: int | None = None) -> Page[Book]:
    tag = await search_soup(keyword, 'book', page)
    result = Page(more=tag.select_one('.amore') is not None)
    result.data = list(map(Book.from_tag, tag.select('.zongheShiwen')))
    return result


@app.get('/search/author')
async def search_author(keyword: str, page: int | None = None) -> Page[Author]:
    tag = await search_soup(keyword, 'author', page)
    result = Page(more=tag.select_one('.amore') is not None)
    result.data = list(map(Author.from_tag, tag.select('.zongheShiwen')))
    return result
