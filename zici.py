from typing import Self

from bs4 import Tag
from pydantic import BaseModel, Field


class Example(BaseModel):
    content: str
    source: str | None = None
    comment: str | None = None


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
    info: dict[str, str] = Field(default_factory=dict)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = super().from_tag(tag)
        if jinyi := tag.select_one('.jinyi-item .jinyiziContent'):
            result.info['近义词'] = jinyi.get_text(strip=True)
        if fanyi := tag.select_one('.fanyi-item .jinyiziContent'):
            result.info['反义词'] = fanyi.get_text(strip=True)
        if zuci := tag.select_one('.zuci'):
            result.info['组词'] = zuci.get_text().replace(' | ', '、')
        for liju in tag.select('.liju'):
            text = liju.get_text(strip=True)
            key, value = text.split('：')
            result.info[key] = value
        return result


class DetailShiyi(Shiyi):
    examples: list[Example] = Field(default_factory=list)

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = super().from_tag(tag)
        for yinzheng in tag.select('.yinzheng-item'):
            if zuci := yinzheng.select_one('.zuci'):
                if zhu := zuci.select_one('.zhu'):
                    zhu.extract()
                content = zuci.get_text(strip=True)
                example = Example(content=content)
                if source := yinzheng.select_one('.sourceYinzheng'):
                    example.source = source.get_text().removeprefix('——')
                if comment := yinzheng.select_one('.zhushiContent'):
                    example.comment = comment.get_text(strip=True)
                result.examples.append(example)
        return result


class ZiciSearchResult(BaseModel):
    name: str | None = None
    pinyin: str | None = None
    info: dict[str, str] = Field(default_factory=dict)
    data: list[BasicShiyi | DetailShiyi] | None = None

    @classmethod
    def from_tag(cls, tag: Tag) -> Self:
        result = cls()
        if cidianNames := tag.select_one('.zi-grid-container'):
            result.name = cidianNames.get_text(strip=True)
        if pinyinStr := tag.select_one('.pingyinStr'):
            result.pinyin = pinyinStr.get_text(strip=True)
        for infoItem in tag.select('.infoItem'):
            if (dinyi := infoItem.select_one('.dinyi')) and\
                    (zhi := infoItem.select_one('.dinyiZhi')):
                key = dinyi.get_text(strip=True)
                value = zhi.get_text(strip=True)
                if key not in result.info:
                    result.info[key] = value
        result.data = [
            DetailShiyi.from_tag(tag)
            if tag.select_one('.yinzheng-item') is not None else
            BasicShiyi.from_tag(tag)
            for tag in tag.select('.shiyiContent')
        ]
        return result
