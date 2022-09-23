import ctypes
import functools
from typing import Any, Generic, Type, TypeVar, cast

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
        struct = _get_struct_type(cls)
        struct_fields = {field[0] for field in struct._fields_}
        for field in struct_fields:
            if field not in cls.__annotations__:
                raise TypeError(
                    f"Struct field {field} not annotated in {cls.__name__}",
                )
            # TODO: Validate types
            setattr(cls, field, FieldProxy(field))

    def as_ref(self) -> Any:
        return ctypes.byref(self._struct)


def _get_struct_type(cls: Type[StructProxy[St]]) -> Type[St]:
    # TODO: Support multiple inheritence
    return cls.__orig_bases__[0].__args__[0]  # type: ignore
