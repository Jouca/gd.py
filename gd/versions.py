from __future__ import annotations

from typing import Type, TypeVar

from attrs import Attribute, field, frozen
from typing_extensions import Final, TypedDict

from gd.binary import VERSION, Binary, BinaryReader, BinaryWriter
from gd.binary_utils import Reader, Writer
from gd.converter import CONVERTER
from gd.enums import ByteOrder
from gd.robtop import RobTop
from gd.string_utils import tick

__all__ = (
    "CURRENT_GAME_VERSION",
    "CURRENT_BINARY_VERSION",
    "Version",
    "VersionData",
    "GameVersion",
)

BASE: Final[int] = 10

V = TypeVar("V", bound="Version")

EXPECTED_MAJOR = "expected major >= 0"
EXPECTED_MINOR = "expected minor >= 0"
EXPECTED_BASE = f"expected minor <= {BASE}"


class VersionData(TypedDict):
    major: int
    minor: int


@frozen(order=True)
class Version(Binary, RobTop):
    major: int = field(default=0)
    minor: int = field(default=0)

    def __hash__(self) -> int:
        return self.to_value()

    @major.validator
    def check_major(self, attribute: Attribute[int], major: int) -> None:
        if major < 0:
            raise ValueError(EXPECTED_MAJOR)

    @minor.validator
    def check_minor(self, attribute: Attribute[int], minor: int) -> None:
        if minor < 0:
            raise ValueError(EXPECTED_MINOR)

        if minor >= BASE:
            raise ValueError(EXPECTED_BASE)

    @classmethod
    def from_json(cls: Type[V], data: VersionData) -> V:
        return CONVERTER.structure(data, cls)

    def to_json(self) -> VersionData:
        return CONVERTER.unstructure(self)  # type: ignore

    @classmethod
    def from_value(cls: Type[V], value: int) -> V:
        major, minor = divmod(value, BASE)

        return cls(major, minor)

    def to_value(self) -> int:
        return self.major * BASE + self.minor

    @classmethod
    def from_robtop(cls: Type[V], string: str) -> V:
        return cls.from_value(int(string))

    def to_robtop(self) -> str:
        return str(self.to_value())

    @classmethod
    def can_be_in(cls, string: str) -> bool:
        return string.isdigit()

    # assume `u8` is enough

    @classmethod
    def from_binary(
        cls: Type[V],
        binary: BinaryReader,
        order: ByteOrder = ByteOrder.DEFAULT,
        version: int = VERSION,
    ) -> V:
        reader = Reader(binary, order)

        return cls.from_value(reader.read_u8())

    def to_binary(
        self, binary: BinaryWriter, order: ByteOrder = ByteOrder.DEFAULT, version: int = VERSION
    ) -> None:
        writer = Writer(binary, order)

        writer.write_u8(self.to_value())


G = TypeVar("G", bound="GameVersion")

INVALID_GAME_VERSION = "invalid game version: {}"


@frozen()
class GameVersion(Version):
    @classmethod
    def from_robtop_value(cls: Type[G], value: int) -> G:  # why, RobTop?
        if not value:
            return cls()

        if 0 < value < 8:
            return cls(1, value - 1)

        if value < 10:
            raise ValueError(INVALID_GAME_VERSION.format(tick(str(value))))

        if value == 10:
            return cls(1, 7)

        if value == 11:
            return cls(1, 8)

        return cls.from_value(value)

    def to_robtop_value(self) -> int:
        major = self.major
        minor = self.minor

        if major == 1:
            if minor == 8:
                return 11

            elif minor == 7:
                return 10

            elif minor < 7:
                return minor + 1

        return self.to_value()

    @classmethod
    def from_robtop(cls: Type[G], string: str) -> G:
        return cls.from_robtop_value(int(string))

    def to_robtop(self) -> str:
        return str(self.to_robtop_value())

    @classmethod
    def can_be_in(cls, string: str) -> bool:
        return string.isdigit()


CURRENT_GAME_VERSION = GameVersion(2, 1)
CURRENT_BINARY_VERSION = Version(3, 5)
