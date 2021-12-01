import weakref
from copy import deepcopy
from enum import Enum
from typing import Any, AsyncGenerator, TypeVar, cast

from aiohttp import ClientSession, ClientResponse
from aiohttp.client_exceptions import ContentTypeError

from .asyncy import end_loop_workaround, AsyncInit, AsyncLazy
from .auth import Auth

Json = dict[str, Any]


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


class _EnumParams:
    '''
        Emulate an EnumParam for serialization into URL params.
        Separate class and hidden since Enum's have special behavior.
    '''
    params: dict[str, set[str]]

    def __init__(self):
        self.params = {}

    def __add__(self, other: 'EnumParam|_EnumParams') -> 'EnumParam':
        new_instance = deepcopy(self)
        match other:
            case EnumParam():
                other_items = [(other.get_title(), {other.value})]
            case _EnumParams():
                other_items = other.params.items()
            case _:
                raise
        for k, v in other_items:
            if k not in new_instance.params:
                new_instance.params[k] = set()
            new_instance.params[k] |= v
        return cast(EnumParam, new_instance)

    def to_dict(self, delimiter: str = ',') -> dict[str, str]:
        '''
            Convert packed parameters to a dictionary for use in a URL.
        '''
        return {
            title: delimiter.join(values)
            for title, values in self.params.items()
        }


Self = TypeVar('Self')


class EnumParam(Enum):
    '''
        Collection of API url parameters which have only specific values.
        Serializes to a dictionary for use in a URL.
    '''

    def get_title(self) -> str:
        return self.__class__.__name__[0].lower() + self.__class__.__name__[1:]

    def __add__(self: Self, other: 'EnumParam|_EnumParams') -> Self:
        '''Collect with another parameter or set of parameters.'''
        # return type is compatible with EnumParam for + and to_dict
        return _EnumParams() + self + other  # type: ignore

    def to_dict(self, _delimiter: str = ',') -> dict[str, str]:
        '''
            Convert packed parameters to a dictionary for use in a URL.
        '''
        return {
            self.get_title(): self.value
        }


def convert_url_params(p: Json | None) -> dict[str, str]:
    '''Excludes empty-valued parameters'''
    if p is None: return {}
    return {k: str(v) for k, v in p.items() if v is not None and v != ''}


class WebAPI(AsyncInit):
    base_url: str
    session: ClientSession
    auth: Auth | None

    common_params: dict[str, str]

    async def _init(self, auth: Auth = None):
        await super()._async_init()

        if auth is not None:
            common_headers = auth.get_common_headers()
            self.common_params = auth.get_common_params()
        else:
            common_headers = {}
            self.common_params = {}

        self.auth = auth

        # the aiohttp context manager does no asynchronous work when entering.
        # Using the context is not necessary as long as ClientSession.close() 
        # is called.
        self.session = await ClientSession(
            headers=common_headers).__aenter__()

        # Although ClientSession.close() may be a coroutine, but it is not
        # necessary to await it as of the time of writing, since it's 
        # connector objects delegate their own coroutine close() methods to 
        # only synchronous methods.
        # this method ensures that the session is closed when the WebAPI object
        # is garbage collected.
        # noinspection PyProtectedMember
        self._finalize = weakref.finalize(self, self.session._connector._close)  # type: ignore ## reportPrivateUsage

        end_loop_workaround()

    def close(self):
        '''Closes the http session with the API server. Should be automatic.'''
        self._finalize()

    def _req(self, method: str, path: str, params: Json = None, json: Any = None, data: Any = None):
        return self.session.request(
            method, f"{self.base_url}{path}",
            params=convert_url_params(params) | self.common_params,
            data=data, json=json)

    async def _req_json(self, method: str, path: str, params: Json | None, json: Any, data: Any) -> Any:
        async with self._req(
                method, path,
                params, json, data) as response:
            try:
                result = await response.json()
            except ContentTypeError:
                result = await response.text()
            if response.status != 200:
                raise await api_err(response, result)
            return result

    async def _req_empty(self, method: str, path: str, params: Json | None, json: Any, data: Any) -> None:
        async with self._req(
                method, path,
                params, data, json) as response:
            if response.status != 204:
                raise await api_err(response)

    async def get_json(self, path: str, params: Json = None, json: Any = None, data: Any = None) -> \
            dict[str, Any]:
        return await self._req_json('GET', path, params, json=json, data=data)

    async def post_json(self, path: str, params: Json = None, json: Any = None, data: Any = None) -> \
            dict[str, Any]:
        return await self._req_json('POST', path, params, json=json, data=data)

    async def put_json(self, path: str, params: Json = None, json: Any = None, data: Any = None) -> \
            dict[str, Any]:
        return await self._req_json('PUT', path, params, json=json, data=data)

    @AsyncLazy.wrap
    # TODO: google only?
    async def paginated(self,
                        path: str,
                        params: Json,  # non-const
                        limit: int | None) -> AsyncGenerator[Any, None]:
        '''Return an awaitable and async iterable over google-style paginated items'''
        result_count = 0

        while True:
            page = await self.get_json(path, params)

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

# Endpoint = Callable[[WebAPI, T], Coro[U]]

# def decorator(func: Endpoint[Any, T]) -> Endpoint[Any, T]:
#     async def wrapper(self: WebAPI, params: Json) -> T:
#         return await func(self, params)
#     return wrapper
