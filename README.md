Typed ctypes
============
This project improves type support for Python's
[ctypes.Structure](https://docs.python.org/3/library/ctypes.html#ctypes.Structure).
The standard type definition for this doesn't flag when the user tries to access
a missing property. This is because the default type definitions rely on
`__getattr__` and the type checker doesn't know how to interpret the `_fields_`
property.

Example
-------
```python
import ctypes
from typed_ctypes import StructProxy

class Struct(ctypes.Structure):
    _fields_ = [
        ("uint", ctypes.c_uint32),
        ("char", ctypes.c_uint8),
    ]

class Proxy(StructProxy[Struct]):
    uint: int
    char: int

s = Struct()
s.uint = 1
print(s.uint)  # Prints 1
s.missing  # Throws attribute error, and gets caught by any type checker
```
