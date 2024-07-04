import contextlib
import ctypes
import dataclasses
import inspect
import types
import typing as t
from pathlib import Path
from weakref import WeakValueDictionary

T = t.TypeVar("T")

# Based on https://docs.python.org/3/library/ctypes.html#fundamental-data-types
Bool = t.Annotated[bool, ctypes.c_bool]
Char = t.Annotated[bytes, ctypes.c_char]
Wchar = t.Annotated[str, ctypes.c_wchar]
Byte = t.Annotated[int, ctypes.c_byte]
Ubyte = t.Annotated[int, ctypes.c_ubyte]
Short = t.Annotated[int, ctypes.c_short]
Ushort = t.Annotated[int, ctypes.c_ushort]
Int = t.Annotated[int, ctypes.c_int]
Uint = t.Annotated[int, ctypes.c_uint]
Long = t.Annotated[int, ctypes.c_long]
Ulong = t.Annotated[int, ctypes.c_ulong]
LongLong = t.Annotated[int, ctypes.c_longlong]
UlongLong = t.Annotated[int, ctypes.c_ulonglong]
Int8 = t.Annotated[int, ctypes.c_int8]
Uint8 = t.Annotated[int, ctypes.c_uint8]
Int16 = t.Annotated[int, ctypes.c_int16]
Uint16 = t.Annotated[int, ctypes.c_uint16]
Int32 = t.Annotated[int, ctypes.c_int32]
Uint32 = t.Annotated[int, ctypes.c_uint32]
Int64 = t.Annotated[int, ctypes.c_int64]
Uint64 = t.Annotated[int, ctypes.c_uint64]
SizeT = t.Annotated[int, ctypes.c_size_t]
SsizeT = t.Annotated[int, ctypes.c_ssize_t]
Float = t.Annotated[float, ctypes.c_float]
Double = t.Annotated[float, ctypes.c_double]
LongDouble = t.Annotated[float, ctypes.c_longdouble]
CharPointer = t.Annotated[bytes | None, ctypes.c_char_p]
WcharPointer = t.Annotated[str | None, ctypes.c_wchar_p]
VoidPointer = t.Annotated[int | None, ctypes.c_void_p]


def cdll_from_spec(path: Path, spec: type[T]) -> T:
    # The given spec must be a class
    assert inspect.isclass(spec)

    # Find all methods that non-internal methods
    spec_funcs = [
        type_
        for name, type_ in inspect.getmembers(spec)
        if not name.startswith("__") and inspect.isfunction(type_)
    ]

    # There has to be at least one function in the spec, or it's likely an error
    assert spec_funcs

    lib = ctypes.CDLL(t.cast(str, path))
    for spec_func in spec_funcs:
        # Inspect the signature of the spec function
        sig = inspect.signature(spec_func)

        # Apply the types to the lib's function
        lib_func = getattr(lib, spec_func.__name__)
        lib_func.argtypes = [
            CTypeAnnotation.from_annotated_type(p.annotation).c_type
            for p in sig.parameters.values()
        ]
        if sig.return_annotation is not sig.empty:
            lib_func.restype = CTypeAnnotation.from_annotated_type(
                sig.return_annotation
            ).c_type
        else:
            lib_func.restype = None

    return t.cast(T, lib)


@dataclasses.dataclass(frozen=True)
class CTypeAnnotation:
    py_type: type[t.Any] | None
    c_type: type[t.Any] | None

    @classmethod
    def from_annotated_type(cls, type_: t.Any) -> t.Self:
        if type_ is None:
            return cls(None, None)

        # We need this hack so StructPointer isn't interpreted as a catch all
        ns = types.SimpleNamespace()
        ns.StructPointer = StructPointer

        origin = t.get_origin(type_)
        match origin:
            case t.Annotated:
                try:
                    (c_type,) = type_.__metadata__
                    return cls(type_.__origin__, c_type)
                except (AttributeError, IndexError):
                    raise TypeError(
                        "Type must be a Python type annotated with a ctype, got "
                        f"{type_!r}"
                    ) from None
            case ns.StructPointer:
                return cls(type_.__args__[0], ctypes.c_void_p)
            case _ if issubclass(type_, CStruct):
                return cls(type_, type_._struct_cls)  # pyright: ignore[reportPrivateUsage]
            case _:
                raise TypeError(f"Invalid type annotation for C type, got {type_!r}")


class _CstructProxyScalarField:
    name: str

    def __init__(self, name: str) -> None:
        self.name = name

    def __get__(self, instance: t.Any, owner: type[t.Any] | None = None) -> t.Any:
        return getattr(instance._struct, self.name)

    def __set__(self, instance: t.Any, value: t.Any) -> None:
        setattr(instance._struct, self.name, value)


class _CstructProxyStructField:
    name: str
    proxy_cls: t.Any
    refs: WeakValueDictionary[int, t.Any]

    def __init__(self, name: str, proxy_cls: t.Any) -> None:
        self.name = name
        self.proxy_cls = proxy_cls
        self.refs = WeakValueDictionary()

    def __get__(self, instance: t.Any, owner: type[t.Any] | None = None) -> t.Any:
        oid = id(instance)
        try:
            return self.refs[oid]
        except KeyError:
            proxy = self.proxy_cls.from_struct(getattr(instance._struct, self.name))
            self.refs[oid] = proxy
            return proxy

    def __set__(self, instance: t.Any, value: t.Any) -> None:
        setattr(instance._struct, self.name, value._struct)


