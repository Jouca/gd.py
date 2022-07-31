from os import getenv as get_environment
from pathlib import Path
from typing import Generic, Type, TypeVar

from attrs import define

from gd.api.database import Database
from gd.async_utils import run_blocking
from gd.constants import DEFAULT_ENCODING, DEFAULT_ERRORS
from gd.encoding import decode_os_save, decode_save, encode_os_save, encode_save
from gd.platform import SYSTEM_PLATFORM, Platform
from gd.typing import IntoPath, Optional, Tuple

__all__ = (
    "MAIN_NAME", "LEVELS_NAME", "PATH", "SaveManager", "create_database", "save_manager", "save"
)

MAIN_NAME = "CCGameManager.dat"
LEVELS_NAME = "CCLocalLevels.dat"


HOME = Path.home()


LOCAL_APP_DATA_NAME = "LOCALAPPDATA"
LOCAL_APP_DATA_STRING = get_environment(LOCAL_APP_DATA_NAME)

APP_DATA = "AppData"
LOCAL = "Local"

if LOCAL_APP_DATA_STRING is None:
    LOCAL_APP_DATA = HOME / APP_DATA / LOCAL

else:
    LOCAL_APP_DATA = Path(LOCAL_APP_DATA_STRING)


GEOMETRY_DASH = "GeometryDash"
GEOMETRY_DASH_ID = 322170

LIBRARY = "Library"
APPLICATION_SUPPORT = "Application Support"

DOT_STEAM = ".steam"
STEAM = "steam"
STEAM_APPS = "steamapps"
COMPATIBILITY_DATA = "compatdata"
PFX = "pfx"

DRIVE_C = "drive_c"
USERS = "users"
STEAM_USER = "steamuser"
LOCAL_SETTINGS = "Local Settings"
APPLICATION_DATA = "Application Data"


WINDOWS_PATH = LOCAL_APP_DATA / GEOMETRY_DASH
MAC_OS_PATH = HOME / LIBRARY / APPLICATION_SUPPORT / GEOMETRY_DASH
LINUX_PATH = (
    HOME / DOT_STEAM / STEAM / STEAM_APPS / COMPATIBILITY_DATA / str(GEOMETRY_DASH_ID) / PFX
    / DRIVE_C / USERS / STEAM_USER / LOCAL_SETTINGS / APPLICATION_DATA / GEOMETRY_DASH
)


PATHS = {
    Platform.WINDOWS: WINDOWS_PATH,
    Platform.MAC_OS: MAC_OS_PATH,
    Platform.LINUX: LINUX_PATH,
}


PATH = PATHS.get(SYSTEM_PLATFORM)

SAVE_NOT_SUPPORTED = "save management is not supported on this platform"

D = TypeVar("D", bound=Database)


