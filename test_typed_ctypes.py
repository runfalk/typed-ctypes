import ctypes
import typing as t
from pathlib import Path

import pytest

from typed_ctypes import (
    Char,
    CStruct,
    CTypeAnnotation,
    Double,
    Float,
    Int8,
    Int16,
    Int32,
    Int64,
    StructPointer,
    Uint8,
    Uint16,
    Uint32,
    Uint64,
    Wchar,
    cdll_from_spec,
)


class Struct(CStruct):
    a: Uint32
    b: Uint8


class StructWithDefaults(CStruct):
    a: Uint32 = 100
    b: Uint32 = 200


class NestedStruct(CStruct):
    a: Struct
    b: StructWithDefaults


class Uint8Tuple(CStruct):
    a: Uint8
    b: Uint8


class TestLib:
    @staticmethod
    def swap_u8_tuple(x: StructPointer[Uint8Tuple], /) -> None: ...

    @staticmethod
    def sub_u8(x: Uint8, y: Uint8, /) -> Uint8:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_u16(x: Uint16, y: Uint16) -> Uint16:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_u32(x: Uint32, y: Uint32) -> Uint32:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_u64(x: Uint64, y: Uint64) -> Uint64:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_i8(x: Int8, y: Int8) -> Int8:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_i16(x: Int16, y: Int16) -> Int16:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_i32(x: Int32, y: Int32) -> Int32:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_i64(x: Int64, y: Int64) -> Int64:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_f32(x: Float, y: Float) -> Float:  # noqa: ARG004
        return NotImplemented

    @staticmethod
    def sub_f64(x: Double, y: Double) -> Double:  # noqa: ARG004
        return NotImplemented


@pytest.fixture()
def struct() -> Struct:
    return Struct.zeroed()


@pytest.fixture()
def lib() -> TestLib:
    path = Path(__file__).parent.joinpath("testlib/target/debug/libtestlib.so")
    if not path.exists():
        pytest.fail("Unable to load FFI")
    return cdll_from_spec(path, TestLib)


def test_read(struct: Struct) -> None:
    assert struct.a == 0
    assert struct.b == 0


def test_repr(struct: Struct) -> None:
    assert repr(struct) == "Struct(a=0, b=0)"


def test_char_types() -> None:
    class CharStruct(CStruct):
        char: Char
        w_char: Wchar

    s = CharStruct(b"a", "b")
    assert s.char == b"a"
    assert s.w_char == "b"


def test_field_packing() -> None:
    class UnpackedStruct(CStruct):
        a: Uint32
        b: Uint8

    class PackedStruct(CStruct, pack=True):
        a: Uint32
        b: Uint8

    assert UnpackedStruct.sizeof() == 8
    assert PackedStruct.sizeof() == 5


def test_defaults() -> None:
    assert StructWithDefaults().a == 100
    assert StructWithDefaults().b == 200


def test_nested_struct() -> None:
    s = NestedStruct.zeroed()

    assert isinstance(s.a, Struct)
    assert isinstance(s.b, StructWithDefaults)

    # Ensure that we always get the same CStruct instance when we fetch an element
    x = s.a
    y = s.a
    assert x is y

    # Ensure that the underlying struct is properly updated when the child structs are
    # updated
    a = s.a
    b = s.b
    a.a = 1
    a.b = 2
    b.a = 3
    b.b = 4

    raw_struct = s.struct()
    assert raw_struct.a.a == 1
    assert raw_struct.a.b == 2
    assert raw_struct.b.a == 3
    assert raw_struct.b.b == 4


def test_nested_struct_assigment() -> None:
    s = NestedStruct.zeroed()
    replacement = Struct(1, 2)

    s.a = replacement
    assert s.a.a == 1
    assert s.a.b == 2

    # The contents of the struct should be copied
    assert s.a is not replacement
    assert s.a.struct() is not replacement.struct()


def test_zeroed_bypass_defaults() -> None:
    assert StructWithDefaults.zeroed().a == 0
    assert StructWithDefaults.zeroed().b == 0


