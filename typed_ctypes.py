import ctypes
import functools
from typing import Any, Generic, Optional, Type, TypeVar, cast

St = TypeVar("St", bound=ctypes.Structure)


_COMPATIBLE_TYPES = {
    ctypes.c_uint32: {int},
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
        struct_fields = {field[0] for field in struct._fields_}
        for field in struct_fields:
            if field not in proxy_cls.__annotations__:
                raise TypeError(
                    f"Struct field {field} not annotated in {proxy_cls.__name__}",
                )
            # TODO: Validate types
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
