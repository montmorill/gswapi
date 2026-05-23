import re
from typing import Iterable

from pydantic import BaseModel, Field


def parse_int(text: str) -> int | None:
    match = re.match(r'\d+', text)
    return int(match.group(0)) if match else None


def make_params(**kwargs) -> dict:
    return {
        key: value
        for key, value in kwargs.items()
        if value is not None
    }


class Page[T](BaseModel):
    data: Iterable[T] = Field(default_factory=list)
    more: bool = False
