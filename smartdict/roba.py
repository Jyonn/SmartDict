import re

from oba.oba import raw, NotFound, iterable, Obj


pattern = re.compile(r"\$\{[^}]+}|[^.]+")

def re_split(s: str):
    tokens = pattern.findall(s)
    if len(tokens) > 1:
        tokens = [tokens[0], '.'.join(tokens[1:])]
    return tokens


class Roba(Obj):
    def __init__(self, object_=None, path=None):
        super().__init__(object_, path)

    def __getitem__(self, key):
        if isinstance(key, str):
            key = re_split(key)

        index = key[0] if isinstance(key, list) else key

        # noinspection PyBroadException
        try:
            value = self.__obj__.__getitem__(index)
        except Exception:
            return NotFound(path=self.__path__ / index)
        if iterable(value):
            value = Roba(value, path=self.__path__ / str(key))

        if isinstance(key, list) and len(key) > 1:
            value = value[key[1]]
        return value

    def __setitem__(self, key: str, value):
        key = re_split(key)
        print(key,)

        if len(key) == 1:
            obj = raw(self)
            obj[key[0]] = value
        else:
            print('here')
            print(type(self[key[0]]))
            self[key[0]][key[1]] = value

    def __str__(self):
        return 'Soba()'
