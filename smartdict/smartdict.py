import warnings
from typing import Any, Dict, Optional, Hashable

from smartdict import function
from smartdict.path import Path
from smartdict.resolver import RefStringStatus, ComponentWithValue, RefStringStatusWithValue
from smartdict.roba import Roba


class CircularReferenceError(ReferenceError):
    """环状引用异常：当解析依赖链条回到自身时抛出。"""
    pass

class ReferenceNotFoundError(KeyError):
    """引用路径不存在：partial=False 时抛出。"""
    pass


# _FULL_REF_PATTERN = re.compile(r"^\$\{([^}]+)}\$$")
# _PARTIAL_REF_PATTERN = re.compile(r"\$\{([^}]+)}")


class SmartDict:
    def __init__(self, data: Any, partial: bool = False, iterations=1):
        self._src = data
        self._cache = {}  # type: Dict[str, RefStringStatus]
        self._partial = partial
        self._iterations = iterations if iterations >= 1 else 100

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
            self._cache.clear()
            component_value = self.deep_resolve(iter_src)
            iter_src = component_value.final

        if component_value is None:
            raise RuntimeError('source is not parsed yet')

        self._analyse(component_value)

        if return_cv:
            return component_value

        return iter_src

    def _analyse(self, component_value: ComponentWithValue, indent=-1):
        if self._partial or not component_value.has_unresolved:
            return

        count = 0

        if indent >= 0:
            print('  ' * indent + component_value.path + ':')

        for key, value in component_value.unresolved.items():
            if isinstance(value, ComponentWithValue):
                self._analyse(value, indent + 1)
            elif isinstance(value, RefStringStatus):
                print('  ' * (indent + 1) + str(value))
            else:
                raise RuntimeError(f'unexpected type {type(value)}')

            count += 1

        if indent == -1:
            raise ReferenceNotFoundError(f'Existing {count} unresolved references')

    @staticmethod
    def is_string(obj: Any) -> bool:
        return obj.__class__ is str

    @staticmethod
    def is_dict(obj: Any) -> bool:
        return obj.__class__ is dict

    @staticmethod
    def is_list(obj: Any) -> bool:
        return obj.__class__ is list

    @classmethod
    def is_tuple(cls: Any, obj: Any) -> bool:
        return obj.__class__ is tuple

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
        Automatically parses the type of default values:
          - "true" / "false" / "null" (case-insensitive)
          - Integers
          - Floats
          - Otherwise, keeps the string as-is
        """
        if isinstance(value, str):
            lower_val = value.lower()
            if lower_val == "true":
                return True
            elif lower_val == "false":
                return False
            elif lower_val == "null":
                return None
            else:
                # Attempt to parse as int
                try:
                    return int(value)
                except ValueError:
                    pass
                # Attempt to parse as float
                try:
                    return float(value)
                except ValueError:
                    pass
                # Keep as string
                return value
        else:
            # Non-string types remain unchanged
            return value

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

    def _resolve_ref_string(self, ref_string: str, path: Path) -> RefStringStatusWithValue:
        if ':' in ref_string:
            ref_string, default_str = ref_string.split(':', 1)
            default_value = self._parse_default_value(default_str)
        else:
            default_value = RefStringStatus.UNSET_VALUE

        if ref_string in self._cache:
            if self._cache[ref_string].is_resolving:
                raise CircularReferenceError(ref_string)
            return RefStringStatusWithValue(self._cache[ref_string], default_value)

        self._cache[ref_string] = RefStringStatus(ref_string)
        subkeys = ref_string.split(".") if ref_string else []
        current_value = self._src
        current_path = path
        for key in subkeys:
            current_path = current_path / key
            current_value = self._get_value(current_value, key)
            if current_value is RefStringStatus.NOTFOUND:
                break
            component_value = self.deep_resolve(current_value, current_path)
            current_value = component_value.final

        if current_value is RefStringStatus.NOTFOUND:
            self._cache[ref_string].unresolve()
        else:
            self._cache[ref_string].resolve(current_value)
        return RefStringStatusWithValue(self._cache[ref_string], default_value)

    def _resolve_string(self, obj: str, path: Path) -> ComponentWithValue:
        component_value = ComponentWithValue(path)

        parts = function.parse_ref_string(obj)
        if len(parts) == 1 and parts[0].full:
            ref_string = self._resolve_string(parts[0].part, path).final
            ref_value = self._resolve_ref_string(ref_string, path=path / '$')
            return component_value.push(ref_value).finalize(obj if ref_value.is_unset else ref_value.value)

        # m_full = _FULL_REF_PATTERN.match(obj)
        #
        # if m_full:
        #     ref_value = self._resolve_ref_string(m_full.group(1), path=path / '$')
        #     return component_value.push(ref_value).finalize(obj if ref_value.is_unset else ref_value.value)

        result_parts = []

        for p in parts:
            if not p.partial:
                result_parts.append(p.part)
                continue
            ref_string = self._resolve_string(p.part, path).final
            ref_value = self._resolve_ref_string(ref_string, path=path / '$')
            current = p.part if ref_value.is_unset else ref_value.value
            component_value.push(ref_value)

            result_parts.append(str(current))

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
