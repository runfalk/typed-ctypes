import ctypes

import pytest

from typed_ctypes import StructProxy


class Struct(ctypes.Structure):
    _fields_ = [
        ("uint", ctypes.c_uint32),
        ("char", ctypes.c_uint8),
    ]


class Proxy(StructProxy[Struct]):
    uint: int
    char: int


@pytest.fixture
def proxy() -> Proxy:
    return Proxy()


def test_read(proxy: Proxy) -> None:
    assert proxy.uint == 0
    assert proxy.char == 0


def test_write(proxy: Proxy) -> None:
    proxy.uint = 1234
    proxy.char = 5678
    assert proxy.uint == 1234
    assert proxy.char == 5678 & 0xFF  # Because uint8 will truncate the value


def test_missing(proxy: Proxy) -> None:
    with pytest.raises(AttributeError):
        proxy.missing  # type: ignore


def test_multiple_inheritance() -> None:
    class Mixin:
        def method(self) -> int:
            return 1

    class OrderA(StructProxy[Struct], Mixin):
        uint: int
        char: int

    order_a = OrderA()
    order_a.uint = 2
    assert order_a.uint == 2
    assert order_a.method() == 1

    class OrderB(Mixin, StructProxy[Struct]):
        uint: int
        char: int

    order_b = OrderB()
    order_b.uint = 3
    assert order_b.uint == 3
    assert order_b.method() == 1


def test_deep_inheritance() -> None:
    class GrandParent(StructProxy[Struct]):
        uint: int
        char: int

    class Parent(GrandParent):
        pass

    parent = Parent()
    parent.uint = 666
    assert parent.uint == 666
