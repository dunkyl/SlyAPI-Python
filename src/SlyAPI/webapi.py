'''
Implementation for following classes:

- WebAPI
'''
from enum import Enum
import asyncio
import json
from typing import Any, AsyncGenerator, cast

from aiohttp import ClientSession as Client, ContentTypeError
from .asyncy import AsyncLazy, unmanage_async_context_sync
from .auth import Auth
from .web import Request, Method, JsonMap, ParamsDict, ApiError

class WebAPI:
    'Base class for web APIs'
    _client: Client
    _client_close_semaphone: asyncio.Semaphore
    _parameter_list_delimiter: str = ','

    base_url: str
    auth: Auth

    def __init__(self, auth: Auth) -> None:
        self._client, self._client_close_semaphone = unmanage_async_context_sync(Client())
        self.auth = auth

    def __del__(self):
        # free up the client session
        try:
            self._client_close_semaphone.release()
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
                    values = [e.value for e in v if e.value is not None]
                    if len(values) > 0:
                        converted[k] = self._parameter_list_delimiter.join(values)
                case [_, *_]: # non-empty list
                    converted[k] = self._parameter_list_delimiter.join(map(str, v))
                case Enum() if v.value is not None:
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
                try:
                    reason = await resp.text()
                except ContentTypeError as _:
                    reason = None
                raise ApiError(resp.status, reason, resp)
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
        params = dict(params) if params else {}

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