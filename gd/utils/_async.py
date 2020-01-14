import asyncio
import functools

try:
    import gc
except ImportError:
    pass

import inspect
from types import CoroutineType as coroutine

from .._typing import Any, Callable, Coroutine, Dict, Sequence, Set, Tuple, Type, Union

__all__ = (
    'run_blocking_io', 'wait', 'run',
    'cancel_all_tasks', 'shutdown_loop',
    'coroutine', 'maybe_coroutine', 'acquire_loop',
    'enable_asyncwrap', 'enable_run_method', 'synchronize'
)


async def run_blocking_io(func: Callable, *args, **kwargs) -> Any:
    """|coro|

    Run some blocking function in an event loop.

    If there is a running loop, ``'func'`` is executed in it.

    Otherwise, a new loop is being created and closed at the end of the execution.

    Example:

    .. code-block:: python3

        def make_image():
            ...  # long code of creating an image

        # somewhere in an async function:

        await run_blocking_io(make_image)
    """
    loop = acquire_loop(running=True)

    asyncio.set_event_loop(loop)

    return await loop.run_in_executor(None, functools.partial(func, *args, **kwargs))


async def wait(
    fs: Sequence[Coroutine], *, loop: asyncio.AbstractEventLoop = None,
    timeout: Union[float, int] = None, return_when: str = 'ALL_COMPLETED'
) -> Tuple[Set[asyncio.Future], Set[asyncio.Future]]:
    """A function that is calling :func:`asyncio.wait`.

    Used for less imports inside and outside of this library.

    Wait for the Futures and coroutines given by fs to complete.

    The sequence futures must not be empty.

    Coroutines will be wrapped in Tasks.

    Returns two sets of Future: (done, pending).

    Usage:

    .. code-block:: python3

        done, pending = await gd.utils.wait(fs)

    .. note::

        This does not raise :exc:`TimeoutError`! Futures that aren't done
        when the timeout occurs are returned in the second set.
    """
    try:
        fs = set(fs)
    except TypeError:  # not iterable 'fs'
        fs = {fs}

    if loop is None:
        loop = acquire_loop()

    fs = {asyncio.ensure_future(f, loop=loop) for f in fs}

    return await asyncio.wait(fs, loop=loop, timeout=timeout, return_when=return_when)


def run(
    coro: Coroutine, *, loop: asyncio.AbstractEventLoop = None,
    debug: bool = False, set_to_none: bool = False
) -> Any:
    """Run a |coroutine_link|_.

    This function runs the passed coroutine, taking care
    of the event loop and shutting down asynchronous generators.

    This function is basically ported from Python 3.7 for backwards compability
    with earlier versions of Python.

    This function cannot be called when another event loop is
    running in the same thread.

    If ``debug`` is ``True``, the event loop will be run in debug mode.

    This function creates a new event loop and closes it at the end if a ``loop`` is ``None``.

    If a loop is given, this function basically calls :meth:`asyncio.AbstractEventLoop.run_until_complete`.

    It should be used as a main entry point to asyncio programs, and should
    ideally be called only once.

    Example:

    .. code-block:: python3

        async def test(pid):
            return pid

        one = gd.utils.run(test(1))

    Parameters
    ----------
    coro: |coroutine_link|_
        Coroutine to run.

    loop: Optional[:class:`asyncio.AbstractEventLoop`]
        A loop to run ``coro`` with. If ``None`` or omitted, a new event loop is created.

    debug: :class:`bool`
        Whether or not to run event loop in debug mode.

    set_to_none: :class:`bool`
        Indicates if the loop should be set to None after execution.

    Returns
    -------
    `Any`
        Anything that ``coro`` returns.
    """
    if asyncio._get_running_loop() is not None:
        raise RuntimeError('Can not perform gd.utils.run() in a running event loop.')

    if not asyncio.iscoroutine(coro):
        raise ValueError('A coroutine was expected, got {!r}.'.format(coro))

    shutdown = False

    if loop is None:
        loop = asyncio.new_event_loop()
        shutdown = True

    try:
        asyncio.set_event_loop(loop)
        loop.set_debug(debug)
        return loop.run_until_complete(coro)

    finally:
        if shutdown:
            shutdown_loop(loop)

        if set_to_none:
            loop = None

        else:
            loop = asyncio.new_event_loop()

        asyncio.set_event_loop(loop)


