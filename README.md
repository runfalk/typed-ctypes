Typed ctypes
============
This project improves type support for Python's
[ctypes.Structure](https://docs.python.org/3/library/ctypes.html#ctypes.Structure).
The standard type definition for this doesn't flag when the user tries to access
a missing property.

```python
import ctypes

class Struct(ctypes.Structure):
    _fields_ = [("field", ctypes.c_uint32)]

s = Struct()
print(s.missing)  # Not caught by type checkers
```

This is because the default type definitions rely on
`__getattr__` and the type checker doesn't know how to interpret the `_fields_`
property. The [ctypes.Structure type definition[^1] in Python looks something
like this:

```python
# ctypes module (simplified for easier reading)
class Structure:
    def __init__(self, *args: Any, **kw: Any) -> None:
        ...

    # To a type checker this means that any field can be accessed
    def __getattr__(self, name: str) -> Any:
        ...

    def __setattr__(self, name: str, value: Any) -> None:
        ...
```

Example
-------
```python
from typed_ctypes import CStruct, Uint32, Uint8

class Struct(CStruct):
    uint: Uint32
    char: Uint8

s = Struct()
s.uint = 1
print(s.uint)  # Prints 1
s.missing  # Throws attribute error, and gets caught by any type checker
```

Known issues
------------
It's not possible to statically ensure that the attribute types can be
understood by this library. This happens at runtime:

```python
from typed_ctypes import CStruct

class Struct(CStruct):
    invalid: int  # Raises TypeError
```

This is fine most of the time since you don't generate struct inside of
functions. Therefore you would catch it when you start the application or the
test suite.

Enums are a bit awkward to work with. The recommended implementation for now is:

```python
from enum import IntEnum
from typed_ctypes import CStruct, Int32

class State:
    Unknown = 0
    Open = 1
    Closed = 2


class Struct(CStruct):
    _state: Int32

    @property
    def state(self) -> State:
        return State(self._state)

    @state.setter
    def state(self, state: State) -> None:
        self._state = state.value


[^1]: https://github.com/python/typeshed/blob/a702daa6311db14db603827cd649fcfab15f8f53/stdlib/ctypes/__init__.pyi#L248