def test_write(struct: Struct) -> None:
    struct.a = 1234
    struct.b = 5678
    assert struct.a == 1234
    assert struct.b == 5678 & 0xFF  # Because uint8 will truncate the value


def test_missing(struct: Struct) -> None:
    with pytest.raises(AttributeError):
        struct.missing  # type: ignore  # noqa: B018


def test_endianess() -> None:
    class LE(CStruct, little_endian=True):
        v: Uint32

    class BE(CStruct, little_endian=False):
        v: Uint32

    v = 0x12345678
    le = LE(v)
    be = BE(v)

    assert le.v == be.v

    be_bytes = b"\x12\x34\x56\x78"
    assert bytes(le.struct()) == bytes(reversed(be_bytes))
    assert bytes(be.struct()) == be_bytes


def test_multiple_inheritance() -> None:
    class Mixin:
        def method(self) -> int:
            return 1

    class OrderA(CStruct, Mixin):
        uint: Uint32
        char: Uint8

    order_a = OrderA.zeroed()
    order_a.uint = 2
    assert order_a.uint == 2
    assert order_a.method() == 1

    class OrderB(Mixin, CStruct):
        uint: Uint32
        char: Uint8

    order_b = OrderB.zeroed()
    order_b.uint = 3
    assert order_b.uint == 3
    assert order_b.method() == 1


def test_deep_inheritance() -> None:
    class GrandParent(CStruct):
        uint: Uint32
        char: Uint8

    class Parent(GrandParent):
        pass

    parent = Parent.zeroed()
    parent.uint = 666
    assert parent.uint == 666


@pytest.mark.parametrize(
    "invalid_type",
    [
        bool,
        bytes,
        str,
        bytes | None,
        str | None,
        int | None,
    ],
)
def test_invalid_types(invalid_type: type[t.Any]) -> None:
    with pytest.raises(TypeError):

        class InvalidStruct(CStruct):  # pyright: ignore[reportUnusedClass]
            invalid_field: invalid_type  # type: ignore[valid-type]


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (Char, CTypeAnnotation(bytes, ctypes.c_char)),
        (Uint8, CTypeAnnotation(int, ctypes.c_uint8)),
        (Float, CTypeAnnotation(float, ctypes.c_float)),
    ],
)
def test_from_annotated_type(type_: t.Any, expected: CTypeAnnotation) -> None:
    assert CTypeAnnotation.from_annotated_type(type_) == expected


def test_shared_object_typing(lib: TestLib) -> None:
    u8_tuple = Uint8Tuple(42, 69)
    assert u8_tuple.a == 42
    assert u8_tuple.b == 69
    lib.swap_u8_tuple(u8_tuple.byref())
    assert u8_tuple.a == 69
    assert u8_tuple.b == 42

    assert lib.sub_u8(2, 1) == 1
    assert lib.sub_u16(69, 42) == 27
    assert lib.sub_u32(1_000_000_000, 400_000_000) == 600_000_000
    assert lib.sub_u64(1_000_000_000_000, 1) == 999_999_999_999

    assert lib.sub_i8(1, 2) == -1
    assert lib.sub_i16(42, 69) == -27
    assert lib.sub_i32(400_000_000, 1_000_000_000) == -600_000_000
    assert lib.sub_i64(1, 1_000_000_000_000) == -999_999_999_999

    assert lib.sub_f32(1.0, 0.5) == 0.5
    assert lib.sub_f64(0.5, 1.0) == -0.5

    t.assert_type(lib.sub_u8(1, 1), int)
    t.assert_type(lib.sub_u16(1, 1), int)
    t.assert_type(lib.sub_u32(1, 1), int)
    t.assert_type(lib.sub_u64(1, 1), int)
    t.assert_type(lib.sub_i8(1, 1), int)
    t.assert_type(lib.sub_i16(1, 1), int)
    t.assert_type(lib.sub_i32(1, 1), int)
    t.assert_type(lib.sub_i64(1, 1), int)
    t.assert_type(lib.sub_f32(1.0, 1.0), float)
    t.assert_type(lib.sub_f64(1.0, 1.0), float)
    t.assert_type(lib.swap_u8_tuple(u8_tuple.byref()), None)
