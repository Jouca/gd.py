from typing import Any, Optional

from aiohttp.web import Response, json_response
from attrs import field, frozen
from typing_extensions import TypedDict

from gd.enum_extensions import Enum
from gd.server.constants import APPLICATION_JSON
from gd.server.typing import Handler, Headers
from gd.typing import JSONType, StringDict, StringMapping

__all__ = (
    "HTTP_STATUS_TO_ERROR_TYPE",
    # error handling
    "Error",
    "ErrorHandler",
    "ErrorResult",
    "default_error_handler",
    "fail_error_handler",
    # request handling
    "RequestHandler",
    "request_handler",
    # utils for handling dynamic typing
    "error_result_into_response",
    "handler_into_request_handler",
)


class ErrorType(Enum):
    DEFAULT = 13000

    INVALID_ENTITY = 13001
    MISSING_PARAMETER = 13002
    FORBIDDEN = 13003
    NOT_FOUND = 13004
    FAILED = 13005

    UNAUTHORIZED = 13101
    LOGIN_FAILED = 13102

    RATE_LIMITED = 13201

    AUTH_INVALID = 13301
    AUTH_MISSING = 13302
    AUTH_NOT_SET = 13303


HTTP_STATUS_TO_ERROR_TYPE = {
    401: ErrorType.UNAUTHORIZED,
    403: ErrorType.FORBIDDEN,
    404: ErrorType.NOT_FOUND,
    422: ErrorType.INVALID_ENTITY,
    429: ErrorType.RATE_LIMITED,
}


class ErrorData(TypedDict):
    code: str
    message: Optional[str]


DEFAULT_STATUS_CODE = 500
DEFAULT_ERROR_TYPE = ErrorType.DEFAULT


@frozen()
class Error:
    status: int = DEFAULT_STATUS_CODE
    type: ErrorType = DEFAULT_ERROR_TYPE
    message: Optional[str] = None
    headers: Optional[Headers] = None

    def into_data(self) -> ErrorData:
        return ErrorData(code=self.type.name, message=self.message)

    def into_response(self, **keywords: Any) -> Response:
        actual = dict(status=self.status, headers=self.headers)

        actual.update(keywords)

        return json_response(self.into_data(), **actual)


ErrorExcept = Union[Type[BaseException], Tuple[Type[BaseException], ...]]
ErrorResult = Union[Error, web.StreamResponse]
ErrorReturn = Union[NoReturn, ErrorResult]

ErrorHandler = Callable[[web.Request, Exception], Awaitable[ErrorReturn]]


def error_result_into_response(error_result: ErrorResult) -> web.StreamResponse:
    if isinstance(error_result, Error):
        return error_result.into_response()

    elif isinstance(error_result, web.StreamResponse):
        return error_result

    else:
        raise ValueError(
            f"Expected error result of types {ErrorResult}, got {type(error_result).__name__!r}."
        )


async def default_error_handler(request: web.Request, error: BaseException) -> Error:
    # default error handler is simply going to return not really useful generic error message
    return Error(message="Some unexpected error has occurred.")


async def fail_error_handler(request: web.Request, error: BaseException) -> NoReturn:
    # fail error handler is going to raise the exception it is given
    raise error


class RequestHandler:
    def __init__(
        self,
        handler: Handler,
        error_except: ErrorExcept = Exception,
        fail_on_error: bool = False,
    ) -> None:
        self.handler: Handler = handler
        self.error_handler: ErrorHandler = (
            fail_error_handler if fail_on_error else default_error_handler
        )

        self.error_except = error_except

    async def __call__(self, request: web.Request) -> web.StreamResponse:
        try:
            return await self.handler(request)

        except self.error_except as error:
            error_result = await self.error_handler(request, cast(Exception, error))

            return error_result_into_response(error_result)

    def error(self, error_handler: ErrorHandler) -> ErrorHandler:
        self.error_handler = error_handler

        return error_handler


def request_handler(
    error_except: ErrorExcept = Exception,
    fail_on_error: bool = False,
) -> Callable[[Handler], RequestHandler]:
    def wrapper(handler: Handler) -> RequestHandler:
        return RequestHandler(handler, error_except=error_except, fail_on_error=fail_on_error)

    return wrapper


def handler_into_request_handler(handler: Handler) -> RequestHandler:
    if isinstance(handler, RequestHandler):
        return handler

    return RequestHandler(handler)
