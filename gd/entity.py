from __future__ import annotations

from builtins import getattr as get_attribute
from builtins import setattr as set_attribute
from typing import TYPE_CHECKING, Any, Optional, Type, TypeVar

from attrs import Attribute, define, field, fields
from cattrs.gen import make_dict_unstructure_fn, override
from typing_extensions import TypedDict

from gd.binary import VERSION, Binary, BinaryReader, BinaryWriter
from gd.binary_utils import Reader, Writer
from gd.converter import CONVERTER
from gd.enums import ByteOrder
from gd.errors import ClientError

if TYPE_CHECKING:
    from gd.client import Client

__all__ = ("Entity", "EntityData")

E = TypeVar("E", bound="Entity")

CLIENT_NOT_ATTACHED = "`client` not attached to the entity: {}"


class EntityData(TypedDict):
    id: int


ID = "id"


@define()
class Entity(Binary):
    id: int = field()

    client_unchecked: Optional[Client] = field(default=None, init=False, repr=False, eq=False)

    def __hash__(self) -> int:
        return hash(type(self)) ^ self.id

    @id.validator
    def check_id(self, attribute: Attribute[int], id: int) -> None:
        if id < 0:
            raise ValueError  # TODO: message?

    @property
    def client(self) -> Client:
        result = self.client_unchecked

        if result is None:
            raise ClientError(CLIENT_NOT_ATTACHED.format(self))

        return result

    @client.setter
    def client(self, client: Client) -> None:
        self.client_unchecked = client

    @client.deleter
    def client(self) -> None:
        self.client_unchecked = None

    def attach_client_unchecked(self: E, client: Optional[Client]) -> E:
        self.client_unchecked = client

        return self

    def attach_client(self: E, client: Client) -> E:
        self.client = client

        return self

    def detach_client(self: E) -> E:
        del self.client

        return self

    def update_from(self: E, entity: Entity) -> E:
        for attribute in fields(type(entity)):
            name = attribute.name

            set_attribute(self, name, get_attribute(entity, name))

        return self

    @classmethod
    def from_json(cls: Type[E], data: EntityData) -> E:
        return CONVERTER.structure(data, cls)

    def to_json(self) -> EntityData:
        return CONVERTER.unstructure(self)  # type: ignore

    @classmethod
    def from_binary(
        cls: Type[E],
        binary: BinaryReader,
        order: ByteOrder = ByteOrder.DEFAULT,
        version: int = VERSION,
    ) -> E:
        reader = Reader(binary, order)

        id = reader.read_u32()

        return cls(id)

    def to_binary(
        self, binary: BinaryWriter, order: ByteOrder = ByteOrder.DEFAULT, version: int = VERSION
    ) -> None:
        writer = Writer(binary, order)

        writer.write_u32(self.id)


if not TYPE_CHECKING:
    Client = Any


CONVERTER.register_unstructure_hook(
    Entity,
    make_dict_unstructure_fn(Entity, CONVERTER, client_unchecked=override(omit=True)),
)
