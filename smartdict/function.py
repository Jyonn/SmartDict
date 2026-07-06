class Part:
    def __init__(self, part: str, full: bool = False, partial: bool = False):
        self.part = part
        self.full = full
        self.partial = partial

    def __call__(self):
        if self.full:
            return '${' + self.part + '}$'
        if self.partial:
            return '${' + self.part + '}'
        return self.part


def _scan_top_level_delimiter(s: str, delimiter: str):
    depth = 0
    brace_depth = 0
    quote_char = None
    escaped = False
    i = 0
    n = len(s)

    while i < n:
        if quote_char is not None:
            if escaped:
                escaped = False
            elif s[i] == '\\':
                escaped = True
            elif s[i] == quote_char:
                quote_char = None
            i += 1
            continue

        if s[i] in ('"', "'"):
            quote_char = s[i]
            i += 1
        elif s[i:i + 2] == '${':
            depth += 1
            i += 2
        elif s[i] == '{':
            brace_depth += 1
            i += 1
        elif s[i] == '}':
            if brace_depth > 0:
                brace_depth -= 1
            elif depth > 0:
                depth -= 1
            i += 1
        elif s[i] == delimiter and depth == 0 and brace_depth == 0:
            return i
        else:
            i += 1

    return -1


def split_top_level_once(s: str, delimiter: str):
    idx = _scan_top_level_delimiter(s, delimiter)
    if idx == -1:
        return s, None
    return s[:idx], s[idx + 1:]


def split_top_level(s: str, delimiter: str) -> list[str]:
    parts = []
    rest = s
    while True:
        head, tail = split_top_level_once(rest, delimiter)
        parts.append(head)
        if tail is None:
            return parts
        rest = tail


def parse_ref_string(s: str) -> list[Part]:
    parts = []
    i = 0
    n = len(s)

    while i < n:
        if s[i:i + 2] == '${':  # 进入引用
            depth = 1
            brace_depth = 0
            quote_char = None
            escaped = False
            j = i + 2
            while j < n and depth > 0:
                if quote_char is not None:
                    if escaped:
                        escaped = False
                    elif s[j] == '\\':
                        escaped = True
                    elif s[j] == quote_char:
                        quote_char = None
                    j += 1
                    continue

                if s[j] in ('"', "'"):
                    quote_char = s[j]
                    j += 1
                elif s[j:j + 2] == '${':
                    depth += 1
                    j += 2
                elif s[j] == '{':
                    brace_depth += 1
                    j += 1
                elif s[j] == '}':
                    if brace_depth > 0:
                        brace_depth -= 1
                        j += 1
                    else:
                        depth -= 1
                        j += 1
                else:
                    j += 1
            if depth != 0:
                raise ValueError(f"Unmatched braces in: {s}")
            expr = s[i + 2:j - 1]  # 提取 ${ ... }

            # full 的严格条件：整个字符串是 ${...}$
            if i == 0 and j == n - 1 and s.endswith('$'):
                parts.append(Part(expr, full=True))
                return parts  # 整个字符串就是 full，直接返回
            else:
                parts.append(Part(expr, partial=True))
            i = j
        else:
            # 普通文本
            start = i
            while i < n and s[i:i + 2] != '${':
                i += 1
            parts.append(Part(s[start:i]))
    return parts
