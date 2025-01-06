import re
from typing import Any


class CircularReferenceError(ReferenceError):
    """Raised when a circular reference is detected."""
    pass


############################################
# 1) Regex to specifically determine if the entire string is a reference
############################################
FULL_REF_PATTERN = re.compile(
    r'^('  # Start capturing group
    r'\${([^}:]+(?:\.[^}:]+)*)(?::([^}]+))?}'  # \${ ref_path : default? }
    r'(\$)?'  # Optional trailing $
    r'|'  # OR
    r'\$([^$:]+(?:\.[^$:]+)*)(?::([^$]+))?\$'  # \$ ref_path : default? \$
    r')$'  # End capturing group
)

############################################
# 2) Regex for "partial replacement"
#    Matches all sub-references within the text
############################################
PARTIAL_REF_PATTERN = re.compile(
    r'(\${([^}:]+(?:\.[^}:]+)*)(?::([^}]+))?})'
    r'|(\$([^$:]+(?:\.[^$:]+)*)(?::([^$]+))?\$)'
)


def parse(data: Any) -> Any:
    """
    Parses internal references within any data structure (dict, list, or scalar).
    Returns a new structure with all references resolved. Raises CircularReferenceError on circular references.
    """
    return _resolve(data, data, resolving_refs=set(), path="<root>")


def _resolve(
        node: Any,
        root_data: Any,
        resolving_refs: set,
        path: str
) -> Any:
    """Recursively resolves references within the node."""
    if isinstance(node, dict):
        resolved = {}
        for k, v in node.items():
            resolved_key = _resolve_string(k, root_data, resolving_refs, f"{path}.<key>")
            child_path = f"{path}.{k}"
            resolved[resolved_key] = _resolve(v, root_data, resolving_refs, child_path)
        return resolved

    elif isinstance(node, list):
        resolved_list = []
        for i, item in enumerate(node):
            child_path = f"{path}[{i}]"
            resolved_list.append(_resolve(item, root_data, resolving_refs, child_path))
        return resolved_list

    elif isinstance(node, str):
        return _resolve_string(node, root_data, resolving_refs, path)

    else:
        # int / float / bool / None / ...
        return node


def _resolve_string(
        text: str,
        root_data: Any,
        resolving_refs: set,
        path: str,
) -> Any:
    """
    Determines if the entire string is a "full reference" (with an optional `$`).
    If so, returns the resolved original type (e.g., int).
    Otherwise, treats it as a string with partial references and performs in-place replacements, returning a string.
    """
    # 1) First, check if FULL_REF_PATTERN matches the entire string
    m_full = FULL_REF_PATTERN.match(text)
    if m_full:
        # If the entire string is a complete reference
        # Group order as per FULL_REF_PATTERN
        ref_path_curly = m_full.group(2)  # Internal path within \${...}
        default_curly = m_full.group(3)    # \${...:default}
        trailing_dollar = m_full.group(4)  # Optional trailing $
        ref_path_dollar = m_full.group(5)  # Internal path within $...$
        default_dollar = m_full.group(6)    # $...:default$

        if ref_path_curly is not None:
            ref_path = ref_path_curly
            default_value = default_curly
        else:
            ref_path = ref_path_dollar
            default_value = default_dollar

        return _lookup_ref(ref_path, default_value, root_data, resolving_refs, path)

    # 2) Otherwise, perform "partial replacement"
    matches = list(PARTIAL_REF_PATTERN.finditer(text))
    if not matches:
        return text  # No references found, return as-is

    result_parts = []
    last_end = 0
    for m in matches:
        start_idx = m.start()
        end_idx = m.end()
        # Add the original text before this reference
        result_parts.append(text[last_end:start_idx])

        # group(2) = internal path within \${path}
        # group(3) = default within \${path:default}
        # group(5) = internal path within $path$
        # group(6) = default within $path:default$
        if m.group(1):  # \${...} form
            ref_path = m.group(2)
            default_value = m.group(3)
        else:  # $...$ form
            ref_path = m.group(5)
            default_value = m.group(6)

        ref_value = _lookup_ref(ref_path, default_value, root_data, resolving_refs, path)
        # Treat partial replacements as string concatenation
        result_parts.append(str(ref_value))

        last_end = end_idx

    # Add the remaining text after the last reference
    result_parts.append(text[last_end:])

    return "".join(result_parts)



def _lookup_ref(
        ref_path: str,
        default_value: str,
        root_data: Any,
        resolving_refs: set,
        path: str,
) -> Any:
    """
    Given a path like "a.x.y" or "my_list.0", retrieves the corresponding value from root_data.
    Supports:
      - Dict key access
      - List index access (if the segment k is purely numeric, it is converted to int for indexing)
      - Custom classes implementing the __getitem__ method
    If the key/index is not found and a default_value exists, uses the default_value.
    If not found and no default is provided, raises ReferenceError.
    Also checks for circular references.

    New Features:
      - Automatically parses the type of default values
      - Supports more types of indexing
    """
    # Check if this ref_path is already being resolved to prevent circular references
    if ref_path in resolving_refs:
        raise CircularReferenceError(f"Circular reference detected: '{ref_path}' is being referenced again in path '{path}'.")

    resolving_refs.add(ref_path)

    current_value = root_data
    subkeys = ref_path.split(".") if ref_path else []
    try:
        for k in subkeys:
            # If current_value is a list and k is purely numeric, convert to int index
            if isinstance(current_value, list):
                try:
                    idx = int(k)
                except ValueError:
                    raise TypeError(f"Index '{k}' is not an integer and cannot be used for list.")
                current_value = current_value[idx]
                continue

            try:
                current_value = current_value[k]
            except (KeyError, IndexError, TypeError, AttributeError, ValueError) as e:
                # If key/index access fails, try using getattr for attribute access
                try:
                    current_value = getattr(current_value, k)
                except AttributeError:
                    raise KeyError(k) from e
    except (KeyError, IndexError, TypeError):
        # If index out of range or key doesn't exist, use default_value if provided, else raise error
        if default_value is not None:
            # default_value might contain references and needs to be resolved
            resolved_default = _resolve(default_value, root_data, resolving_refs, f"{path}(default)")
            # Attempt to automatically parse the type of default_value
            resolved_default = _parse_default_value(resolved_default)
            resolving_refs.remove(ref_path)
            return resolved_default
        else:
            resolving_refs.remove(ref_path)
            raise ReferenceError(f"Reference '{ref_path}' not found in path '{path}'.")

    # If current_value is found, perform another resolve in case it contains references
    resolved_value = _resolve(current_value, root_data, resolving_refs, f"{path}.{ref_path}")

    resolving_refs.remove(ref_path)
    return resolved_value


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


if __name__ == '__main__':
    d = dict(
        x=1,
        y='${x}x',
    )
    d['z${y}'] = 3
    print(parse(d))  # {'x': 1, 'y': '1x', 'z1x': 3}
