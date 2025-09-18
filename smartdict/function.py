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


def parse_ref_string(s: str) -> list[Part]:
    parts = []
    i = 0
    n = len(s)

    while i < n:
        if s[i:i + 2] == '${':  # 进入引用
            depth = 1
            j = i + 2
            while j < n and depth > 0:
                if s[j:j + 2] == '${':
                    depth += 1
                    j += 2
                elif s[j] == '}':
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
