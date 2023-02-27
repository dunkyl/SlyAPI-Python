'''Useful classes and functions for asynchronous programming.'''
import asyncio
import functools
from typing import Coroutine, ParamSpec, TypeVar, Callable, Generator, Generic, AsyncGenerator, Any
from contextlib import AbstractAsyncContextManager

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

def unmanage_async_context_sync(context: AbstractAsyncContextManager[T]) -> tuple[T, asyncio.Semaphore]:
    '''
    Extract an async context manager's value without manually managing its lifetime.
    The context manager is leaked and will only be cleaned up when the program exits.
    '''
    MISSING = object()
    extracted = context
    closed_semaphore = asyncio.Semaphore(0)
    async def background():
        nonlocal extracted
        async with context as _inner:
            print(f'Released semaphore for {context}')
            await closed_semaphore.acquire()
    task = asyncio.create_task(background())
    unmanaged_tasks.add(task)
    task.add_done_callback(unmanaged_tasks.remove)
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
        '''Yield the aggregate results of the generator as a list.'''
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
        '''Yield the aggregate results of the transformed generator as a list.'''
        return self._items().__await__()

    async def _items(self) -> list[U]:
        return [u async for u in self]