# SmartDict

`smartdict` is a small Python library for resolving references inside nested data structures.
It is especially useful for configuration dictionaries where one field needs to reuse another.

SmartDict walks through built-in `dict`, `list`, and `tuple` containers, finds reference
expressions inside strings, and replaces them with resolved values.

## Features

- Inline string interpolation with `${path.to.value}`
- Native-value resolution for single references such as `${path.to.value}`
- Optional explicit full-match syntax with `${path.to.value}$`
- Nested reference strings such as `${${keys.${env}}}`
- Default values such as `${missing:42}`, `${missing:fallback}`, or `${missing:[1, 2, 3]}`
- Optional pipelines such as `${env.PORT:8000|int}` or `${dataset:"unknown"|slug}`
- Dictionary key generation from references
- List and tuple index lookup through dotted paths
- Circular reference detection
- Strict mode, partial mode, and iterative parsing mode

## Installation

```bash
pip install smartdict
```

## Quick Start

```python
import smartdict

data = {
    "dataset": "spotify",
    "load": {
        "base_path": "~/data/${dataset}",
        "train_path": "${load.base_path}/train",
        "dev_path": "${load.base_path}/dev",
        "test_path": "${load.base_path}/test",
    },
    "network": {
        "num_hidden_layers": 3,
        "num_attention_heads": 8,
    },
    "store": "checkpoints/${dataset}/${network.num_hidden_layers}L${network.num_attention_heads}H/",
}

parsed = smartdict.parse(data)

print(parsed["load"]["base_path"])
# ~/data/spotify

print(parsed["load"]["dev_path"])
# ~/data/spotify/dev

print(parsed["store"])
# checkpoints/spotify/3L8H/
```

## Reference Syntax

### 1. References

Use `${...}` as the default reference syntax.

```python
import smartdict

parsed = smartdict.parse({
    "name": "smartdict",
    "message": "hello-${name}",
})

print(parsed["message"])
# hello-smartdict
```

When `${...}` is part of a larger string, SmartDict performs string interpolation.

When the whole value is a single reference, SmartDict preserves the referenced value type:

```python
import smartdict

parsed = smartdict.parse({
    "config": {"debug": True},
    "selected": "${config}",
})

print(parsed["selected"])
# {'debug': True}
```

This means `${config}`, `${missing:null}`, and `${missing:[1, 2, 3]}` can all resolve to
native Python values instead of strings.

### 2. Explicit full-match references

Use `${...}$` when you want to make that intent explicit in config files or examples.

```python
import smartdict

parsed = smartdict.parse({
    "config": {
        "debug": True,
        "retries": 3,
    },
    "selected": "${config}$",
})

print(parsed["selected"])
# {'debug': True, 'retries': 3}
```

`${...}$` is kept for readability and backward compatibility, but it is no longer the only way
to get non-string values.

### 3. Nested reference strings

Reference expressions can themselves contain reference expressions.

```python
import smartdict

parsed = smartdict.parse({
    "env": "prod",
    "keys": {"prod": "url"},
    "url": "https://example.com",
    "result": "${${keys.${env}}}",
})

print(parsed["result"])
# https://example.com
```

### 4. Default values

If a path cannot be found, you can provide a default value with `:`.

```python
import smartdict

parsed = smartdict.parse({
    "int_value": "${missing:42}",
    "bool_value": "${missing:true}",
    "null_value": "${missing:null}",
    "text_value": "${missing:fallback}",
})

print(parsed)
# {
#   'int_value': 42,
#   'bool_value': True,
#   'null_value': None,
#   'text_value': 'fallback'
# }
```

Default values are automatically interpreted as JSON when possible:

- `true` / `false` -> `bool`
- `null` -> `None`
- integers -> `int`
- floats -> `float`
- arrays -> `list`
- objects -> `dict`
- anything else -> `str`

Bare fallback strings such as `${missing:fallback}` remain supported for convenience.

Nested default expressions are also supported:

```python
import smartdict

parsed = smartdict.parse({
    "repr_source_model": "text-embedding-3-small",
    "embedding_model": "${sid_embedding_model:${repr_source_model:null}}",
})

print(parsed["embedding_model"])
# text-embedding-3-small
```

If both references are missing, the same expression resolves to `None`.

JSON arrays and objects are also valid defaults:

```python
import smartdict

parsed = smartdict.parse({
    "sinkhorn_epsilon": "${sid_sinkhorn_epsilon:[0.0, 0.0, 0.003]}",
    "metadata": '${config:{"hello": "world"}}',
})

print(parsed["sinkhorn_epsilon"])
# [0.0, 0.0, 0.003]

print(parsed["metadata"])
# {'hello': 'world'}
```

If the primary value already exists, SmartDict keeps that value and ignores the default:

```python
import smartdict

parsed = smartdict.parse({
    "sid_sinkhorn_epsilon": [1.0, 2.0, 3.0],
    "sinkhorn_epsilon": "${sid_sinkhorn_epsilon:[0.0, 0.0, 0.003]}",
})

print(parsed["sinkhorn_epsilon"])
# [1.0, 2.0, 3.0]
```

### 5. Pipelines

SmartDict also supports simple pipelines:

```python
import smartdict

parsed = smartdict.parse({
    "dataset": "  My Dataset  ",
    "save_dir": "${dataset|strip|lower|slug}",
    "port": "${env.PORT:8000|int}",
})

print(parsed["save_dir"])
# my-dataset

print(parsed["port"])
# 8000
```

