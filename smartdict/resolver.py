from typing import Any, Dict, Union


class RefStringStatus:
    RESOLVING = object()
    UNRESOLVED = object()
    RESOLVED = object()
    NOTFOUND = object()

    UNSET_VALUE = object()

    def __init__(self, ref_string):
        self.ref_string = ref_string

        self.status = self.RESOLVING
        self.value = self.UNSET_VALUE

    @property
    def is_resolved(self):
        return self.status == self.RESOLVED

    @property
    def is_unresolved(self):
        return self.status == self.UNRESOLVED

    @property
    def is_resolving(self):
        return self.status == self.RESOLVING

    def resolve(self, value):
        self.status = self.RESOLVED
        self.value = value
        return self

    def unresolve(self):
        self.status = self.UNRESOLVED
        return self

    @property
    def has_value(self):
        return self.value != self.UNSET_VALUE

    def __str__(self):
        value = self.value if self.has_value else '<UNSET>'
        return f'{self.ref_string} → {value}'

    def __repr__(self):
        return str(self)


class RefStringStatusWithValue:
    def __init__(self, status: RefStringStatus, value: Any = RefStringStatus.UNSET_VALUE):
        self.status = status
        self.value = value

        if status.is_resolved:
            self.value = status.value

    @property
    def is_unset(self):
        return self.value == RefStringStatus.UNSET_VALUE


class ComponentWithValue:
    def __init__(self, path):
        super().__init__()
        self.path = str(path)
        self.unresolved = {}  # type: Dict[Any, Union[RefStringStatus, ComponentWithValue]]
        self.final = None

    def push(self, ref_value: RefStringStatusWithValue):
        if ref_value.is_unset:
            self.unresolved[ref_value.status.ref_string] = ref_value.status
        return self

    def list_push(self, index, component_value: 'ComponentWithValue'):
        if component_value.has_unresolved:
            self.unresolved[str(index)] = component_value
        return self

    def dict_push(self, key, component_value: 'ComponentWithValue'):
        if component_value.has_unresolved:
            self.unresolved[key] = component_value
        return self

    def finalize(self, obj):
        self.final = obj
        return self

    @property
    def has_unresolved(self):
        return len(self.unresolved) > 0
