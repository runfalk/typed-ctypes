import ctypes
import functools
from typing import Any, Dict, Generic, Optional, Type, TypeVar, cast

St = TypeVar("St", bound=ctypes.Structure)


# From https://docs.python.org/3/library/ctypes.html#fundamental-data-types
_COMPATIBLE_TYPES: Dict[Type[Any], Type[Any]] = {
    ctypes.c_bool: bool,
    ctypes.c_char: bytes,
    ctypes.c_wchar: str,
    ctypes.c_byte: int,
    ctypes.c_ubyte: int,
    ctypes.c_short: int,
    ctypes.c_ushort: int,
    ctypes.c_int: int,
    ctypes.c_uint: int,
    ctypes.c_long: int,
    ctypes.c_ulong: int,
    ctypes.c_longlong: int,
    ctypes.c_ulonglong: int,
    ctypes.c_int8: int,
    ctypes.c_uint8: int,
    ctypes.c_int16: int,
    ctypes.c_uint16: int,
    ctypes.c_int32: int,
    ctypes.c_uint32: int,
    ctypes.c_int64: int,
    ctypes.c_uint64: int,
    ctypes.c_size_t: int,
    ctypes.c_ssize_t: int,
    ctypes.c_float: float,
    ctypes.c_double: float,
    ctypes.c_longdouble: float,
    ctypes.c_char_p: Optional[bytes],  # type: ignore
    ctypes.c_wchar_p: Optional[str],  # type: ignore
    ctypes.c_void_p: Optional[int],  # type: ignore
}


class FieldProxy:
    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name

    def __get__(self, obj: Any, cls: Type[Any]) -> Any:
        return getattr(obj._struct, self.name)

    def __set__(self, obj: Any, value: Any) -> None:
        setattr(obj._struct, self.name, value)


class StructProxy(Generic[St]):
    _struct: St

    def __init__(self) -> None:
        struct = _get_struct_type(self.__class__)
        self._struct = struct()

    def __init_subclass__(cls) -> None:
        proxy_cls = _find_proxy_class(cls)
        if proxy_cls is None:
            raise TypeError(
                f"The class {cls.__name__} doesn't inherit from StructProxy",
            )

        struct = _get_struct_type(cls)
        struct_fields = {field[0]: field[1] for field in struct._fields_}
        for field, field_ctype in struct_fields.items():
            annotated_type = proxy_cls.__annotations__.get(field)
            if annotated_type is None:
                raise TypeError(
                    f"Struct field {field} not annotated in {proxy_cls.__name__}",
                )

            expected_type = _COMPATIBLE_TYPES.get(field_ctype)
            if expected_type is None:
                raise TypeError(
                    (
                        f"Struct {struct.__name__} has an invalid field type for "
                        f"field {field}"
                    ),
                )

            if annotated_type != expected_type:
                raise TypeError(
                    (
                        f"Proxy class {proxy_cls.__name__} has invalid type for field "
                        f"{field}, expected {expected_type.__name__} (got "
                        f"{annotated_type.__name__})"
                    ),
                )

            setattr(cls, field, FieldProxy(field))

    def as_ref(self) -> Any:
        return ctypes.byref(self._struct)


def _find_proxy_class(cls: Type[StructProxy[St]]) -> Optional[Type[StructProxy[St]]]:
    if StructProxy in cls.__bases__:
        return cls

    # Traverse the class hierarchy depth first to find the correct class
    for parent in cls.__bases__:
        x: Optional[Type[StructProxy[St]]] = _find_proxy_class(parent)
        if x is not None:
            return x
    return None


def _get_struct_type(cls: Type[StructProxy[St]]) -> Type[St]:
    for base_cls in getattr(cls, "__orig_bases__", []):
        origin: Optional[Type[Any]] = getattr(base_cls, "__origin__", None)
        if origin is StructProxy:
            return base_cls.__args__[0]  # type: ignore
    raise TypeError("Unable to find StructProxy in the inheritance hierarchy")
