'''
Implementation for following classes:

- WebAPI
'''
from dataclasses import asdict
from enum import Enum
import json
from typing import TYPE_CHECKING, Any, AsyncGenerator, Sequence, cast, TypeVar, overload
from typing_extensions import TypeIs
if TYPE_CHECKING:
    from _typeshed import DataclassInstance

from aiohttp import ClientSession as Client
from .asyncy import AsyncLazy, unmanage_async_context
from .auth import Auth
from .web import Request, Method, JsonMap, ParamsDict, ApiError

T = TypeVar('T')

def is_dataclass_instance(obj: object) -> 'TypeIs[DataclassInstance]':
    return hasattr(type(obj), "__dataclass_fields__")

class WebAPI:
    'Base class for web APIs'
    _use_form_data: bool

    _parameter_list_delimiter: str = ','

    base_url: str
    auth: Auth

    _maybe_client: Client | None
    @property
    def _client(self) -> Client:
        if self._maybe_client is None:
            self._maybe_client = Client()
            # Client.__aenter__ returns Client
            (_, self._client_close_context) = unmanage_async_context(self._maybe_client)
        return self._maybe_client

    def __init__(self, auth: Auth, use_form_data: bool = False) -> None:
        self._maybe_client = None
        self.auth = auth
        self._use_form_data = use_form_data

    def __del__(self):
        # free up the client session if its been created
        if hasattr(self, '_client_close_context'):
            try:
                self._client_close_context.set()
            except RuntimeError: # event loop was closed
                if self._client._connector is not None: # type: ignore
                    self._client._connector._close() # type: ignore
                    self._client._connector = None # type: ignore

    # delimit lists and sets, convert enums to their values, and exclude None values
    def _convert_parameters(self, params: ParamsDict) -> dict[str, str|int]:
        converted: dict[str, str|int] = {}
        for k, v in params.items():
            match v:
                case set() if len(v) > 0: # non-empty set
                    first  = next(iter(v))
                    if isinstance(first, Enum): # set of enums
                        v = cast(set[Enum], v)
                        values = [e.value for e in v if e.value is not None]
                        if len(values) > 0:
                            converted[k] = self._parameter_list_delimiter.join(values)
                    else:
                        converted[k] = self._parameter_list_delimiter.join(map(str, v))
                case [Enum(), *_]: # list of enums
                    enums = cast(Sequence[Enum], v)
                    values = [e.value for e in enums if e.value is not None]
                    if len(values) > 0:
                        converted[k] = self._parameter_list_delimiter.join(values)
                case [_, *_]: # non-empty list
                    converted[k] = self._parameter_list_delimiter.join(map(str, v))
                case Enum() if v.value is not None:
                    # print(F"Converting enum {v} to {v.value}")
                    converted[k] = v.value
                case int() | str():
                    converted[k] = v
                case _: pass # exclude None values
        return converted

    def get_full_url(self, path: str) -> str:
        '''Convert a relative path to an absolute url for this API'''
        return self.base_url + path

    # authenticate and use the base URL to make a request
    async def _base_request(self, request: Request) -> str|None:
        request.url = self.get_full_url(request.url)
        signed = await self.auth.sign(self._client, request)
        async with signed.send(self._client) as resp:
            if resp.status >= 400:
                raise await ApiError.from_resposnse(resp)
            elif resp.status == 204:
                return None
            else:
                return await resp.text()

    async def _text_request(self, req: Request) -> str:
        result = await self._base_request(req)
        if result is None:
            raise ApiError(204, 'HTTP No Content returned, but some content was expected', None)
        return result

    async def _json_request(self, req: Request) -> JsonMap:
        return json.loads(await self._text_request(req))

    async def _empty_request(self, req: Request) -> None:
        await self._base_request(req)

    def _create_request(self, method: Method, path: str, params: ParamsDict|None=None, 
        json: Any=None, headers: dict[str, str]|None=None
        ) -> Request:
        return Request( method,
            path, self._convert_parameters(params) if params else {},
            headers or {},
            json, True
        )
    
    def _create_form_request(self, method: Method, path: str, params: ParamsDict|None=None, 
        data: Any=None, headers: dict[str, str]|None=None
        ) -> Request:
        return Request( method,
            path, self._convert_parameters(params) if params else {},
            headers or {},
            data, False
        )
    
    @overload
    async def _request(self, method: Method, returns: None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> None:
        ...

    @overload
    async def _request(self, method: Method, returns: type[T], path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T:
        ...
        

    async def _request_context(self, method: Method, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None):
        if data and hasattr(data, 'to_json'):
            data = data.json()
        elif data and is_dataclass_instance(data):
            data = asdict(data)
        req = await self.auth.sign(self._client,
            Request( method, self.get_full_url(path), 
                self._convert_parameters(params) if params else {},
                headers or {},
                data, not self._use_form_data
            ))
        return req.send(self._client)

    async def _request(self, method: Method, returns: type[T]|None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T|None:
        ctx = await self._request_context(method, path, params, data, headers)
        async with ctx as resp:
            if resp.status >= 400:
                raise await ApiError.from_resposnse(resp)
            if returns is None:
                return None
            elif returns == str:
                return await resp.text() # type: ignore ## T is str
            else:
                obj = await resp.json()
                if hasattr(returns, 'from_json'):
                    return getattr(returns, 'from_json')(obj)
                else:
                    return returns(obj) # type: ignore
    
    @overload
    async def _get(self, returns: None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> None: ...

    @overload
    async def _post(self, returns: None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> None: ...

    @overload
    async def _put(self, returns: None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> None: ...

    @overload
    async def _patch(self, returns: None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> None: ...

    @overload
    async def _delete(self, returns: None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> None: ...
    
    @overload
    async def _get(self, returns: type[T], path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T: ...

    @overload
    async def _post(self, returns: type[T], path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T: ...
    @overload
    async def _put(self, returns: type[T], path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T: ...

    @overload
    async def _patch(self, returns: type[T], path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T: ...

    @overload
    async def _delete(self, returns: type[T], path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T: ...
            
    async def _get(self, returns: type[T]|None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T|None:
        return await self._request(Method.GET, returns, path, params, data, headers)
    
    async def _post(self, returns: type[T]|None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T|None:
        return await self._request(Method.POST, returns, path, params, data, headers)
    
    async def _put(self, returns: type[T]|None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T|None:
        return await self._request(Method.PUT, returns, path, params, data, headers)
    
    async def _patch(self, returns: type[T]|None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T|None:
        return await self._request(Method.PATCH, returns, path, params, data, headers)
    
    async def _delete(self, returns: type[T]|None, path: str, params: ParamsDict|None=None, data: Any = None, headers: dict[str, str]|None=None) -> T|None:
        return await self._request(Method.DELETE, returns, path, params, data, headers)
    
    async def delete_json(self, path: str, params: ParamsDict|None=None, 
        json: Any=None, headers: dict[str, str]|None=None
        ):
        await self._json_request(self._create_request(
            Method.DELETE, path, params, json, headers
        ))

    async def get_json(self, path: str, params: ParamsDict|None=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_request(
            Method.GET, path, params, json, headers
        ))

    async def post_json(self, path: str, params: ParamsDict|None=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_request(
            Method.POST, path, params, json, headers
        ))
    
    async def post_json_empty(self, path: str, params: ParamsDict|None=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ):
        return await self._empty_request(self._create_request(
            Method.POST, path, params, json, headers
        ))


    async def put_json(self, path: str, params: ParamsDict|None=None, 
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_request(
            Method.PUT, path, params, json, headers
        ))
    
    async def get_form(self, path: str, params: ParamsDict|None=None,
        data: Any|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_form_request(
            Method.GET, path, params, data, headers
        ))

    async def post_form(self, path: str, params: ParamsDict|None=None,
        data: Any|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_form_request(
            Method.POST, path, params, data, headers
        ))
    
    async def post_form_empty(self, path: str, params: ParamsDict|None=None,
        data: Any|None=None, headers: dict[str, str]|None=None
        ):
        return await self._empty_request(self._create_form_request(
            Method.POST, path, params, data, headers
        ))

    async def put_form(self, path: str, params: ParamsDict|None=None, 
        data: Any|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_form_request(
            Method.PUT, path, params, data, headers
        ))

    async def get_text(self, path: str, params: ParamsDict|None=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> str:
        return await self._text_request(self._create_request(
            Method.GET, path, params, json, headers
        ))
    
    def paginated(self,
                        path: str,
                        params: ParamsDict,
                        limit: int | None) -> AsyncLazy[JsonMap]:
        '''
        Return an awaitable and async iterable over google or twitter-style paginated items.
        You can also await the return value to get the entire list.
        '''
        return AsyncLazy(self._paginated(path, params, limit))

    async def _paginated(self,
                        path: str,
                        params: ParamsDict,
                        limit: int | None) -> AsyncGenerator[JsonMap, None]:
        result_count = 0

        params = dict(params or {})

        while True:
            page = await self.get_json(path, params)

            items = page.get('items', page.get('data'))

            if not items: break

            for item in cast(list[JsonMap], items):
                result_count += 1
                yield item
                if limit is not None and result_count >= limit:
                    return

            page_token = cast(str, page.get('nextPageToken'))
            if not page_token: break
            params['pageToken'] = page_token