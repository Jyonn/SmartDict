from smartdict.resolver import RefStringStatus, RefStringStatusWithValue, ComponentWithValue
from smartdict.smartdict import SmartDict
from smartdict.path import Path

__all__ = [
    "parse",
    "RefStringStatus",
    "RefStringStatusWithValue",
    "ComponentWithValue",
    "SmartDict",
    "Path"
]


def parse(obj):
    return SmartDict(data=obj).parse()


def partial_parse(obj):
    return SmartDict(data=obj, partial=True).parse()


def iterative_parse(obj, iterations=1):
    return SmartDict(data=obj, iterations=iterations, partial=True).parse()
