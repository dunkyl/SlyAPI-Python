from enum import Enum
import json
from typing import Any, AsyncGenerator, cast

from aiohttp import ClientSession as Client

from .asyncy import AsyncLazy, run_sync_ensured
from .auth import Auth
from .web import Request, Method, JsonMap, ParamsDict, ApiError


# T = TypeVar('T')
# @dataclass
# class APIObj(Generic[T]):
#     _service: T

#     def __init__(self, service: T):
#         self._service = service

class WebAPI():
    _client: Client
    _parameter_list_delimiter: str = ','

    base_url: str
    auth: Auth

    def __init__(self, auth:Auth) -> None:
        self._client = Client()
        self.auth = auth

    def __del__(self):
        if hasattr(self, '_session'):
            run_sync_ensured(self._client.close())

    # delimit lists and sets, convert enums to their values, and exclude None values
    def _convert_parameters(self, params: dict[str, Any]|None) -> dict[str, Any]:
        if params is None: return {}
        converted = {}
        for k, v in params.items():
            if v is None:
                continue
            elif isinstance(v, (list, set)):
                if len(v) != 0:
                    if isinstance(v.__iter__().__next__(), Enum):
                        v = (e.value for e in v)
                    converted[k] = self._parameter_list_delimiter.join(v)
            elif isinstance(v, Enum):
                converted[k] = v.value
            else:
                converted[k] = v
        return converted

    # convert a relative path to an absolute url for this api
    def get_full_url(self, path: str) -> str:
        '''convert a relative path to an absolute url for this api'''
        return self.base_url + path

    # authenticate and use the base URL to make a request
    async def _base_request(self, request: Request) -> str|None:
        request.url = self.get_full_url(request.url)
        signed = await self.auth.sign(self._client, request)
        async with signed.send(self._client) as resp:
            if resp.status >= 400:
                raise ApiError(resp.status, resp.reason, resp)
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

    def _create_request(self, method: Method, path: str, params: ParamsDict=None, 
        json: Any=None, headers: dict[str, str]|None=None
        ) -> Request:
        return Request( method,
            path, self._convert_parameters(params),
            headers or {},
            json, True
        )

    # TODO: _create_form_request

    async def get_json(self, path: str, params: ParamsDict=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_request(
            Method.GET, path, params, json, headers
        ))

    async def post_json(self, path: str, params: ParamsDict=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_request(
            Method.POST, path, params, json, headers
        ))

    async def put_json(self, path: str, params: ParamsDict=None, 
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> JsonMap:
        return await self._json_request(self._create_request(
            Method.PUT, path, params, json, headers
        ))

    async def get_text(self, path: str, params: ParamsDict=None,
        json: JsonMap|None=None, headers: dict[str, str]|None=None
        ) -> str:
        return await self._text_request(self._create_request(
            Method.GET, path, params, json, headers
        ))

    @AsyncLazy.wrap
    async def paginated(self,
                        path: str,
                        params: ParamsDict,
                        limit: int | None) -> AsyncGenerator[JsonMap, None]:
        '''
        Return an awaitable and async iterable over google or twitter-style paginated items.
        You can also await the return value to get the entire list.
        '''
        result_count = 0
        params = params.copy() if params else {}

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