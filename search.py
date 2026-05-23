from typing import Literal, Self

from bs4 import BeautifulSoup, Tag
from httpx import AsyncClient
from pydantic import BaseModel, Field

from utils import Page, make_params, parse_int


FENLEI_SELECTOR = '.main3>.left>div:has(img[src="../img/search/{fenlei}.png"])'
SHIWEN_BEFORE_SELECTOR = 'img[src="../img/book/shiwen.png"]'
MINGJU_BEFORE_SELECTOR = 'img[src="../img/book/mingjuBefor.png"]'


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
            shiwen.title = timu.text.strip()
        if source := tag.select_one('.source'):
            shiwen.source = source.text.strip()
        if contson := tag.select_one('.contson'):
            shiwen.content = [
                tag.text.strip()
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
            mingju.content = content.text.strip()
        if source := tag.select_one('.mingjuSource'):
            if 'href' in source.attrs and type(source.attrs['href']) == str:
                mingju.source_href = source.attrs['href']
            mingju.source = source.text.strip()
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
            book.title = timu.text.strip()
        if beiming := tag.select_one('.bieming2'):
            book.alias = beiming.text.strip()
        if (img := tag.select_one(MINGJU_BEFORE_SELECTOR)) and img.parent:
            if count := parse_int(mingju_count := img.parent.text.strip()):
                book.mingju_count = count
            if parent := img.parent.parent:
                book.tags = set(
                    text
                    for child in parent.children
                    if (text := child.text.strip())
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
            if img.parent and (count := parse_int(img.parent.text.strip())):
                author.shiwen_count = count
        if (img := tag.select_one(MINGJU_BEFORE_SELECTOR)) and img.parent:
            if count := parse_int(img.parent.text.strip()):
                author.mingju_count = count
        if contson := tag.select_one('.contson'):
            author.content = contson.text.strip()
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
            zhuanti.title = timu.text.strip()
        if content := tag.select_one('.content'):
            zhuanti.content = content.text.strip()
        return zhuanti


type SearchType = Literal['shiwen', 'mingju', 'book', 'author'] | None


class SearchResult(BaseModel):
    keyword: str
    type: SearchType = None
    page: int | None = None
    zhuanti: Page[Zhuanti] | None = None
    shiwen: Page[Shiwen] | None = None
    mingju: Page[Mingju] | None = None
    book: Page[Book] | None = None
    author: Page[Author] | None = None

    def parse_more(self, tag: Tag) -> bool:
        return (
            tag.select_one('.viewMore') is not None
            if self.type is None else
            tag.select_one('.amore') is not None
        )

    def parse_zhuanti(self, tag: Tag):
        return Page(
            data=map(Zhuanti.from_tag, tag.select('.zhuanti-item')),
            more=self.parse_more(tag)
        )

    def parse_shiwen(self, tag: Tag):
        return Page(
            data=map(Shiwen.from_tag, tag.select('.zongheShiwen')),
            more=self.parse_more(tag)
        )

    def parse_mingju(self, tag: Tag):
        return Page(
            data=map(Mingju.from_tag, tag.select('.mingju-item')),
            more=self.parse_more(tag)
        )

    def parse_book(self, tag: Tag):
        return Page(
            data=map(Book.from_tag, tag.select('.zongheShiwen')),
            more=self.parse_more(tag)
        )

    def parse_author(self, tag: Tag):
        return Page(
            data=map(Author.from_tag, tag.select('.zongheShiwen')),
            more=self.parse_more(tag)
        )

    async def search(self, client: AsyncClient):
        url = 'https://www.guwendao.net/search.aspx'
        resp = await client.get(url, params=make_params(
            value=self.keyword,
            type=self.type,
            page=self.page
        ))
        soup = BeautifulSoup(resp.text, 'lxml')
        if self.type is None:
            for field in ['zhuanti', 'shiwen', 'mingju', 'book', 'author']:
                if tag := soup.select_one(FENLEI_SELECTOR.format(fenlei=field)):
                    setattr(self, field, getattr(self, f'parse_{field}')(tag))
        elif self.type == 'shiwen':
            self.zhuanti = self.parse_zhuanti(soup)
            self.shiwen = self.parse_shiwen(soup)
        elif self.type == 'mingju':
            self.zhuanti = self.parse_zhuanti(soup)
            self.mingju = self.parse_mingju(soup)
        elif self.type == 'book':
            self.book = self.parse_book(soup)
        elif self.type == 'author':
            self.author = self.parse_author(soup)
        return self
