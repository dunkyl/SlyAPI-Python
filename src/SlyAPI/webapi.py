import weakref
from enum import Enum
from typing import Any, AsyncGenerator, Callable, Generator, Generic, TypeVar, cast, Awaitable

from collections.abc import Coroutine

from aiohttp import ClientSession, ClientResponse
from aiohttp.client_exceptions import ContentTypeError

from copy import deepcopy

T = TypeVar('T')
U = TypeVar('U')

Coro = Coroutine[Any, Any, T]

class AsyncLazy(Generic[T], Awaitable[list[T]]):
    '''Does not accumulate any results unless awaited.'''
    gen: AsyncGenerator[T, None]

    def __init__(self, gen: AsyncGenerator[T, None]):
        self.gen = gen

    def __aiter__(self) -> AsyncGenerator[T, None]:
        return self.gen

    async def _items(self) -> list[T]:
        return [t async for t in self.gen]

    def __await__(self) -> Generator[Any, Any, list[T]]:
        return self._items().__await__()

    def map(self, f: Callable[[T], U]) -> 'AsyncTrans[U]':
        return AsyncTrans(self.gen, f)

class AsyncTrans(Generic[U], Awaitable[list[U]], AsyncLazy[Any], ):
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

    async def _items(self) -> list[U]:
        return [u async for u in self]

class APIError(Exception):
    status: int
    reason: Any

    def __init__(self, status: int, reason: Any):
        super().__init__()
        self.status = status
        self.reason = reason

    def __str__(self) -> str:
        return super().__str__() + F"\nStatus: {self.status}\nReason: {self.reason}"

class _EnumParams:
    '''
        Emulate an EnumParam for serialization into URL params.
        Separate class and hidden since Enum's have special behavior.
    '''
    params: dict[str, set[str]]

    def __init__(self):
        self.params = {}

    def __add__(self, other: 'EnumParam|_EnumParams') -> '_EnumParams':
        new_instance = _EnumParams()
        match other:
            case EnumParam():
                other_items = [(other.get_title(), set([other.value]))]
            case _EnumParams():
                other_items = other.params.items()
        for k, v in other_items:
            if k not in new_instance.params:
                new_instance.params[k] = set()
            new_instance.params[k] |= v
        return new_instance

    def to_dict(self, delimiter: str=',') -> dict[str, str]:
        '''
            Convert packed parameters to a dictionary for use in a URL.
        '''
        return {
            title: delimiter.join(values)
            for title, values in self.params.items()
        }

class EnumParam(Enum):
    '''
        Collection of API url parameters which have only specific values.
        Serializes to a dictionary for use in a URL.
    '''
    
    def get_title(self) -> str:
        return self.__class__.__name__[0].lower()+self.__class__.__name__[1:]

    def __add__(self: T, other: 'Self|_EnumParams') -> T:
        '''Collect with another parameter or set of parameters.'''
        params = _EnumParams()
        params += self
        params += other

        # return type is compatible with EnumParam for + and to_dict
        return cast(EnumParam, params)
    
    def to_dict(self, delimiter: str=',') -> dict[str, str]:
        '''
            Convert packed parameters to a dictionary for use in a URL.
        '''
        return {
            self.get_title(): self.value
        }

async def api_err(response: ClientResponse, result: Any = None) -> APIError:
    match result:
        case {'message': msg}:
            return APIError(response.status, msg)
        case _:
            return APIError(response.status, await response.text())

from .oauth2 import OAuth2User
from .oauth1 import OAuth1User

def convert_url_params(p: dict[str, Any]|None) -> dict[str, str]:
    '''Excludes empty-valued parameters'''
    if p is None: return {}
    return {k: str(v) for k, v in p.items() if v is not None and v != ''}

