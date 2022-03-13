'''A collection of useful classes and functions for asynchronous programming.
'''

from abc import ABC, abstractmethod
import functools
from typing import Coroutine, ParamSpec, TypeVar, Callable, Generator, Generic, AsyncGenerator, Any

T = TypeVar('T')
U = TypeVar('U')

T_Params = ParamSpec("T_Params")
U_Params = ParamSpec("U_Params")

def end_loop_workaround():
    '''Workaround for:
    https://github.com/aio-libs/aiohttp/issues/4324#issuecomment-733884349

    Replace the event loop destructor thing with one a wrapper which ignores
    this specific exception on windows.

    Note:
        Already called by WebAPI's initializer. You shouldn't have to worry about this.
    '''
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
    '''Class which depends on some asynchronous initialization.
    To use, override _async_init() to do the actual initialization.

    Note:
        You should still define a __init__() method to collect parameters for construction.

    Caution:
        Accessing any non-static public attributes before the async initialization is complete will result in an error.

    Example:
        .. code::

            class MyAsyncInit(AsyncInit):
                def __init__(self, param1: str, param2: int):
                    self.param1 = param1
                    self.param2 = param2

                async def _async_init(self):
                    await asyncio.sleep(0.1)
                    self.param3 = self.param1 + str(self.param2)

            inst = await MyAsyncInit("hello", 42)
    '''
    _async_ready = False
    _async_init_coro: Coroutine[Any, Any, Any] | None = None

    
    @abstractmethod
    async def _async_init(self):
        '''Implementation must initialize the instance
        arguments should be already passed to the constructor.
        '''
        pass

    def __await__(self: TSelfAtAsyncClass) -> Generator[Any, Any, TSelfAtAsyncClass]:
        async def combined_init() -> TSelfAtAsyncClass:
            # if self._async_init_coro is None:
            #     raise RuntimeError("Expected AsyncInit subclass to set an initialization coroutine.")
            # else:
            await self._async_init()
            self._async_ready = True
            return self
        return combined_init().__await__()

# protect members from being accessed before async initialization is complete
def _AsyncInit_get_attr(self: AsyncInit, name: str) -> Any:
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
    '''Does not accumulate any results unless awaited.
    Awaiting instances will return a list of the results.
    Can be used as an async iterator.
    '''
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
        return AsyncTrans(self, f)

    @classmethod
    def wrap(cls, fn: Callable[T_Params, AsyncGenerator[T, None]]):
        '''Convert an async generator async function to return an AsyncLazy instance.'''
        @functools.wraps(fn)
        def wrapped(*args: T_Params.args, **kwargs: T_Params.kwargs) -> AsyncLazy[T]:
            return AsyncLazy(fn(*args, **kwargs))
        return wrapped


class AsyncTrans(Generic[U]):
    '''
    Transforms the results of the AsyncLazy generator using the mapping function.
    Awaiting instances will return a list of the transformed results.
    Can be used as an async iterator.
    '''
    gen: AsyncLazy[Any]
    mapping: Callable[[Any], U]

    def __init__(self, gen: AsyncLazy[T], mapping: Callable[[T], U]):
        self.gen = gen
        self.mapping = mapping

    def __aiter__(self):
        return (self.mapping(t) async for t in self.gen)

    def __await__(self) -> Generator[Any, None, list[U]]:
        return self._items().__await__()

    async def _items(self) -> list[U]:
        return [u async for u in self]