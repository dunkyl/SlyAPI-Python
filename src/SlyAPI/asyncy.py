'''Useful classes and functions for asynchronous programming.'''
from abc import ABC, abstractmethod
import asyncio
from datetime import datetime, timedelta
import functools
import traceback
from typing import Awaitable, Coroutine, ParamSpec, TypeVar, Callable, Generator, Generic, AsyncGenerator, Any
import warnings

T = TypeVar('T')
U = TypeVar('U')

T_Params = ParamSpec("T_Params")
U_Params = ParamSpec("U_Params")

class Cooldown:
    '''Keeps track of whether a certain amount of time has passed.
    Awaitable.'''
    def __init__(self, *, expiry: datetime | timedelta):
        match expiry:
            case datetime():
                self.expiry = expiry
            case timedelta():
                self.expiry = datetime.now() + expiry
            case _:
                raise TypeError(f"Expiry must be a datetime or timedelta, not {type(expiry)}")

    def poll(self) -> bool:
        '''Returns whether the cooldown has expired yet.'''
        return self.expiry > datetime.now()
    
    def __await__(self) -> Generator[Any, Any, None]:
        seconds = (self.expiry - datetime.now()).total_seconds()
        if seconds > 0:
            yield from asyncio.sleep(seconds)
        return

class Stopwatch:
    '''A simple stopwatch.'''
    start_time: datetime | None
    accumulated: timedelta

    def __init__(self):
        self.reset()

    def start(self) -> None:
        '''Begin timing.'''
        if self.start_time is not None:
            raise RuntimeError("Stopwatch already started")
        self.start_time = datetime.now()

    def stop(self) -> timedelta:
        '''Pause timing and return the current time elapsed.'''
        if self.start_time is None:
            raise RuntimeError("Stopwatch not started")
        self.accumulated += datetime.now() - self.start_time
        self.start_time = None
        return self.accumulated

    def reset(self) -> None:
        '''Reset the stopwatch to zero and stop it.'''
        self.start_time = None
        self.accumulated = timedelta()

    def format(self, include_hours: bool) -> str:
        '''Return a string representation of the time elapsed.
        
        Returns:
            str like "MM:SS.02", or "HH:MM:SS.02" if `include_hours` is True.
        '''
        secs = self.accumulated.total_seconds()
        mins = int(secs // 60)
        secs -= mins * 60
        if not include_hours:
            return f"{mins}m {secs:.0f}s"
        hours = int(mins // 60)
        mins -= hours * 60
        return F"{hours:02}:{mins:02}:{secs:02.0f}"

    async def wait_until(self, target_elapsed: timedelta, timeout: timedelta | None = None) -> bool:
        '''Wait until the accumulated time reaches the specified amount.

        Note:
            The precision in time of the stopwatch is approximate, it 
            may return a little late.

        Note:
            If the stopwatch is paused once or more while waiting,
            this may wait for much longer than `accumulation`, perhaps
            even forever.

        Returns:
            True if the time has reached the specified amount, False if the timeout was reached.
        '''
        timeout_expires = \
            datetime.now() + timeout if timeout is not None \
                else None
        while True:
            # wait at least as long as it would take to reach the target time, if there was no stop()
            wait_time_left = (target_elapsed - self.accumulated).total_seconds()
            expire_time_left = \
                (timeout_expires - datetime.now()).total_seconds() if timeout_expires is not None \
                    else wait_time_left
            await asyncio.sleep(max(0, min(wait_time_left, expire_time_left)))
            if self.accumulated >= target_elapsed:
                return True
            if timeout_expires is not None and datetime.now() >= timeout_expires:
                return False



    def __str__(self) -> str:
        return self.format(False)

TSelfAtAsyncClass = TypeVar("TSelfAtAsyncClass", bound="AsyncInit")
TAsyncInitClass = TypeVar("TAsyncInitClass", bound="AsyncInit")


class PendingInit(Generic[TAsyncInitClass]):
    '''Temporary value to hold an AsyncInit instance until it is awaited.'''
    _async_uinit_inst: TAsyncInitClass
    _was_awaited: bool = False

    def __init__(self, uninit_inst: TAsyncInitClass, args, kwargs):
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

def run_sync_ensured(coro: Coroutine[Any, None, None]) -> None:
    '''Run a coroutine, regardless of whether it is already running in an event loop.'''
    try:
        event_loop = asyncio.get_running_loop()
        asyncio.create_task(coro)
    except RuntimeError:
        event_loop = asyncio.new_event_loop()
        event_loop.run_until_complete(coro)

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
    async def __init__(self, *args, **kwargs) -> None: pass

    def __new__(cls: type[TSelfAtAsyncClass], *args, **kwargs) -> Awaitable[TSelfAtAsyncClass]:
        inst = object.__new__(cls)
        
        if not asyncio.iscoroutinefunction(cls.__init__):
            warnings.warn(F"{cls.__name__}.__init__ should be async.", RuntimeWarning, 2)

        return PendingInit(inst, args, kwargs)

    def __await__(self: TSelfAtAsyncClass) -> Generator[Any, Any, TSelfAtAsyncClass]:
        raise NotImplemented()

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