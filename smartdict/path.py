class Path:
    def __init__(self, path=None):
        self._path = path or []

    def __truediv__(self, other):
        if isinstance(other, str):
            return Path(self._path.copy() + [other])
        if isinstance(other, Path):
            return Path(self._path.copy() + other._path.copy())
        raise TypeError(f'Path `/` operation get unexpected type {type(other)}')

    def __call__(self):
        return '→'.join(self._path)

    def __len__(self):
        return len(self._path)

    def __str__(self):
        path = list(map(lambda x: f'{x}', self._path))
        return ' → '.join(path)