@define()
class SaveManager(Generic[D]):
    database_type: Type[D]
    main_name: str = MAIN_NAME
    levels_name: str = LEVELS_NAME

    def load(self, main: Optional[IntoPath] = None, levels: Optional[IntoPath] = None) -> D:
        return self.load_local(main, levels)

    async def load_async(
        self, main: Optional[IntoPath] = None, levels: Optional[IntoPath] = None
    ) -> D:
        return await run_blocking(self.load_local, main, levels)

    def dump(
        self,
        database: Database,
        main: Optional[IntoPath] = None,
        levels: Optional[IntoPath] = None,
    ) -> None:
        return self.dump_local(database, main, levels)

    async def dump_async(
        self,
        database: Database,
        main: Optional[IntoPath] = None,
        levels: Optional[IntoPath] = None,
    ) -> None:
        return await run_blocking(self.dump_local, database, main, levels)

    def create_database(self) -> D:
        return self.database_type()

    def load_local(
        self, main: Optional[IntoPath] = None, levels: Optional[IntoPath] = None
    ) -> D:
        main_path = self.compute_path(main, self.main_name)
        levels_path = self.compute_path(levels, self.levels_name)

        main_data = main_path.read_bytes()
        levels_data = levels_path.read_bytes()

        return self.load_parts(main_data, levels_data, apply_xor=True, follow_os=True)

    def dump_local(
        self,
        database: Database,
        main: Optional[IntoPath] = None,
        levels: Optional[IntoPath] = None,
    ) -> None:
        main_path = self.compute_path(main, self.main_name)
        levels_path = self.compute_path(levels, self.levels_name)

        main_data, levels_data = self.dump_parts(database, apply_xor=True, follow_os=True)

        main_path.write_bytes(main_data)
        levels_path.write_bytes(levels_data)

    def to_bytes(
        self,
        database: Database,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> Tuple[bytes, bytes]:
        main_data, levels_data = self.dump_parts(
            database, apply_xor=apply_xor, follow_os=follow_os
        )

        return (main_data, levels_data)

    async def to_bytes_async(
        self,
        database: Database,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> Tuple[bytes, bytes]:
        main_data, levels_data = await run_blocking(
            self.dump_parts, database, apply_xor=apply_xor, follow_os=follow_os
        )

        return (main_data, levels_data)

    def to_strings(
        self,
        database: Database,
        encoding: str = DEFAULT_ENCODING,
        errors: str = DEFAULT_ERRORS,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> Tuple[str, str]:
        main_string, levels_string = self.dump_string_parts(
            database,
            encoding=encoding,
            errors=errors,
            apply_xor=apply_xor,
            follow_os=follow_os,
        )

        return (main_string, levels_string)

    async def to_strings_async(
        self,
        database: Database,
        encoding: str = DEFAULT_ENCODING,
        errors: str = DEFAULT_ERRORS,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> Tuple[str, str]:
        main_string, levels_string = await run_blocking(
            self.dump_string_parts,
            database,
            encoding=encoding,
            errors=errors,
            apply_xor=apply_xor,
            follow_os=follow_os,
        )

        return (main_string, levels_string)

    def from_bytes(
        self,
        main_data: bytes,
        levels_data: bytes,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> D:
        return self.load_parts(main_data, levels_data, apply_xor=apply_xor, follow_os=follow_os)

    async def from_bytes_async(
        self,
        main_data: bytes,
        levels_data: bytes,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> D:
        return await run_blocking(
            self.load_parts, main_data, levels_data, apply_xor=apply_xor, follow_os=follow_os
        )

    def from_strings(
        self,
        main_string: str,
        levels_string: str,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> D:
        return self.load_string_parts(
            main_string, levels_string, apply_xor=apply_xor, follow_os=follow_os
        )

    async def from_strings_async(
        self,
        main_string: str,
        levels_string: str,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> D:
        return await run_blocking(
            self.load_string_parts,
            main_string,
            levels_string,
            apply_xor=apply_xor,
            follow_os=follow_os,
        )

    def load_parts(
        self,
        main_data: bytes,
        levels_data: bytes,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> D:
        main = self.decode_data(main_data, apply_xor=apply_xor, follow_os=follow_os)
        levels = self.decode_data(levels_data, apply_xor=apply_xor, follow_os=follow_os)

        return self.database_type(main, levels)

    def load_string_parts(
        self,
        main_string: str,
        levels_string: str,
        encoding: str = DEFAULT_ENCODING,
        errors: str = DEFAULT_ERRORS,
        apply_xor: bool = False,
        follow_os: bool = False,
        database_type: Type[Database] = Database,
    ) -> D:
        return self.load_parts(
            main_string.encode(encoding, errors),
            levels_string.encode(encoding, errors),
            apply_xor=apply_xor,
            follow_os=follow_os,
        )

    def dump_parts(
        self, database: Database, apply_xor: bool = False, follow_os: bool = False
    ) -> Tuple[bytes, bytes]:
        main_data = self.encode_data(
            database.main.dump(), apply_xor=apply_xor, follow_os=follow_os
        )
        levels_data = self.encode_data(
            database.levels.dump(), apply_xor=apply_xor, follow_os=follow_os
        )

        return (main_data, levels_data)

    def dump_string_parts(
        self,
        database: Database,
        encoding: str = DEFAULT_ENCODING,
        errors: str = DEFAULT_ERRORS,
        apply_xor: bool = False,
        follow_os: bool = False,
    ) -> Tuple[str, str]:
        main_data, levels_data = self.dump_parts(
            database, apply_xor=apply_xor, follow_os=follow_os
        )

        return (main_data.decode(encoding, errors), levels_data.decode(encoding, errors))

    def compute_path(self, base_path: Optional[IntoPath], additional_path: IntoPath) -> Path:
        if base_path is None:
            if PATH is None:
                raise OSError  # TODO: message?

            return PATH / additional_path

        path = Path(base_path)

        if path.is_dir():
            return path / additional_path

        return path

    def decode_data(self, data: bytes, apply_xor: bool = True, follow_os: bool = True) -> bytes:
        decode = decode_os_save if follow_os else decode_save

        return decode(data, apply_xor=apply_xor)

    def encode_data(self, data: bytes, apply_xor: bool = True, follow_os: bool = True) -> bytes:
        encode = encode_os_save if follow_os else encode_save

        return encode(data, apply_xor=apply_xor)


save_manager = SaveManager(Database)
save = save_manager
create_database = save_manager.create_database
