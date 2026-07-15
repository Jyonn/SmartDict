import json
import re
import warnings
from dataclasses import dataclass
from typing import Any, Dict, Optional, Hashable

from smartdict import function
from smartdict.path import Path
from smartdict.resolver import RefStringStatus, ComponentWithValue, RefStringStatusWithValue
from smartdict.roba import Roba


@dataclass(frozen=True)
class UnresolvedReference:
    path: str
    reference: str


@dataclass(frozen=True)
class PipelineStage:
    name: str
    arg: Any = None


class CircularReferenceError(ReferenceError):
    """Raised when a reference dependency chain loops back to itself."""

    def __init__(self, ref_string: str):
        self.ref_string = ref_string
        super().__init__(f'Circular reference detected: {ref_string}')


class ReferenceNotFoundError(KeyError):
    """Raised when strict parsing encounters unresolved references."""

    def __init__(self, unresolved: list[UnresolvedReference]):
        self.unresolved = tuple(unresolved)
        details = ', '.join(
            f'{item.path or "<root>"} -> {item.reference}' for item in self.unresolved
        )
        super().__init__(f'Unresolved references: {details}')


class PipelineStageError(ValueError):
    """Raised when a pipeline stage cannot be applied."""

    def __init__(self, stage: str, value: Any, path: Path, message: str):
        self.stage = stage
        self.value = value
        self.path = str(path)
        super().__init__(f'Pipeline stage `{stage}` failed at {self.path or "<root>"}: {message}')


# _FULL_REF_PATTERN = re.compile(r"^\$\{([^}]+)}\$$")
# _PARTIAL_REF_PATTERN = re.compile(r"\$\{([^}]+)}")


