from typing import ClassVar, Literal, Protocol, Self

from bs4 import Tag
from pydantic import BaseModel, Field

from utils import parse_int


FENLEI_SELECTOR = '.main3>.left>div:has(img[src="../img/search/{fenlei}.png"])'
SHIWEN_BEFORE_SELECTOR = 'img[src="../img/book/shiwen.png"]'
MINGJU_BEFORE_SELECTOR = 'img[src="../img/book/mingjuBefor.png"]'

type SearchType = Literal['shiwen', 'mingju', 'book', 'author']


class Zhuanti(BaseModel):
    selector: ClassVar[str] = '.zhuanti-item'

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


class Shiwen(BaseModel):
    selector: ClassVar[str] = '.zongheShiwen'

    href: str | None = None
    title: str | None = None
    source: str | None = None
    content: list[str] | None = None

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
    selector: ClassVar[str] = '.mingju-item'

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
    selector: ClassVar[str] = '.zongheShiwen'

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
    selector: ClassVar[str] = '.zongheShiwen'

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


class FromTag(Protocol):
    selector: ClassVar[str]

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        ...


def parse_tags[T: FromTag](cls: type[T], tag: Tag) -> list[T]:
    return [cls.from_tag(tag) for tag in tag.select(cls.selector)]


ITEM_TYPE_TO_CLASS: dict[Literal[SearchType, "zhuanti"], type[FromTag]] = {
    'zhuanti': Zhuanti,
    'shiwen': Shiwen,
    'mingju': Mingju,
    'book': Book,
    'author': Author,
}


class SearchResult(BaseModel):
    zhuantis: list[Zhuanti] | None = None
    shiwens: list[Shiwen] | None = None
    mingjus: list[Mingju] | None = None
    books: list[Book] | None = None
    authors: list[Author] | None = None
    more: bool = False

    @classmethod
    def from_tag(cls, tag: Tag, type: SearchType | None = None):
        result = cls()
        if type is None:
            result.more = tag.select_one('.viewMore') is not None
            for field in ITEM_TYPE_TO_CLASS.keys():
                selector = FENLEI_SELECTOR.format(fenlei=field)
                if fenlei := tag.select_one(selector):
                    items = parse_tags(ITEM_TYPE_TO_CLASS[field], fenlei)
                    setattr(result, f'{field}s', items)
            return result
        if len(zhuantis := parse_tags(Zhuanti, tag)):
            result.zhuantis = zhuantis
        setattr(result, f'{type}s', parse_tags(ITEM_TYPE_TO_CLASS[type], tag))
        result.more = tag.select_one('.amore') is not None
        return result
