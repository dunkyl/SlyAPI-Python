from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timedelta
import functools
from typing import Coroutine, ParamSpec, TypeVar, Callable, Generator, Generic, AsyncGenerator, Any

T = TypeVar('T')
U = TypeVar('U')

T_Params = ParamSpec("T_Params")
U_Params = ParamSpec("U_Params")

class Cooldown:
    
    def __init__(self, *, expiry: datetime | timedelta):
        match expiry:
            case datetime():
                self.expiry = expiry
            case timedelta():
                self.expiry = datetime.now() + expiry
            case _:
                raise TypeError(f"Expiry must be a datetime or timedelta, not {type(expiry)}")

    def poll(self) -> bool:
        return self.expiry > datetime.now()
    
    def __await__(self) -> Generator[Any, Any, None]:
        seconds = (self.expiry - datetime.now()).total_seconds()
        if seconds > 0:
            yield from asyncio.sleep(seconds)
        return

class Stopwatch:
    start_time: datetime | None
    accumulated: timedelta

    def __init__(self):
        self.reset()

    def start(self) -> None:
        self.start_time = datetime.now()

    def stop(self) -> None:
        self.accumulated += datetime.now() - self.start_time

    def reset(self) -> None:
        self.start_time = None
        self.accumulated = timedelta()

    def format(self, include_hours: bool) -> str:
        secs = self.accumulated.total_seconds()
        mins = int(secs // 60)
        secs -= mins * 60
        if not include_hours:
            return f"{mins}m {secs:.0f}s"
        hours = int(mins // 60)
        mins -= hours * 60
        return F"{hours:02}:{mins:02}:{secs:02.0f}"

    def __str__(self) -> str:
        s

def end_loop_workaround():
    # workaround for:
    # https://github.com/aio-libs/aiohttp/issues/4324#issuecomment-733884349

    # Replace the event loop destructor thing with one a wrapper which ignores
    # this specific exception on windows.
    import sys
    if sys.platform.startswith("win"):
        # noinspection PyProtectedMember
        from asyncio.proactor_events import _ProactorBasePipeTransport  # type: ignore

        base_del = _ProactorBasePipeTransport.__del__
        if not hasattr(base_del, '_once'):
            def quiet_delete(*args, **kwargs):  # type: ignore
                try:
                    return base_del(*args, **kwargs)  # type: ignore
                except RuntimeError as e:
                    if str(e) != 'Event loop is closed':
                        raise

            quiet_delete._once = True  # type: ignore

            _ProactorBasePipeTransport.__del__ = quiet_delete


TSelfAtAsyncClass = TypeVar("TSelfAtAsyncClass", bound="AsyncInit")


class AsyncInit(ABC): # Awaitable[TSelfAtAsyncClass]
    '''
    Class which depends on some asynchronous initialization.
    To use, override _async_init() to do the actual initialization.
    Accessing any non-static public attributes before the async initialization is complete will result in an error.
    '''
    _async_ready = False
    _async_init_coro: Coroutine[Any, Any, Any] | None = None

    # implementation must initialize the instance
    # arguments should be already passed to the constructor
    # and this method must set self._async_ready to True
    @abstractmethod
    async def _async_init(self): pass

    # not passing args from constructor to _async_init() anymore
    # both are expected to be implemented in the subclass
    # def __init__(self, *args: Any, **kwargs: Any):
    #     if hasattr(self, '_async_init'):
    #         self._async_init_coro = getattr(self, '_async_init')(*args, **kwargs)
    #     else:
    #         raise RuntimeError("AsyncInit class must implement _async_init().")

    def __await__(self: TSelfAtAsyncClass) -> Generator[Any, Any, TSelfAtAsyncClass]:
        async def combined_init() -> TSelfAtAsyncClass:
            # if self._async_init_coro is None:
            #     raise RuntimeError("Expected AsyncInit subclass to set an initialization coroutine.")
            # else:
            await self._async_init()
            return self
        return combined_init().__await__()

# protect members from being accessed before async initialization is complete
def _AsyncInit_get_attr(self: AsyncInit, name: str) -> Any:
    # name not in ('_async_init_coro', '_async_ready', '__await__')
    # private attributes are allowed to be accessed
    # TODO: consider if all private attributes should be allowed
    # note: order of checks is important
    if not name.startswith('_') and not self._async_ready: # type: ignore
        raise RuntimeError("AsyncInit class must be awaited before accessing public attributes.")
    else:
        return object.__getattribute__(self, name)
# workaround to preserve type checks for accessing undefined methods
# Pylance, at least, will presume __getattribute__ will succeed and
# not raise an AttributeError
setattr(AsyncInit, '__getattribute__', _AsyncInit_get_attr)


class AsyncLazy(Generic[T]):
    '''Does not accumulate any results unless awaited.'''
    gen: AsyncGenerator[T, None]

    def __init__(self, gen: AsyncGenerator[T, None]):
        self.gen = gen

    def __aiter__(self) -> AsyncGenerator[T, None]:
        return self.gen

    async def _items(self) -> list[T]:
        return [t async for t in self.gen]

    def __await__(self) -> Generator[Any, None, list[T]]:
        return self._items().__await__()

    def map(self, f: Callable[[T], U]) -> 'AsyncTrans[U]':
        return AsyncTrans(self.gen, f)

    @classmethod
    def wrap(cls, fn: Callable[T_Params, AsyncGenerator[T, None]]):
        @functools.wraps(fn)
        def wrapped(*args: T_Params.args, **kwargs: T_Params.kwargs) -> AsyncLazy[T]:
            return AsyncLazy(fn(*args, **kwargs))
        return wrapped


class AsyncTrans(Generic[U], AsyncLazy[Any]):
    '''
    Does not accumulate any results unless awaited.
    Transforms the results of the generator using the mapping function.
    '''
    gen: AsyncGenerator[Any, None]
    mapping: Callable[[Any], U]

    def __init__(self, gen: AsyncGenerator[Any, None], mapping: Callable[[Any], U]):
        super().__init__(gen)
        self.mapping = mapping

    def __aiter__(self):
        return (self.mapping(t) async for t in self.gen)

    def __await__(self) -> Generator[Any, None, list[U]]:
        return self._items().__await__()

    async def _items(self) -> list[U]:
        return [u async for u in self]