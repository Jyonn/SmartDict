import copy
import re


class CircularReferenceError(Exception):
    """Raised when a circular reference is detected."""
    pass


class InvalidPathError(Exception):
    """Raised when an invalid path or index is accessed."""
    pass


class DictReferenceResolver:
    """
    Recursively resolves references of the form:
      - ${path} or ${path}$,
      - optionally with a default value, e.g. ${path:default} or ${path:default}$.
    Prevents true circular dependencies. E.g. if a -> b -> a, it raises CircularReferenceError.
    """

    PARTIAL_REF_REGEX = re.compile(r'\${(.*?)}')
    FULL_REF_REGEX = re.compile(r'\${(.*?)}\$')

    class InCircle:
        """Marker class to indicate that a path is currently being resolved."""
        pass

    class NotFound:
        """Marker class for no full-reference match."""
        pass

    class NoDefault:
        """Marker class for no default value."""
        pass

    def __init__(self, data: dict):
        self.data = copy.deepcopy(data)  # Deep copy original data
        self.circle = {}  # Tracks resolution status

    def resolve(self):
        """Public method to parse and return the resolved structure."""
        return self._process_value([], self.data)

    def _process_value(self, path_list: list, value):
        """
        Dispatch based on value's type:
         - dict: process each key-value
         - list/tuple: process each element
         - str: attempt to parse references
         - other: return as is
        """
        if isinstance(value, dict):
            return self._process_dict(path_list, value)
        elif isinstance(value, (list, tuple)):
            return self._process_sequence_items(path_list, value)
        elif isinstance(value, str):
            # 'path_list' indicates where this string is located in the data
            caller_path = '.'.join(path_list)
            return self._process_string(caller_path, value)
        else:
            return value

    def _process_dict(self, path_list: list, d: dict):
        """Recursively process each key-value pair in the dictionary."""
        for k in list(d.keys()):
            d[k] = self._process_value(path_list + [k], d[k])
        return d

    def _process_sequence_items(self, path_list: list, seq):
        """Unified handler for list and tuple."""
        is_tuple = isinstance(seq, tuple)
        seq_list = list(seq)  # convert to list
        for i, val in enumerate(seq_list):
            seq_list[i] = self._process_value(path_list + [str(i)], val)
        return tuple(seq_list) if is_tuple else seq_list

    # ------------------------------------------------------------------
    #  重点改动：不对 'caller_path' 标记 InCircle，而只缓存结果
    # ------------------------------------------------------------------
    def _process_string(self, caller_path: str, s: str):
        """
        Resolve references in the string 's'.
        'caller_path' is just a label where this string is located.
        """
        # 如果这个字符串已经解析过，直接返回缓存
        if caller_path in self.circle:
            cached_value = self.circle[caller_path]
            if isinstance(cached_value, self.InCircle):
                # 这里表示该字符串本身还在处理中，但并不一定是循环
                # 通常若是完整引用的 target path == caller_path 才是循环
                # 对于 'a' -> 'b' 不应报错
                # 因简化起见，如果真的担心出现 a->a 的状况，可以再做特殊处理
                pass
            return cached_value

        # 暂不将 caller_path 标记为 InCircle，避免误报循环
        # 仅在结束时缓存解析结果

        # 1) 如果整段字符串是一个完整引用 (e.g. ${foo}$ or ${foo:default}$)
        full_val = self._process_full_reference(s)
        if full_val is not self.NotFound:
            # 缓存结果
            self.circle[caller_path] = full_val
            return full_val

        # 2) 否则处理部分引用
        partial_val = self._process_partial_references(s)
        self.circle[caller_path] = partial_val
        return partial_val

    def _process_full_reference(self, s: str):
        """If 's' is a full reference like ${...}$, resolve it; otherwise return NotFound."""
        match = self.FULL_REF_REGEX.fullmatch(s)
        if not match:
            return self.NotFound

        ref_str = match.group(1)
        return self._resolve_reference(ref_str)

    def _process_partial_references(self, s: str):
        """Handle zero or more partial references in the string (e.g. foo_${bar=3}_baz)."""
        spans = [m.span() for m in self.PARTIAL_REF_REGEX.finditer(s)]
        if not spans:
            return s  # no reference found

        result_parts = []
        pos = 0
        for start, end in spans:
            # text before ${...}
            result_parts.append(s[pos:start])

            ref_str = s[start + 2:end - 1]  # the content inside ${ }
            ref_val = self._resolve_reference(ref_str)

            # Convert the resolved value to string
            result_parts.append(str(ref_val))
            pos = end

        # remaining text
        result_parts.append(s[pos:])
        return ''.join(result_parts)

    # ------------------------------------------------------------------
    #  仅给 "目标路径" 打 InCircle 标记
    # ------------------------------------------------------------------
    def _resolve_reference(self, ref_str: str):
        """
        Resolve a reference that may contain :default, e.g. 'b:3'.
        We parse 'ref_path' and 'default_val', then try to get the real value.
        If 'ref_path' was not found or is truly in circle, fallback to default_val (if any).
        """
        path_part, default_val = self._parse_ref_path_and_default(ref_str)

        # 如果目标路径已在 InCircle，说明真正的循环
        if path_part in self.circle and isinstance(self.circle[path_part], self.InCircle):
            if default_val is not self.NoDefault:
                return default_val
            raise CircularReferenceError(f"Circular reference at path '{path_part}'")

        # 否则先将目标路径标记为 InCircle
        self.circle[path_part] = self.InCircle()

        try:
            val = self._get_value_by_path(path_part)
            # val 可能还是个字符串，继续处理
            val = self._process_value([], val)
            # 解析完成后缓存目标路径的结果
            self.circle[path_part] = val
            return val
        except (InvalidPathError, CircularReferenceError):
            # 如果有默认值，就返回默认值，否则抛出异常
            if default_val is not self.NoDefault:
                return default_val
            raise

    def _parse_ref_path_and_default(self, ref_str: str):
        """
        e.g. 'b:3' -> ('b', 3), 'b' -> ('b', None), 'b:hello' -> ('b', 'hello')
        """
        if ':' not in ref_str:
            return ref_str.strip(), self.NoDefault

        path_part, default_part = ref_str.split(':', 1)
        path_part = path_part.strip()
        default_part = default_part.strip()

        # 简单尝试转 int/float
        default_val = self._try_parse_scalar(default_part)
        return path_part, default_val

    def _try_parse_scalar(self, s: str):
        if s == 'true':
            return True
        if s == 'false':
            return False
        if s == 'null':
            return None

        try:
            return int(s)
        except ValueError:
            pass
        try:
            return float(s)
        except ValueError:
            pass
        return s

    def _get_value_by_path(self, dotted_path: str):
        """Traverse self.data according to a.b.0, etc."""
        parts = dotted_path.split('.')
        cur = self.data
        full_path_list = []

        for p in parts:
            full_path_list.append(p)
            path_str = '.'.join(full_path_list)

            if isinstance(cur, dict):
                if p not in cur:
                    raise InvalidPathError(f"Key '{p}' not found at '{path_str}' (full: '{dotted_path}')")
                cur = cur[p]
            elif isinstance(cur, (list, tuple)):
                # interpret p as index
                try:
                    idx = int(p)
                except ValueError:
                    raise InvalidPathError(f"Invalid index '{p}' at '{path_str}' (full: '{dotted_path}')")
                if idx < 0 or idx >= len(cur):
                    raise InvalidPathError(f"Index out of bounds '{p}' at '{path_str}' (full: '{dotted_path}')")
                cur = cur[idx]
            else:
                raise InvalidPathError(
                    f"Cannot access '{p}' in a scalar/string at '{path_str}' (full: '{dotted_path}')")

            # 如果拿到的值还是字符串，可能是个完整引用
            cur = self._resolve_or_break(cur, path_str)

        return cur

    def _resolve_or_break(self, val, path_str: str):
        """
        If 'val' is a full-reference string, resolve it right away.
        If not a full reference, return as is.
        """
        while isinstance(val, str):
            match = self.FULL_REF_REGEX.fullmatch(val)
            if not match:
                break
            new_ref_str = match.group(1)
            val = self._resolve_reference(new_ref_str)
        return val


def parse(data: dict):
    """
    Convenient standalone function that returns the resolved structure.
    """
    resolver = DictReferenceResolver(data)
    return resolver.resolve()


# -------------------------
#         Usage Demo
# -------------------------
if __name__ == '__main__':
    # 1) 没有真正循环的互相引用
    #    'a' references 'b', but 'b' is just a scalar
    d1 = {
        'a': '${b}$',
        'b': '123',
    }
    print(parse(d1))  # Expect: {'a': '123', 'b': '123'}

    # 2) 真正的循环
    d2 = {
        'x': '${y}$',
        'y': '${x}$',
    }
    try:
        print(parse(d2))
    except CircularReferenceError as e:
        print("Caught a CircularReferenceError:", e)

    # 3) 带默认值
    d3 = {
        'a': '${b:null}$'
    }
    print(parse(d3))  # {'a': 999} because b not found

    # 4) 部分引用 + 默认值
    d4 = {
        'foo': 'Hello_${bar:World}_!'
    }
    print(parse(d4))  # "Hello_World_!"

    # 5) 真循环 + 默认值
    d5 = {
        'a': '${b:true}$',
        'b': '${a:defaultB}$'
    }
    print(parse(d5))  # {'a': 'defaultA', 'b': 'defaultB'}
