from dataclasses import dataclass
from enum import Enum
from typing import Any, AsyncGenerator, Generic, TypeVar, cast

from aiohttp import ClientSession, ClientResponse
from aiohttp.client_exceptions import ContentTypeError

from .asyncy import AsyncInit, AsyncLazy, run_sync_ensured
from .auth import Auth
from .web import Request, Method

Json = int | float | bool | str | None | list['Json'] | dict[str, 'Json']
JsonObj = dict[str, Json]

class APIError(Exception):
    status: int
    reason: Any

    def __init__(self, status: int, reason: Any):
        super().__init__()
        self.status = status
        self.reason = reason

    def __str__(self) -> str:
        return super().__str__() + F"\nStatus: {self.status}\nReason: {self.reason}"


async def api_err(response: ClientResponse, result: Any = None) -> APIError:
    match result:
        case {'message': msg}:
            return APIError(response.status, msg)
        case _:
            return APIError(response.status, await response.text())

Self = TypeVar('Self', bound='EnumParam')

class EnumParam(Enum):
    '''Enum for use as a parameter in a request, with utitily for aggregating multiple values.'''
    _values: set[str]

    @property
    def values(self) -> set[str]:
        if not hasattr(self, '_values'):
            self._values = { self.value, }
        return self._values

    def __add__(self: Self, other: Self) -> Self:
        inst = self.__class__(self.value)
        inst.values.add(other.value)
        return inst

    def __eq__(self, other: 'EnumParam') -> bool:
        return self._values == other._values

    def __contains__(self: Self, other: Self) -> bool:
        return other.value in self.values

    @classmethod
    def get_title(cls) -> str:
        return cls.__name__[0].lower() + cls.__name__[1:]

    # def to_dict(self, delimiter: str = ',') -> dict[str, str]:
    #     return {
    #         self.get_title(): delimiter.join(self.values)
    #     }

def combine_params(*params: EnumParam, delimiter=',') -> JsonObj:
    '''Combines multiple EnumParams into a single dict'''
    results: dict[str, set[str]] = {}
    for param in params:
        title = param.get_title()
        results[title] = results.get(title, set()).union(param.values)
    return {
        k: delimiter.join(v) for k, v in results.items()
    }

def convert_url_params(p: JsonObj | None) -> dict[str, str]:
    '''Excludes empty-valued parameters'''
    if p is None: return {}
    return {k: str(v) for k, v in p.items() if v is not None and v != ''}

T = TypeVar('T')
@dataclass
class APIObj(Generic[T]):
    _service: T

    def __init__(self, service: T):
        self._service = service

class WebAPI(AsyncInit):
    base_url: str
    _session: ClientSession
    auth: Auth | None

    async def __init__(self, auth:Auth|None=None) -> None:
        self.auth = auth
        self._session = await ClientSession().__aenter__()

    def __del__(self):
        if hasattr(self, '_session'):
            run_sync_ensured(self._session.close())

    # convert a relative path to an absolute url for this api
    def get_full_url(self, path: str) -> str:
        '''convert a relative path to an absolute url for this api'''
        return self.base_url + path

    async def _req_json(self, req: Request) -> Any:
        async with req.send(self._session) as resp:
            try:
                result = await resp.json()
            except ContentTypeError:
                result = await resp.text()
            if resp.status >= 300 or resp.status < 200:
                raise await api_err(resp, result)
            return result

    async def _req_text(self, req: Request) -> str:
        async with req.send(self._session) as resp:
            result = await resp.text()
            if resp.status != 200:
                raise await api_err(resp, result)
            return result

    async def _req_empty(self, req: Request) -> None:
        async with req.send(self._session) as resp:
            if resp.status != 204:
                raise await api_err(resp)

    def _prepare_req(self, method: Method, path: str, params: JsonObj | None,
        json: Any, data: Any, headers: dict[str, str] | None = None
        ) -> Request:
        full_url = self.get_full_url(path)
        if json is not None:
            data_ = json
            data_is_json = True
        else:
            data_ = data
            data_is_json = False
        if data_ is None:
            data_: dict[str, Any] = {}
        if headers is None:
            headers = {}
        return Request(method, full_url, convert_url_params(params), headers, data_, data_is_json)

    async def _call(self, method: Method, path: str, params: JsonObj | None,
        json: Any, data: Any, headers: dict[str, str] | None = None
        ) -> dict[str, Any]:
        req = self._prepare_req(method, path, params, json, data, headers)
        if self.auth is not None:
            req = await self.auth.sign_request(self._session, req)
        return await self._req_json(req)

    async def get_json(self, path: str, params: JsonObj | None=None, 
        json: Any=None, data: Any=None, headers: dict[str, str] | None=None
        ) -> dict[str, Any]:
        return await self._call(Method.GET, path, params, json, data, headers)

    async def post_json(self, path: str, params: JsonObj | None=None, 
        json: Any=None, data: Any=None, headers: dict[str, str] | None=None
        ) -> dict[str, Any]:
        return await self._call(Method.POST, path, params, json, data, headers)

    async def put_json(self, path: str, params: JsonObj | None=None, 
        json: Any=None, data: Any=None, headers: dict[str, str] | None=None
        ) -> dict[str, Any]:
        return await self._call(Method.PUT, path, params, json, data, headers)

    async def get_text(self, path: str, params: JsonObj | None=None,
        json: Any=None, data: Any=None, headers: dict[str, str] | None=None
        ) -> str:
        req = self._prepare_req(Method.GET, path, params, json, data, headers)
        return await self._req_text(req)

    @AsyncLazy.wrap
    async def paginated(self,
                        path: str,
                        params: JsonObj,  # non-const
                        limit: int | None) -> AsyncGenerator[JsonObj, None]:
        '''
        Return an awaitable and async iterable over google or twitter-style paginated items.
        You can also await the return value to get the entire list.
        '''
        result_count = 0

        while True:
            page = await self.get_json(path, params)

            items = page.get('items', page.get('data'))

            if not items: break

            for item in items:
                result_count += 1
                yield item
                if limit is not None and result_count >= limit:
                    return

            page_token = cast(str, page.get('nextPageToken'))
            if not page_token: break
            params['pageToken'] = page_token