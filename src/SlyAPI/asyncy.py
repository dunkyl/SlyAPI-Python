import functools
from typing import Awaitable, Coroutine, TypeVar, Callable, Generator, Generic, AsyncGenerator, Any

T = TypeVar('T')
U = TypeVar('U')


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


class AsyncInit(): # Awaitable[TSelfAtAsyncClass]
    '''
    Class which depends on some asynchronous initialization.
    To use, override _init() to do the actual initialization with call to super()._init().
    Accessing any non-static public attributes before the async initialization is complete will result in an error.
    # TODO: result in an error
    '''
    _async_ready = False
    _async_init_coro: Coroutine[Any, Any, Any] | None = None

    def __init__(self, *args: Any, **kwargs: Any):
        if hasattr(self, '_async_init'):
            self._async_init_coro = getattr(self, '_async_init')(*args, **kwargs)
        else:
            raise RuntimeError("AsyncInit class must implement _async_init().")

    def __await__(self: TSelfAtAsyncClass) -> Generator[Any, Any, TSelfAtAsyncClass]:
        async def combined_init() -> TSelfAtAsyncClass:
            if self._async_init_coro is None:
                raise RuntimeError("Expected AsyncInit subclass to set an initialization coroutine.")
            else:
                await self._async_init_coro
                self._async_ready = True
                return self
        return combined_init().__await__()


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
    def wrap(cls, fn: Callable[[Any, ...], AsyncGenerator[T, None]]):
        @functools.wraps(fn)
        def wrapped(*args: Any, **kwargs: Any) -> AsyncLazy[T]:
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