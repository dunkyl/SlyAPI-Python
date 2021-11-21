# import os.path, asyncio, json, hashlib, sys
# import http.server, urllib.parse, webbrowser, secrets
import weakref
from enum import Enum
# from json.decoder import JSONDecodeError
# import datetime as dt
# from dataclasses import dataclass
from typing import Any, AsyncGenerator, Callable, Generic, TypeVar, cast

# import base64
# from hashlib import sha1
# import hmac
# import secrets

# from urllib.parse import urlencode

# from copy import deepcopy, copy

from collections.abc import Coroutine

import hashlib

from aiohttp import ClientSession, ClientResponse

def nc_hash(x: str) -> str:
    h = hashlib.new('ripemd160')
    h.update(x.encode('utf8'))
    return h.hexdigest()

T = TypeVar('T')
U = TypeVar('U')

Json = dict[str, 'Json'] | list['Json'] | str | int | float | None
JsonMap = dict[str, Json]
JsonScalar = str | int | float | None
Coro = Coroutine[Any, Any, T]
GenOrAsync = AsyncGenerator[T, list[T]]

class AsyncLazy(Generic[T]):
    '''Does not accumulate any results unless awaited.'''
    gen: AsyncGenerator[T, None]

    def __init__(self, gen: AsyncGenerator[T, None]):
        self.gen = gen

    async def __aiter__(self) -> AsyncGenerator[T, None]:
        return self.gen

    async def _items(self) -> list[T]:
        return [t async for t in self.gen]

    def __await__(self):
        return self._items().__await__()

    def map(self, f: Callable[[T], U]) -> 'AsyncTrans[U]':
        return AsyncTrans(self.gen, f)

class AsyncTrans(AsyncLazy[Any], Generic[U]):
    '''
    Does not accumulate any results unless awaited.
    Transforms the results of the generator using the mapping function.
    '''
    gen: AsyncGenerator[Any, None]
    mapping: Callable[[Any], U]

    def __init__(self, gen: AsyncGenerator[Any, None], mapping: Callable[[Any], U]):
        super().__init__(gen)
        self.mapping = mapping

    async def __aiter__(self):
        return (self.mapping(t) async for t in self.gen)

    async def _items(self) -> list[U]:
        return [self.mapping(t) async for t in self.gen]

class APIError(Exception):
    status: int
    reason: Any

    def __init__(self, status: int, reason: Any):
        super().__init__()
        self.status = status
        self.reason = reason

    def __str__(self) -> str:
        return super().__str__() + F"\nStatus: {self.status}\nReason: {self.reason}"

class EnumParam(Enum):
    _params: list['EnumParam']
    
    def __str__(self) -> str:
        return self.value

    def _get_title(self) -> str:
        return self.__class__.__name__.lower()

    def __add__(self, other: 'EnumParam'):
        if not hasattr(self, '_params'):
            setattr(self, '_params', [self])
        self._params.append(other)
        return self

    def to_dict(self, delimiter: str=',') -> dict[str, str]:
        # TODO: If the value of a param is None, it should be omitted.
        if not hasattr(self, '_params'):
            setattr(self, '_params', [self])
        params: dict[str, str] = {}
        for param in self._params:
            title = param._get_title()
            if not title in params:
                params[title] = param.value
            else:
                params[title] += delimiter+param.value
        return params

async def api_err(response: ClientResponse, result: Json = None) -> APIError:
    match result:
        case {'message': msg}:
            return APIError(response.status, msg)
        case _:
            return APIError(response.status, await response.text())

class Paginator:
    pass

from .oauth2 import OAuth2User
from .oauth1 import OAuth1User

def convert_url_params(p: dict[str, Any]|None) -> dict[str, str]:
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

    def close(self):
        self._finalize() 

    def _req(self, method: str, path: str, params: dict[str, Any]|None=None, json: Any=None, data: Any=None):
        return self.session.request(
                method, f"{self.base_url}{path}",
                params = convert_url_params(params)|self.add_params,
                data = data, json = json )

    async def _req_json(self, method: str, path: str, params: dict[str, Any], json: Any, data: Any) -> Any:
        async with self._req(
                method, f"{self.base_url}{path}",
                params, json, data ) as response:
            result = await response.json()
            if response.status != 200:
                raise await api_err(response, result)
            return result
    
    async def _req_empty(self, method: str, path: str, params: dict[str, Any], json: Any, data: Any) -> None:
        async with self._req(
                method, f"{self.base_url}{path}",
                params, data, json ) as response:
            if response.status != 204:
                raise await api_err(response)

    async def get_json(self, path: str, params: dict[str, Any], json: Any=None, data: Any=None) -> dict[str, Any]:
        return await self._req_json('GET', F"{self.base_url}{path}", params, json=json, data=data)

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

            result_count += len(items)
            for item in items:
                if limit is not None and result_count >= limit:
                    break
                result_count += 1
                yield item
            
            page_token = cast(str, page.get('nextPageToken'))
            if not page_token: break
            params['pageToken'] = page_token

    def paginated(self,
        method: Callable[[str, dict[str, Any]], Coro[Any]],
        path: str,
        params: dict[str, Any], # non-const
        limit: int|None) -> AsyncLazy[Any]:
        return AsyncLazy(self._paginated(method, path, params, limit))

# Endpoint = Callable[[WebAPI, T], Coro[U]]

# def decorator(func: Endpoint[Any, T]) -> Endpoint[Any, T]:
#     async def wrapper(self: WebAPI, params: dict[str, Any]) -> T:
#         return await func(self, params)
#     return wrapper