Pipeline execution order is:

1. Resolve the reference
2. If missing, apply the default value
3. Run pipeline stages from left to right

Current built-in stages:

- `int`
- `float`
- `bool`
- `json`
- `lower`
- `upper`
- `strip`
- `slug`

Examples:

```python
import smartdict

parsed = smartdict.parse({
    "raw": '{"hello": "world"}',
    "value": "${raw|json}",
    "embedding_model": "${sid_embedding_model:${repr_source_model:null}|lower}",
})
```

If a pipeline stage fails, SmartDict raises `PipelineStageError`.

### 6. List and tuple indices

Dotted paths can also index built-in sequences.

```python
import smartdict

parsed = smartdict.parse({
    "items": ["a", "b"],
    "pair": ("x", "y"),
    "pick_list": "${items.1}",
    "pick_tuple": "${pair.0}",
})

print(parsed["pick_list"])
# b

print(parsed["pick_tuple"])
# x
```

### 7. Dictionary keys can be generated

References are resolved in both keys and values.

```python
import smartdict

parsed = smartdict.parse({
    "name": "k",
    "${name}": 1,
})

print(parsed)
# {'name': 'k', 'k': 1}
```

### 8. Referencing custom objects

SmartDict resolves path components in this order:

1. `obj[key]`
2. `getattr(obj, key)`
3. `obj[int(key)]`

That means you can expose custom lookup behavior through objects used inside your data.

```python
import random
import string

import smartdict


class Rand(dict):
    chars = string.ascii_letters + string.digits

    def __getitem__(self, item):
        return "".join(random.choice(self.chars) for _ in range(int(item)))


parsed = smartdict.parse({
    "utils": {
        "rand": Rand(),
    },
    "filename": "${utils.rand.4}",
})

print(parsed["filename"])
# for example: aZ19
```

## Parse Modes

### `smartdict.parse(obj)`

Strict mode.

- Resolves all references
- Raises an error if any reference cannot be resolved
- Detects circular references

```python
import smartdict

parsed = smartdict.parse({
    "a": "x",
    "b": "${a}/y",
})

print(parsed)
# {'a': 'x', 'b': 'x/y'}
```

### `smartdict.partial_parse(obj)`

Best-effort mode.

- Resolves what it can
- Does not raise for missing references
- Leaves unresolved results in their current best-effort form

```python
import smartdict

parsed = smartdict.partial_parse({
    "a": "${missing}",
    "b": "pre-${missing}-post",
    "c": "${missing}$",
})

print(parsed)
# {'a': '${missing}', 'b': 'pre-${missing}-post', 'c': '${missing}$'}
```

### `smartdict.iterative_parse(obj, iterations=1)`

Repeated best-effort parsing.

This is useful when one pass unlocks another pass.

```python
import smartdict

parsed = smartdict.iterative_parse({
    "a": "${b}",
    "b": "${c}",
    "c": "ok",
}, iterations=2)

print(parsed)
# {'a': 'ok', 'b': 'ok', 'c': 'ok'}
```

## Errors

### `ReferenceNotFoundError`

Raised by `smartdict.parse()` when a reference cannot be resolved.

```python
import smartdict
from smartdict.smartdict import ReferenceNotFoundError

try:
    smartdict.parse({
        "a": "${missing}",
    })
except ReferenceNotFoundError as exc:
    print(type(exc).__name__, exc)
```

Nested missing references are also detected:

```python
import smartdict

smartdict.parse({
    "app": {
        "profile": "prod",
    },
    "services": {
        "prod": {
            "url": "${config.endpoints.api}",
        },
    },
    "result": "${services.${app.profile}.url}",
})
```

### `CircularReferenceError`

Raised when references depend on each other in a cycle.

```python
import smartdict
from smartdict.smartdict import CircularReferenceError

try:
    smartdict.parse({
        "a": "${b}$",
        "b": "${a}$",
    })
except CircularReferenceError as exc:
    print(type(exc).__name__, exc)
```

Cycles can also appear across nested dictionaries:

```python
import smartdict

smartdict.parse({
    "app": {
        "profile": "${services.primary.profile}$",
    },
    "services": {
        "primary": {
            "profile": "${app.profile}$",
        },
    },
})
```

### `KeyError`

Raised when two dictionary keys resolve to the same final key.

```python
import smartdict

smartdict.parse({
    "aliases": {
        "primary": "stable",
    },
    "${aliases.primary}": 1,
    "stable": 2,
})
```

## Public API

The main public entry points are:

```python
import smartdict

smartdict.parse(obj)
smartdict.partial_parse(obj)
smartdict.iterative_parse(obj, iterations=2)
```

The package also exports:

- `SmartDict`
- `Path`
- `CircularReferenceError`
- `PipelineStageError`
- `PipelineStage`
- `ReferenceNotFoundError`
- `UnresolvedReference`
- `RefStringStatus`
- `RefStringStatusWithValue`
- `ComponentWithValue`

## Development

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

Build distributions with:

```bash
python -m build
```

## Notes and Current Behavior

- SmartDict recursively parses built-in `dict`, `list`, `tuple`, and `str` values.
- Intermediate path components can be aliases, including full-match references such as `${config}$`.
- In strict mode, unresolved references raise `ReferenceNotFoundError`.
- `ReferenceNotFoundError.unresolved` contains structured unresolved entries with `path` and `reference`.
- `iterations` must be greater than `0`.
- If resolved dictionary keys collide, SmartDict raises `KeyError`.

## License

MIT
