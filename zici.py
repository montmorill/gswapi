from typing import Self

from bs4 import Tag
from pydantic import BaseModel, Field


class Example(BaseModel):
    content: str
    source: str | None = None


class Shiyi(BaseModel):
    cixing: str | None = None
    jieshi: str | None = None

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = cls()
        if cixing := tag.select_one('.cixingContent'):
            result.cixing = cixing.get_text(strip=True)
        if jieshi := tag.select_one('.jieshi'):
            result.jieshi = jieshi.get_text(strip=True)
        return result


class BasicShiyi(Shiyi):
    extras: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = super().from_tag(tag)
        if jinyi := tag.select_one('.jinyi-item .jinyiziContent'):
            result.extras['近义词'] = jinyi.get_text(strip=True)
        if fanyi := tag.select_one('.fanyi-item .jinyiziContent'):
            result.extras['反义词'] = fanyi.get_text(strip=True)
        if zuci := tag.select_one('.zuci'):
            result.extras['组词'] = zuci.get_text().replace(' | ', '、')
        for liju in tag.select('.liju'):
            text = liju.get_text(strip=True)
            key, value = text.split('：')
            result.extras[key] = value
        return result


class DetailShiyi(Shiyi):
    examples: list[Example] = Field(default_factory=list)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = super().from_tag(tag)
        for yinzheng in tag.select('.yinzheng-item'):
            if zuci := yinzheng.select_one('.zuci'):
                content = zuci.get_text(strip=True)
                source = yinzheng.select_one('.sourceYinzheng')
                result.examples.append(Example(
                    content=content,
                    source=source.get_text(strip=True).removeprefix('——')
                    if source else None,
                ))
        return result


class ZiciSearchResult(BaseModel):
    name: str | None = None
    pinyin: str | None = None
    data: list[BasicShiyi | DetailShiyi] = Field(default_factory=list)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = cls()
        if cidianNames := tag.select_one('.zi-grid-container'):
            result.name = cidianNames.get_text(strip=True)
        if pinyinStr := tag.select_one('.pingyinStr'):
            result.pinyin = pinyinStr.get_text(strip=True)
        result.data = [
            DetailShiyi.from_tag(tag)
            if tag.select_one('.yinzheng-item') is not None else
            BasicShiyi.from_tag(tag)
            for tag in tag.select('.shiyiContent')
        ]
        return result
