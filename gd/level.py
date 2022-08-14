from __future__ import annotations

from datetime import datetime, timedelta

# from pathlib import Path
from typing import TYPE_CHECKING, Any, AsyncIterator, BinaryIO, Iterable, Optional, Type, TypeVar

from attrs import define, field
from iters import iter

# from gd.api.editor import Editor
from gd.await_iters import wrap_await_iter
from gd.binary_utils import UTF_8, Reader, Writer
from gd.constants import COMMENT_PAGE_SIZE, DEFAULT_PAGE, DEFAULT_RECORD, EMPTY, EMPTY_BYTES
from gd.entity import Entity
from gd.enums import (
    ByteOrder,
    CommentStrategy,
    DemonDifficulty,
    Difficulty,
    LevelLeaderboardStrategy,
    LevelLength,
    Score,
    TimelyID,
    TimelyType,
)
from gd.errors import MissingAccess

# from gd.models import LevelModel
from gd.password import Password
from gd.song import Song
from gd.user import User
from gd.versions import CURRENT_GAME_VERSION, GameVersion

from .binary import VERSION

if TYPE_CHECKING:
    from gd.client import Client  # noqa
    from gd.comments import Comment  # noqa

__all__ = ("Level",)

L = TypeVar("L", bound="Level")

REQUESTED_STARS_MASK = 0b11110000
STARS_MASK = 0b00001111

REQUESTED_STARS_SHIFT = STARS_MASK.bit_length()

DIFFICULTY_MASK = 0b00001111
TWO_PLAYER_BIT = 0b00010000
VERIFIED_COINS_BIT = 0b00100000
EPIC_BIT = 0b01000000
LOW_DETAIL_BIT = 0b10000000