def cancel_all_tasks(loop: asyncio.AbstractEventLoop) -> None:
    """Cancels all tasks in a loop.

    Parameters
    ----------
    loop: :class:`asyncio.AbstractEventLoop`
        Event loop to cancel tasks in.
    """
    try:
        to_cancel = asyncio.all_tasks(loop)
    except AttributeError:  # py < 3.7
        to_cancel = asyncio.Task.all_tasks(loop)

    if not to_cancel:
        return

    for task in to_cancel:
        task.cancel()

    loop.run_until_complete(
        asyncio.gather(*to_cancel, loop=loop, return_exceptions=True)
    )

    for task in to_cancel:
        if task.cancelled():
            continue

        if task.exception() is not None:
            loop.call_exception_handler({
                'message': 'Unhandled exception during runner shutdown',
                'exception': task.exception(),
                'task': task
            })


def shutdown_loop(loop: asyncio.AbstractEventLoop) -> None:
    try:
        loop.stop()
        cancel_all_tasks(loop)
        loop.run_until_complete(loop.shutdown_asyncgens())

    finally:
        loop.close()


async def maybe_coroutine(func: Callable, *args, **kwargs) -> Any:
    value = func(*args, **kwargs)

    if inspect.isawaitable(value):
        return await value

    else:
        return value


def acquire_loop(running: bool = False) -> None:
    """Gracefully acquire a loop.

    The function tries to get an event loop via :func:`asyncio.get_event_loop`.
    On fail, returns a new loop using :func:`asyncio.new_event_loop`.

    Parameters
    ----------
    running: :class:`bool`
        Indicates if the function should get a loop that is already running.
    """
    try:
        loop = asyncio._get_running_loop()

    except Exception:  # an error might occur actually
        loop = None

    if running and loop is not None:
        return loop

    else:
        try:
            loop = asyncio.get_event_loop()

            if loop.is_running() and not running:
                # loop is running while we have to get the non-running one,
                # let us raise an error to go into <except> clause.
                raise ValueError('Current event loop is already running.')

        except Exception:
            loop = asyncio.new_event_loop()

    return loop


def _get_class_dict(cls: Type[Any]) -> Dict[str, Any]:
    """Gets 'cls.__dict__' that can be edited."""
    for obj in gc.get_objects():

        try:
            if obj == dict(cls.__dict__) and type(obj) is dict:
                return obj

        except Exception:
            continue

    raise ValueError(
        'Failed to find editable __dict__ for {}.'.format(cls)
    )


def _del_method(cls: type, method_name: str):
    """Delete a method of a 'cls'."""
    cls_d = _get_class_dict(cls)
    cls_d.pop(method_name, None)


def _add_method(cls: type, func, *, name: str = None):
    """Adds a new method to a 'cls'."""
    cls_d = _get_class_dict(cls)

    if name is None:
        name = _get_name(func)

    cls_d[name] = func


def _get_name(func):
    try:
        if isinstance(func, property):
            return func.fget.__name__
        elif isinstance(func, (staticmethod, classmethod)):
            return func.__func__.__name__
        else:
            return func.__name__
    except AttributeError:
        raise RuntimeError(
            'Failed to find the name of given function. '
            'Please provide the name explicitly.'
        ) from None


def _run(self, loop: asyncio.AbstractEventLoop = None) -> Any:
    """Run the coroutine in a new event loop,
    closing the loop after execution (if not given).
    """

    if loop is None:
        loop = acquire_loop()

    asyncio.set_event_loop(loop)

    return loop.run_until_complete(self)


async def _async_wrapper(var: object) -> Any:
    try:
        return await var
    except Exception:
        return var


def _asyncwrap(self: object) -> Callable:
    return _async_wrapper(self)


def _enable_method(obj: type, name: str, on: bool = True, func: Callable = None) -> None:
    try:
        if on:
            _add_method(obj, func, name=name)
        else:
            _del_method(obj, name)

    except Exception:
        print('Failed to edit the {!r} method.'.format(name))


def enable_asyncwrap(on: bool = True) -> None:
    """Add or delete '__asyncwrap__' method of objects."""
    _enable_method(object, '__asyncwrap__', on, _asyncwrap)


def enable_run_method(on: bool = True) -> None:
    """Add or delete 'run' method of a coroutine."""
    _enable_method(coroutine, 'run', on, _run)


def synchronize(on: bool = True) -> None:
    enable_asyncwrap(on)
    enable_run_method(on)