@t.dataclass_transform()
class CStruct:
    _struct_cls: "t.ClassVar[type[RawStruct[t.Self]]]"
    _struct: "RawStruct[t.Self]"

    def __init_subclass__(
        cls,
        *,
        pack: bool = False,
        little_endian: bool | None = None,
    ) -> None:
        base_cls: type[ctypes.Structure]
        match little_endian:
            case None:
                base_cls = ctypes.Structure
            case True:
                base_cls = ctypes.LittleEndianStructure
            case False:
                base_cls = ctypes.BigEndianStructure

        defaults: dict[str, t.Any] = {}
        fields = list[tuple[str, type[t.Any]]]()
        for attr, type_ in t.get_type_hints(cls, include_extras=True).items():
            if attr in {"_struct_cls", "_struct"}:
                continue

            annotation = CTypeAnnotation.from_annotated_type(type_)

            if annotation.py_type is None or annotation.c_type is None:
                raise TypeError(f"{attr} must not be of type None")

            # Save the default value if it was defined
            with contextlib.suppress(AttributeError):
                defaults[attr] = getattr(cls, attr)

            if issubclass(annotation.py_type, CStruct):
                setattr(cls, attr, _CstructProxyStructField(attr, annotation.py_type))
            else:
                setattr(cls, attr, _CstructProxyScalarField(attr))
            fields.append((attr, annotation.c_type))

        cls._struct_cls = t.cast(  # type: ignore # mypy
            type[RawStruct[t.Self]],
            type(
                f"_{cls.__name__}_ctypes_struct",
                (base_cls,),
                {
                    "_pack_": pack,
                    "_fields_": list(fields),
                },
            ),
        )

        def __init__(self: CStruct, *args: t.Any, **kwargs: t.Any) -> None:  # noqa: N807
            self._struct = self._struct_cls()  # type: ignore # pyright

            if len(args) > len(fields):
                raise TypeError(
                    f"{self.__class__.__name__}() takes {len(fields)} positional "
                    f"argument{'s' if len(fields) > 1 else ''} but {len(args)} were "
                    "given"
                )

            for attr, value in defaults.items():
                setattr(self, attr, value)

            used_args = set[str]()
            for arg, (attr, _) in zip(args, fields, strict=False):
                used_args.add(attr)
                setattr(self, attr, arg)

            available_attrs = {attr for attr, _ in fields}
            for attr, value in kwargs.items():
                if attr in used_args:
                    raise TypeError(
                        f"{self.__class__.__name__}() got multiple values for argument "
                        f"{attr!r}"
                    )
                if attr not in available_attrs:
                    raise TypeError(
                        f"{self.__class__.__name__}() got an unexpected keyword "
                        f"argument {attr!r}"
                    )
                setattr(self, attr, value)

        def __repr__(self: CStruct) -> str:  # noqa: N807
            fields_repr = [f"{attr}={getattr(self, attr)!r}" for attr, _ in fields]
            return f"{self.__class__.__name__}({', '.join(fields_repr)})"

        cls.__init__ = __init__  # type: ignore
        cls.__repr__ = __repr__  # type: ignore

    @classmethod
    def zeroed(cls) -> t.Self:
        """Return an instance of this struct where all values are zero"""
        return cls.from_struct(cls._struct_cls())  # type: ignore # mypy

    @classmethod
    def sizeof(cls) -> int:
        """Equivalent to calling ctypes.sizeof for the underlying struct"""
        return ctypes.sizeof(cls._struct_cls)

    @classmethod
    def from_struct(cls, struct: "RawStruct[t.Self]") -> t.Self:
        """
        Create an instance of this struct using, backed by the given struct instance.

        If the given struct is not the same as the expected one a TypeError is raised.
        """
        if not isinstance(struct, cls._struct_cls):
            raise TypeError(f"Expected {cls._struct_cls}, got {type(struct)}")

        rv = cls.__new__(cls)
        rv._struct = struct
        return rv

    def struct(self) -> "RawStruct[t.Self]":
        return self._struct  # type: ignore

    def byref_raw(self) -> t.Any:
        return ctypes.byref(self._struct)  # type: ignore

    def byref(self) -> "StructPointer[t.Self]":
        return self.byref_raw()  # type: ignore

    def __eq__(self, other: object) -> bool:
        if isinstance(other, self.__class__):
            return self._struct == other._struct
        return NotImplemented

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)


T_struct = t.TypeVar("T_struct", bound=CStruct)


class RawStruct(t.Generic[T], ctypes.Structure):
    """
    A type annotation struct that is used to represent a raw ctypes.Structure in a way
    that's typed for the CStruct. This allows us to ensure that the correct raw struct
    is passed.
    """


class StructPointer(t.Generic[T_struct]):
    """
    A type annotation struct that is used to represent when a pointer is expected in an
    FFI function call.
    """
