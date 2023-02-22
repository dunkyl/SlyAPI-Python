'''Useful classes and functions for asynchronous programming.'''
from abc import ABC, abstractmethod
import asyncio
import functools
import traceback
from typing import Awaitable, Coroutine, ParamSpec, TypeVar, Callable, Generator, Generic, AsyncGenerator, Any
from contextlib import AbstractAsyncContextManager
import warnings

T = TypeVar('T')
U = TypeVar('U')

T_Params = ParamSpec("T_Params")
U_Params = ParamSpec("U_Params")

def run_sync_ensured(corofn: Callable[[], Coroutine[Any, None, None]]) -> None:
    '''Run a coroutine, regardless of whether there is already an event loop.'''
    try:
        event_loop = asyncio.get_running_loop()
        asyncio.create_task(corofn())
    except RuntimeError:
        event_loop = asyncio.get_event_loop_policy().get_event_loop()
        event_loop.run_until_complete(corofn())

unmanaged_tasks: set[Any] = set()
async def unmanage_async_context(context: AbstractAsyncContextManager[T]) -> tuple[T, asyncio.Semaphore]:
    '''
    Extract an async context manager's value without manually managing its lifetime.
    The context manager is leaked and will only be cleaned up when the program exits.
    '''
    MISSING = object()
    extracted = MISSING
    extracted_semaphore = asyncio.Semaphore(0)
    closed_semaphore = asyncio.Semaphore(0)
    async def background():
        nonlocal extracted
        async with context as inner:
            extracted = inner
            extracted_semaphore.release()
            print(f'Released semaphore for {context}')
            await closed_semaphore.acquire()
    task = asyncio.create_task(background())
    unmanaged_tasks.add(task)
    task.add_done_callback(unmanaged_tasks.remove)
    await extracted_semaphore.acquire()
    if extracted is MISSING:
        raise RuntimeError('Async context manager did not return a value.')
    else:
        return (
            extracted, # type: ignore
            closed_semaphore )

class AsyncLazy(Generic[T]):
    '''
    Async iterator which does not accumulate any results unless awaited.
    Awaiting instances will return a list of the results.
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
    Transforms the results of the AsyncLazy generator using the provided mapping function.
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

TSelfAtAsyncClass = TypeVar("TSelfAtAsyncClass", bound="AsyncInit")
TAsyncInitClass = TypeVar("TAsyncInitClass", bound="AsyncInit")


class PendingInit(Generic[TAsyncInitClass]):
    '''Temporary value to hold an AsyncInit instance until it is awaited.'''
    _async_uinit_inst: TAsyncInitClass
    _was_awaited: bool = False

    def __init__(self, uninit_inst: TAsyncInitClass, args: 'tuple[*Any]', kwargs: dict[str, Any]):
        self._async_uinit_inst = uninit_inst
        stackframe = traceback.extract_stack()[-3]
        self._construction_site = (stackframe.filename, stackframe.lineno or 0)
        self._init_args = args
        self._init_kwargs = kwargs

    def __await__(self) -> Generator[Any, Any, TAsyncInitClass]:
        self._was_awaited = True
        return self._init_and_return_inst().__await__()

    async def _init_and_return_inst(self) -> TAsyncInitClass:
        await self._async_uinit_inst.__init__(*self._init_args, **self._init_kwargs)
        return self._async_uinit_inst

    def __getattribute__(self, item: str) -> Any:
        if not item.startswith('_'):
            raise RuntimeError("AsyncInit class must be awaited before accessing public attributes.")
        return super().__getattribute__(item)

    def __del__(self):
        if not self._was_awaited:
            offendingName = self._async_uinit_inst.__class__.__name__
            warnings.warn_explicit(
                F"AsyncInit class {offendingName}'s construction was never awaited!",
                RuntimeWarning,
                *self._construction_site
            )

class AsyncInit(ABC): # Awaitable[TSelfAtAsyncClass]
    '''Class which depends on some asynchronous initialization.
    Subclass AsyncInit and define an __init__ method which is async.

    Note:
        Some analysis tools will show a type error unless __init__ is annotated with an explicit return type of `None`.

    Caution:
        Accessing any non-static public attributes before the async initialization is complete will result in an error.

    Example:
        class MyAsyncInit(AsyncInit):
            async def __init__(self, param1):
                self.easy_value = param1
                # do some async stuff
                await asyncio.sleep(0.1)
                self.hard_value = "this took a while to retrive"

        inst = await MyAsyncInit(42)
    '''
    
    @abstractmethod
    async def __init__(self, *args: Any, **kwargs: Any) -> None: pass

    def __new__(cls: type[TSelfAtAsyncClass], *args: Any, **kwargs: Any) -> Awaitable[TSelfAtAsyncClass]:
        inst = object.__new__(cls)
        
        if not asyncio.iscoroutinefunction(cls.__init__):
            warnings.warn(F"{cls.__name__}.__init__ should be async.", RuntimeWarning, 2)

        return PendingInit(inst, args, kwargs)

    def __await__(self: TSelfAtAsyncClass) -> Generator[Any, Any, TSelfAtAsyncClass]:
        raise NotImplementedError()