class SmartDict:
    def __init__(self, data: Any, partial: bool = False, iterations=1):
        if iterations <= 0:
            raise ValueError('`iterations` must be greater than 0')

        self._src = data
        self._cache = {}  # type: Dict[str, RefStringStatus]
        self._partial = partial
        self._iterations = iterations

        if self._iterations > 1 and not self._partial:
            self._partial = True
            warnings.warn('`partial` will be set to True when `iteration` > 1')

    def combine_and_parse(self, cache: dict, return_cv=False):
        roba = Roba(self._src)
        for key, value in cache.items():
            roba[key] = value
        self._src = roba()

        component_value = self.deep_resolve(self._src)
        src = component_value.final

        self._analyse(component_value)

        if return_cv:
            return component_value

        return src

    def parse(self, return_cv=False) -> Any:
        iter_src = self._src
        component_value = None  # type: Optional[ComponentWithValue]
        for _ in range(self._iterations):
            # Each iterative pass should resolve against the latest expanded
            # snapshot so newly generated keys become visible on the next round.
            self._src = iter_src
            self._cache.clear()
            component_value = self.deep_resolve(iter_src)
            iter_src = component_value.final

        if component_value is None:
            raise RuntimeError('source is not parsed yet')

        self._analyse(component_value)

        if return_cv:
            return component_value

        return iter_src

    def _collect_unresolved(self, component_value: ComponentWithValue) -> list[UnresolvedReference]:
        unresolved = []
        for value in component_value.unresolved.values():
            if isinstance(value, ComponentWithValue):
                unresolved.extend(self._collect_unresolved(value))
            elif isinstance(value, RefStringStatus):
                unresolved.append(
                    UnresolvedReference(
                        path=component_value.path,
                        reference=value.ref_string,
                    )
                )
            else:
                raise RuntimeError(f'unexpected type {type(value)}')
        return unresolved

    def _analyse(self, component_value: ComponentWithValue):
        if self._partial or not component_value.has_unresolved:
            return

        raise ReferenceNotFoundError(self._collect_unresolved(component_value))

    @staticmethod
    def is_string(obj: Any) -> bool:
        return isinstance(obj, str)

    @staticmethod
    def is_dict(obj: Any) -> bool:
        return isinstance(obj, dict)

    @staticmethod
    def is_list(obj: Any) -> bool:
        return isinstance(obj, list)

    @classmethod
    def is_tuple(cls: Any, obj: Any) -> bool:
        return isinstance(obj, tuple)

    def deep_resolve(self, obj: Any, path: Path = None) -> ComponentWithValue:
        path = path or Path()

        if self.is_string(obj):
            return self._resolve_string(obj, path=path)

        final_component_value = ComponentWithValue(path)

        if self.is_list(obj) or self.is_tuple(obj):
            new_list = []
            for i, item in enumerate(obj):
                component_value = self.deep_resolve(item, path=path / str(i))
                new_list.append(component_value.final)
                final_component_value.list_push(str(i), component_value)
            if self.is_tuple(obj):
                new_list = tuple(new_list)
            return final_component_value.finalize(new_list)

        if self.is_dict(obj):
            new_dict = {}
            for key, value in obj.items():
                key_path = path / f'<k>' / key
                key_component_value = self.deep_resolve(key, path=key_path)
                final_component_value.dict_push(f'<k> / {key}', key_component_value)
                if not isinstance(key_component_value.final, Hashable):
                    raise TypeError(f'Key object is not hashable: {key_component_value.final}')
                new_key = key_component_value.final

                if new_key in new_dict:
                    raise KeyError(f'Duplicate key: {new_key}')

                value_component_value = self.deep_resolve(value, path=path / str(new_key))
                final_component_value.dict_push(new_key, value_component_value)
                new_dict[new_key] = value_component_value.final
            return final_component_value.finalize(new_dict)

        return final_component_value.finalize(obj)

    @staticmethod
    def _parse_default_value(value: Any) -> Any:
        """
        Automatically parses default values.

        It first attempts JSON parsing so values like `null`, `true`, `false`,
        numbers, arrays, and objects keep their native Python types.
        If JSON parsing fails, it falls back to the original loose scalar
        parsing behavior so bare strings like `fallback` remain supported.
        """
        if isinstance(value, str):
            stripped = value.strip()
            try:
                return json.loads(stripped)
            except json.JSONDecodeError:
                pass

            # Preserve support for unquoted fallback strings and other
            # non-JSON literals used by existing callers.
            try:
                return int(value)
            except ValueError:
                pass
            try:
                return float(value)
            except ValueError:
                pass
            return value
        else:
            # Non-string types remain unchanged
            return value

    @staticmethod
    def _split_ref_expression(ref_string: str):
        ref, default = function.split_top_level_once(ref_string, ':')
        if default is None:
            return ref, RefStringStatus.UNSET_VALUE
        return ref, default

    @staticmethod
    def _parse_stage_arg(arg: Any) -> Any:
        if arg is None:
            return None
        if isinstance(arg, str) and '${' in arg:
            return arg
        return SmartDict._parse_default_value(arg)

    def _parse_pipeline_expression(self, expression: str):
        pieces = function.split_top_level(expression, '|')
        head = pieces[0]
        ref_string, default_str = self._split_ref_expression(head)

        stages = []
        for raw_stage in pieces[1:]:
            stage_name, stage_arg = function.split_top_level_once(raw_stage, ':')
            stage_name = stage_name.strip()
            if not stage_name:
                raise ValueError(f'Invalid pipeline stage in expression: {expression}')
            stage_arg = None if stage_arg is None else stage_arg.strip()
            stages.append(PipelineStage(name=stage_name, arg=self._parse_stage_arg(stage_arg)))

        return ref_string, default_str, stages

    @staticmethod
    def _stringify_resolved_part(value: Any, for_ref: bool = False):
        if for_ref:
            if value is None:
                return 'null'
            if value is True:
                return 'true'
            if value is False:
                return 'false'
        return str(value)

    def _apply_pipeline_stages(self, value: Any, stages: list[PipelineStage], path: Path):
        current = value
        for stage in stages:
            current = self._apply_pipeline_stage(current, stage, path)
        return current

    @staticmethod
    def _stage_bool(value: Any):
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == 'true':
                return True
            if lowered == 'false':
                return False
        raise ValueError(f'cannot convert {value!r} to bool')

    @staticmethod
    def _stage_slug(value: Any):
        text = str(value).strip().lower()
        text = re.sub(r'[^a-z0-9]+', '-', text)
        return text.strip('-')

    def _apply_pipeline_stage(self, value: Any, stage: PipelineStage, path: Path):
        name = stage.name
        try:
            if name == 'int':
                return int(value)
            if name == 'float':
                return float(value)
            if name == 'bool':
                return self._stage_bool(value)
            if name == 'json':
                if isinstance(value, str):
                    return json.loads(value)
                return value
            if name == 'lower':
                return str(value).lower()
            if name == 'upper':
                return str(value).upper()
            if name == 'strip':
                return str(value).strip()
            if name == 'slug':
                return self._stage_slug(value)
        except Exception as exc:
            raise PipelineStageError(name, value, path, str(exc)) from exc

        raise PipelineStageError(name, value, path, 'unknown stage')

    @staticmethod
    def _get_value(obj: Any, key):
        try:
            return obj[key]
        except Exception:
            pass

        try:
            return getattr(obj, key)
        except Exception:
            pass

        try:
            return obj[int(key)]
        except Exception:
            pass

        return RefStringStatus.NOTFOUND

    def _resolve_path_component(self, value: Any, path: Path, is_leaf: bool):
        if is_leaf:
            return self.deep_resolve(value, path).final

        # Only resolve string aliases for intermediate nodes so we can keep
        # walking the requested path without eagerly resolving sibling fields.
        while self.is_string(value):
            resolved = self.deep_resolve(value, path).final
            if resolved == value:
                break
            value = resolved

        return value

    def _resolve_ref_string(
        self,
        ref_string: str,
        default_str: Any,
        path: Path,
    ) -> RefStringStatusWithValue:
        if default_str is RefStringStatus.UNSET_VALUE:
            default_value = RefStringStatus.UNSET_VALUE
        else:
            if self.is_string(default_str) and '${' in default_str:
                default_value = self._resolve_string(default_str, path=path, raw_single_ref=True).final
            else:
                default_value = self._parse_default_value(default_str)

        if ref_string in self._cache:
            if self._cache[ref_string].is_resolving:
                raise CircularReferenceError(ref_string)
            return RefStringStatusWithValue(self._cache[ref_string], default_value)

        self._cache[ref_string] = RefStringStatus(ref_string)
        subkeys = ref_string.split(".") if ref_string else []
        current_value = self._src
        current_path = path
        last_index = len(subkeys) - 1
        for index, key in enumerate(subkeys):
            current_path = current_path / key
            current_value = self._get_value(current_value, key)
            if current_value is RefStringStatus.NOTFOUND:
                break
            current_value = self._resolve_path_component(
                current_value,
                current_path,
                is_leaf=index == last_index,
            )

        if current_value is RefStringStatus.NOTFOUND:
            self._cache[ref_string].unresolve()
        else:
            self._cache[ref_string].resolve(current_value)
        return RefStringStatusWithValue(self._cache[ref_string], default_value)

    def _resolve_reference_expression(self, expression: str, path: Path) -> RefStringStatusWithValue:
        ref_string, default_str, stages = self._parse_pipeline_expression(expression)
        ref_value = self._resolve_ref_string(ref_string, default_str, path)
        if ref_value.is_unset:
            return ref_value

        final_value = self._apply_pipeline_stages(ref_value.value, stages, path)
        return RefStringStatusWithValue(ref_value.status, final_value, preserve_value=True)

    def _resolve_string(self, obj: str, path: Path, raw_single_ref: bool = False) -> ComponentWithValue:
        component_value = ComponentWithValue(path)

        parts = function.parse_ref_string(obj)
        if len(parts) == 1 and parts[0].full:
            ref_string = self._resolve_string(parts[0].part, path, raw_single_ref=True).final
            ref_value = self._resolve_reference_expression(ref_string, path=path / '$')
            return component_value.push(ref_value).finalize(obj if ref_value.is_unset else ref_value.value)

        if len(parts) == 1 and parts[0].partial:
            ref_string = self._resolve_string(parts[0].part, path, raw_single_ref=True).final
            ref_value = self._resolve_reference_expression(ref_string, path=path / '$')
            current = '${' + ref_string + '}' if ref_value.is_unset else ref_value.value
            component_value.push(ref_value)
            if raw_single_ref or obj == '${' + parts[0].part + '}':
                return component_value.finalize(current)
            return component_value.finalize(str(current))

        result_parts = []

        for p in parts:
            if not p.partial:
                result_parts.append(p.part)
                continue
            ref_string = self._resolve_string(p.part, path, raw_single_ref=True).final
            ref_value = self._resolve_reference_expression(ref_string, path=path / '$')
            current = '${' + ref_string + '}' if ref_value.is_unset else ref_value.value
            component_value.push(ref_value)

            result_parts.append(self._stringify_resolved_part(current, for_ref=raw_single_ref))

        return component_value.finalize(''.join(result_parts))


        #
        # matches = list(_PARTIAL_REF_PATTERN.finditer(obj))
        # if not matches:
        #     return component_value.finalize(obj)
        #
        # result_parts = []
        # last_end = 0
        # for m in matches:
        #     start_idx = m.start()
        #     end_idx = m.end()
        #     # Add the original text before this reference
        #     result_parts.append(obj[last_end:start_idx])
        #
        #     ref_value = self._resolve_ref_string(m.group(1), path=path / '$')
        #     current = m.group(0) if ref_value.is_unset else ref_value.value
        #     component_value.push(ref_value)
        #
        #     result_parts.append(str(current))
        #
        #     last_end = end_idx
        # # Add the remaining text after the last reference
        # result_parts.append(obj[last_end:])
        #
        # return component_value.finalize("".join(result_parts))

    @property
    def cache(self):
        return self._cache


if __name__ == '__main__':
    data_ = {
        'a': {
            'z': 1,
            'b${a.y}': '${a.b}$',
            'c': '${a.b1}bad',
            'b': 33,
        }
    }
    data_ = SmartDict(data_).parse()
    print(data_)
