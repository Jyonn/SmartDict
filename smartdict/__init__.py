from smartdict.resolver import RefStringStatus, RefStringStatusWithValue, ComponentWithValue
from smartdict.smartdict import (
    SmartDict,
    CircularReferenceError,
    PipelineStageError,
    ReferenceNotFoundError,
    PipelineStage,
    UnresolvedReference,
)
from smartdict.path import Path

__version__ = "0.5.0"

__all__ = [
    "parse",
    "partial_parse",
    "iterative_parse",
    "RefStringStatus",
    "RefStringStatusWithValue",
    "ComponentWithValue",
    "SmartDict",
    "CircularReferenceError",
    "PipelineStageError",
    "ReferenceNotFoundError",
    "PipelineStage",
    "UnresolvedReference",
    "Path"
]


def parse(obj):
    return SmartDict(data=obj).parse()


def partial_parse(obj):
    return SmartDict(data=obj, partial=True).parse()


def iterative_parse(obj, iterations=1):
    return SmartDict(data=obj, iterations=iterations, partial=True).parse()
