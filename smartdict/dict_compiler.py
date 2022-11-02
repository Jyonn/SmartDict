import copy
import re


class CircleDict:
    def __init__(self):
        self.d = {}

    def __getitem__(self, item):
        return self.d[item]

    def __setitem__(self, key, value):
        self.d[key] = value

    def __contains__(self, item):
        return item in self.d


class DictCompiler:
    p = re.compile('\\${(.*?)}')
    pf = re.compile('\\${(.*?)}\\$')

    class InCircle:
        pass

    class NotFound:
        pass

    def __init__(self, d: dict):
        self.d = copy.deepcopy(d)
        self.circle = CircleDict()

    def parse(self):
        return self._process([], self.d)

    def _get_value(self, path: str):
        path = path.split('.')
        present_path = []
        v = self.d
        for k in path:
            present_path.append(k)
            present_path_str = '.'.join(present_path)

            if isinstance(v, list) or isinstance(v, tuple):
                k = int(k)
                if len(v) < k:
                    raise KeyError(f'array out of bound (index = {k}) when retrieving value where path is {present_path} of {path}')
            elif isinstance(v, dict):
                if k not in v:
                    raise KeyError(f'key ({k}) not exist when retrieving value where path is {present_path} of {path}')
            elif isinstance(v, str):
                raise KeyError(f'key ({k}) not exist when retrieving value where path is {present_path} of {path}')

            v = v[k]

            while isinstance(v, str):
                full_match_value = self._process_full_ref('.'.join(present_path), v)
                if full_match_value is self.NotFound:
                    break
                v = full_match_value
        return v

    @classmethod
    def _get_refs(cls, s: str):
        refs = []
        for match in cls.p.finditer(s):
            refs.append(match.span())
        return refs

    def _parse(self, s: str, refs: list):
        paths = []
        for ref in refs:
            paths.append(s[ref[0] + 2: ref[1] - 1])
        values = [self._get_value(path) for path in paths]
        return zip(refs, paths, values)

    def _process(self, path: list, v):
        if isinstance(v, dict):
            return self._process_dict(path, v)
        if isinstance(v, list):
            return self._process_list(path, v)
        if isinstance(v, tuple):
            return self._process_tuple(path, v)
        if isinstance(v, str):
            return self._process_item('.'.join(path), v)
        return v

    def _process_full_ref(self, path: str, s: str):
        match = self.pf.fullmatch(s)
        if not match:
            return self.NotFound

        full_ref = match.group(1)
        self.circle[path] = self.InCircle()
        value = self._get_value(full_ref)
        value = self._process(path.split('.'), value)
        self.circle[path] = value
        return value

    def _process_item(self, path: str, s: str):
        if not isinstance(s, str):
            return s

        if path in self.circle:
            v = self.circle[path]
            if isinstance(v, self.InCircle):
                raise ValueError('Dict references are in circle')
            return v

        full_value = self._process_full_ref(path, s)
        if full_value is not self.NotFound:
            return full_value

        refs = self._get_refs(s)
        if not refs:
            return s

        self.circle[path] = self.InCircle()
        parsed_s = []
        position = 0
        for r, p, v in self._parse(s, refs):
            v = self._process_item(p, v)
            parsed_s.append(s[position: r[0]])
            parsed_s.append(str(v))
            position = r[1]
        parsed_s.append(s[refs[-1][1]:])
        parsed_s = ''.join(parsed_s)
        self.circle[path] = parsed_s
        return parsed_s

    def _process_list(self, path: list, l: list):
        new_l = []
        for i, v in enumerate(l):
            new_l.append(self._process([*path, str(i)], v))
        return new_l

    def _process_tuple(self, path: list, t: tuple):
        return tuple(self._process_list(path, list(t)))

    def _process_dict(self, path: list, d: dict):
        for k in d:
            d[k] = self._process([*path, k], d[k])
        return d


def parse(d: dict):
    compiler = DictCompiler(d)
    return compiler.parse()


if __name__ == '__main__':
    d = dict(
        a='${b.v.1}+1',
        b='${c}$',
        c=dict(
            __l=23,
            v=('sorry', 'good', 'ok'),
            m='${c.__l}'
        )
    )
    # d = [1,2,'${0}$']

    rd = DictCompiler(d)
    print(rd.parse())