class WebAPI:
    base_url: str
    session: ClientSession
    auth: OAuth2User | OAuth1User | dict[str, str] | None
    add_params: dict[str, str]

    def __init__(self,
        base_url: str|None=None,
        auth: OAuth2User | OAuth1User | dict[str, str] | None = None):

        if base_url: self.base_url = base_url
        if not self.base_url:
            raise ValueError("base_url is required")

        headers: dict[str, str]|None = None
        match auth:
            case OAuth2User():
                headers = auth.get_headers()
                self.add_params = {}
            case OAuth1User():
                pass # TODO
                self.add_params = {}
            case {**params}:
                self.add_params = params
            case None:
                self.add_params = {}

        self.auth = auth

        # the aiohttp context manager does no asynchronous work when entering.
        # Using the context is not necessary as long as ClientSession.close() 
        # is called.
        self.session = ClientSession(headers=headers)
        
        # Although ClientSession.close() may be a coroutine, but it is not
        # necessary to await it as of the time of writing, since it's 
        # connector objects delegate their own coroutine close() methods to 
        # only synchronous methods.
        # this method ensures that the session is closed when the WebAPI object
        # is garbage collected.
        self._finalize = weakref.finalize(self, self.session._connector._close) # type: ignore ## reportPrivateUsage

        # workaround for:
        # https://github.com/aio-libs/aiohttp/issues/4324#issuecomment-733884349

        # Replace the event loop destructor thing with one a wrapper which ignores
        # this specific exception on windows.
        import sys
        if sys.platform.startswith("win"):
            from asyncio.proactor_events import _ProactorBasePipeTransport # type: ignore

            base_del = _ProactorBasePipeTransport.__del__
            if not hasattr(base_del, '_once'):
                def quiet_delete(*args, **kwargs): # type: ignore
                    try:
                        return base_del(*args, **kwargs) # type: ignore
                    except RuntimeError as e:
                        if str(e) != 'Event loop is closed':
                            raise
                quiet_delete._once = True # type: ignore

                _ProactorBasePipeTransport.__del__ = quiet_delete

    def close(self):
        '''Closes the http session with the API server. Should be automatic.'''
        self._finalize() 

    def _req(self, method: str, path: str, params: dict[str, Any]|None=None, json: Any=None, data: Any=None):
        return self.session.request(
                method, f"{self.base_url}{path}",
                params = convert_url_params(params)|self.add_params,
                data = data, json = json )

    async def _req_json(self, method: str, path: str, params: dict[str, Any]|None, json: Any, data: Any) -> Any:
        async with self._req(
                method, path,
                params, json, data ) as response:
            try:
                result = await response.json()
            except ContentTypeError:
                result = await response.text()
            if response.status != 200:
                raise await api_err(response, result)
            return result
    
    async def _req_empty(self, method: str, path: str, params: dict[str, Any]|None, json: Any, data: Any) -> None:
        async with self._req(
                method, path,
                params, data, json ) as response:
            if response.status != 204:
                raise await api_err(response)

    async def get_json(self, path: str, params: dict[str, Any]|None=None, json: Any=None, data: Any=None) -> dict[str, Any]:
        return await self._req_json('GET', path, params, json=json, data=data)

    async def _paginated(self,
        method: Callable[[str, dict[str, Any]], Coro[Any]],
        path: str,
        params: dict[str, Any], # non-const
        limit: int|None) -> AsyncGenerator[Any, None]:

        result_count = 0

        while True:
            page = await method(path, params)

            items = page.get('items')

            if not items: break

            # result_count += len(items)
            for item in items:
                result_count += 1
                yield item
                if limit is not None and result_count >= limit:
                    return
            
            page_token = cast(str, page.get('nextPageToken'))
            if not page_token: break
            params['pageToken'] = page_token

    def paginated(self,
        method: Callable[[str, dict[str, Any]], Coro[Any]],
        path: str,
        params: dict[str, Any], # non-const
        limit: int|None) -> AsyncLazy[Any]:
        '''Return an awaitable and async iterable over google-style paginated items'''
        return AsyncLazy(self._paginated(method, path, params, limit))

# Endpoint = Callable[[WebAPI, T], Coro[U]]

# def decorator(func: Endpoint[Any, T]) -> Endpoint[Any, T]:
#     async def wrapper(self: WebAPI, params: dict[str, Any]) -> T:
#         return await func(self, params)
#     return wrapper