@define()
class Level(Entity):
    name: str = field()
    creator: User = field()
    song: Song = field()
    uploaded_at: datetime = field()
    updated_at: datetime = field()
    description: str = field(default=EMPTY)
    data: bytes = field(default=EMPTY_BYTES)
    version: int = field(default=0)
    downloads: int = field(default=0)
    game_version: GameVersion = field(default=CURRENT_GAME_VERSION)
    rating: int = field(default=0)
    length: LevelLength = field(default=LevelLength.DEFAULT)
    difficulty: Difficulty = field(default=Difficulty.DEFAULT)
    stars: int = field(default=0)
    requested_stars: int = field(default=0)
    score: int = field(default=0)
    password_data: Password = field(factory=Password)
    original_id: int = field(default=0)
    two_player: bool = field(default=False)
    coins: int = field(default=0)
    verified_coins: bool = field(default=False)
    low_detail: bool = field(default=False)
    epic: bool = field(default=False)
    object_count: int = field(default=0)
    editor_time: timedelta = field(factory=timedelta)
    copies_time: timedelta = field(factory=timedelta)
    timely_type: TimelyType = field(default=TimelyType.DEFAULT)

    def to_binary(
        self,
        binary: BinaryIO,
        order: ByteOrder = ByteOrder.DEFAULT,
        version: int = VERSION,
        encoding: str = UTF_8,
    ) -> None:
        writer = Writer(binary)

        super().to_binary(binary, order)

        data = self.name.encode(encoding)

        writer.write_u8(len(data), order)

        writer.write(data)

        self.creator.to_binary(binary, order)
        self.song.to_binary(binary, order)

        writer.write_f32(self.uploaded_at.timestamp(), order)
        writer.write_f32(self.updated_at.timestamp(), order)

        data = self.description.encode(encoding)

        writer.write_u16(len(data), order)

        writer.write(data)

        data = self.data

        writer.write_u32(len(data), order)

        writer.write(data)

        writer.write_u8(self.version, order)

        writer.write_u32(self.downloads, order)

        self.game_version.to_binary(binary, order)

        writer.write_i32(self.rating, order)

        writer.write_u8(self.length.value, order)

        value = self.difficulty.value

        if self.is_two_player():
            value |= TWO_PLAYER_BIT

        if self.has_verified_coins():
            value |= VERIFIED_COINS_BIT

        if self.is_epic():
            value |= EPIC_BIT

        if self.has_low_detail():
            value |= LOW_DETAIL_BIT

        writer.write_u8(value, order)

        value = (self.requested_stars << REQUESTED_STARS_SHIFT) | self.stars

        writer.write_u8(value, order)

        writer.write_i32(self.score, order)

        self.password_data.to_binary(binary, order)

        writer.write_u32(self.original_id, order)

        writer.write_u8(self.coins, order)

        writer.write_u32(self.object_count, order)

        writer.write_f32(self.editor_time.total_seconds(), order)
        writer.write_f32(self.copies_time.total_seconds(), order)

        writer.write_u8(self.timely_type.value, order)

    @classmethod
    def from_binary(
        cls: Type[L],
        binary: BinaryIO,
        order: ByteOrder = ByteOrder.DEFAULT,
        version: int = VERSION,
        encoding: str = UTF_8,
    ) -> L:
        two_player_bit = TWO_PLAYER_BIT
        verified_coins_bit = VERIFIED_COINS_BIT
        epic_bit = EPIC_BIT
        low_detail_bit = LOW_DETAIL_BIT

        reader = Reader(binary)

        id = reader.read_u32(order)

        name_length = reader.read_u8(order)

        name = reader.read(name_length).decode(encoding)

        creator = User.from_binary(binary, order, encoding)
        song = Song.from_binary(binary, order, encoding)

        uploaded_timestamp = reader.read_f32(order)
        updated_timestamp = reader.read_f32(order)

        uploaded_at = datetime.fromtimestamp(uploaded_timestamp)
        updated_at = datetime.fromtimestamp(updated_timestamp)

        description_length = reader.read_u16(order)

        description = reader.read(description_length).decode(encoding)

        data_length = reader.read_u32(order)

        data = reader.read(data_length)

        version = reader.read_u8(order)

        downloads = reader.read_u32(order)

        game_version = GameVersion.from_binary(binary, order)

        rating = reader.read_i32(order)

        length_value = reader.read_u8(order)

        length = LevelLength(length_value)

        value = reader.read_u8(order)

        difficulty_value = value & DIFFICULTY_MASK

        difficulty = Difficulty(difficulty_value)

        two_player = value & two_player_bit == two_player_bit
        verified_coins = value & verified_coins_bit == verified_coins_bit
        epic = value & epic_bit == epic_bit
        low_detail = value & low_detail_bit == low_detail_bit

        value = reader.read_u8(order)

        requested_stars = (value & REQUESTED_STARS_MASK) >> REQUESTED_STARS_SHIFT
        stars = value & STARS_MASK

        score = reader.read_i32(order)

        password_data = Password.from_binary(binary, order)

        original_id = reader.read_u32(order)

        coins = reader.read_u8(order)

        object_count = reader.read_u32(order)

        editor_seconds = reader.read_f32(order)
        copies_seconds = reader.read_f32(order)

        editor_time = timedelta(seconds=editor_seconds)
        copies_time = timedelta(seconds=copies_seconds)

        timely_type_value = reader.read_u8(order)

        timely_type = TimelyType(timely_type_value)

        return cls(
            id=id,
            name=name,
            creator=creator,
            song=song,
            uploaded_at=uploaded_at,
            updated_at=updated_at,
            description=description,
            data=data,
            version=version,
            downloads=downloads,
            game_version=game_version,
            rating=rating,
            length=length,
            difficulty=difficulty,
            stars=stars,
            requested_stars=requested_stars,
            score=score,
            password_data=password_data,
            original_id=original_id,
            two_player=two_player,
            coins=coins,
            verified_coins=verified_coins,
            low_detail=low_detail,
            epic=epic,
            object_count=object_count,
            editor_time=editor_time,
            copies_time=copies_time,
            timely_type=timely_type,
        )

    @classmethod
    def official(
        cls: Type[L],
        id: Optional[int] = None,
        name: Optional[str] = None,
        get_data: bool = True,
        server_style: bool = False,
    ) -> L:
        official_levels = OFFICIAL_LEVELS

        if id is None:
            if name is None:
                ...

            else:
                official_level = iter(official_levels).find_or_none(by_name(name))

        else:
            official_level = iter(official_levels).find_or_none(by_id(id))

        if official_level is None:
            raise LookupError("Could not find official level by given query.")

        return cast(OfficialLevel, official_level).into_level(
            client, get_data=get_data, server_style=server_style
        )

    @property
    def score_type(self) -> Score:
        return Score(self.score)

    @property
    def password(self) -> Optional[int]:
        return self.password_data.password

    @property
    def timely_id(self) -> TimelyID:
        return self.timely_type.into_timely_id()

    def is_copyable(self) -> bool:
        return self.password_data.copyable

    def is_timely(self, timely_type: Optional[TimelyType] = None) -> bool:
        if timely_type is None:
            return not self.timely_type.is_not_timely()

        return self.timely_type is timely_type

    def is_rated(self) -> bool:
        return self.stars > 0

    def is_unfeatured(self) -> bool:
        return self.score_type.is_unfeatured()

    def is_epic_only(self) -> bool:
        return self.score_type.is_epic_only()

    def is_featured(self) -> bool:
        return self.score_type.is_featured()

    def is_epic(self) -> bool:
        return self.epic

    def is_original(self) -> bool:
        return not self.original_id

    def is_two_player(self) -> bool:
        return self.two_player

    def has_low_detail(self) -> bool:
        return self.low_detail

    def has_verified_coins(self) -> bool:
        return self.verified_coins

    def open_editor(self) -> Editor:
        ...

    async def report(self) -> None:
        await self.client.report_level(self)

    async def upload(self, **kwargs: Any) -> None:
        song = self.song
        song_id = song.id

        track_id, song_id = (0, song_id) if song.is_custom() else (song_id, 0)

        args = dict(
            name=self.name,
            id=self.id,
            version=self.version,
            length=abs(self.length.value),
            track_id=track_id,
            song_id=song_id,
            two_player=self.is_two_player(),
            original=self.original_id,
            objects=self.objects,
            coins=self.coins,
            stars=self.stars,
            unlisted=False,
            friends_only=False,
            low_detail=self.has_low_detail(),
            password=self.password,
            copyable=self.is_copyable(),
            description=self.description,
            editor_seconds=self.editor_seconds,
            copies_seconds=self.copies_seconds,
            data=self.data,
        )

        args.update(kwargs)

        uploaded = await client.upload_level(**args)

        self.options.update(uploaded.options)

    async def delete(self) -> None:
        await self.client.delete_level(self)

    async def update_description(self, content: str) -> None:
        await self.client.update_level_description(self, content)

    async def rate(self, stars: int) -> None:
        await self.client.rate_level(self, stars)

    async def rate_demon(
        self, demon_difficulty: DemonDifficulty = DemonDifficulty.DEFAULT, as_mod: bool = False
    ) -> None:
        await self.client.rate_demon(self, demon_difficulty=demon_difficulty, as_mod=as_mod)

    async def suggest(self, stars: int, featured: bool) -> None:
        await self.client.suggest_level(self, stars=stars, featured=featured)

    async def is_alive(self) -> bool:
        ...

    async def update(self, *, get_data: bool = True) -> Optional[Level]:
        ...

    async def comment(self, content: str, record: int = DEFAULT_RECORD) -> Optional[Comment]:
        return await self.client.comment_level(self, content, record)

    async def like(self) -> None:
        await self.client.like(self)

    async def dislike(self) -> None:
        await self.client.dislike(self)

    @wrap_await_iter
    def get_leaderboard(
        self,
        strategy: LevelLeaderboardStrategy = LevelLeaderboardStrategy.DEFAULT,
    ) -> AsyncIterator[User]:
        return self.client.get_level_leaderboard(self, strategy=strategy)

    @wrap_await_iter
    def get_comments(
        self,
        strategy: CommentStrategy = CommentStrategy.DEFAULT,
        pages: Iterable[int] = DEFAULT_PAGE,
        amount: int = COMMENT_PAGE_SIZE,
    ) -> AsyncIterator["Comment"]:
        return self.client.get_level_comments(
            level=self,
            strategy=strategy,
            pages=pages,
            amount=amount,
            concurrent=concurrent,
        )

    @wrap_await_iter
    def get_comments_on_page(
        self,
        strategy: CommentStrategy = CommentStrategy.DEFAULT,
        page: int = DEFAULT_PAGE,
        count: int = COMMENT_PAGE_SIZE,
    ) -> AsyncIterator[Comment]:
        return self.client.get_level_comments_on_page(
            self, page=page, count=count, strategy=strategy
        )
