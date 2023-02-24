import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Mapping, Collection

from aiohttp import ClientSession as Client, ClientResponse as Response

ParamType = int | str | Enum | Collection['ParamType'] | None
# Mapping is covariant in the value type, allowing for subclasses of Enum as values.
# dict is invariant in the value type, so we need to use Mapping instead.
ParamsDict = Mapping[str, ParamType]

JsonType = int | float | bool | str | None | list['JsonType'] | dict[str, 'JsonType']
JsonMap = dict[str, JsonType]

class ApiError(Exception):
    status: int
    reason: str|None
    response: Response|None

    def __init__(self, status: int, reason: str|None, response: Response|None):
        super().__init__()
        self.status = status
        self.reason = reason
        self.response = response

    def __str__(self) -> str:
        return super().__str__() + F"\nStatus: {self.status}\nReason: {self.reason}"

class Method(Enum):
    GET = 'GET'
    POST = 'POST'
    PUT = 'PUT'
    DELETE = 'DELETE'
    PATCH = 'PATCH'

@dataclass
class Request:
    method: Method
    url: str
    query_params: dict[str, str|int]= field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    data: JsonMap = field(default_factory=dict)
    data_is_json: bool = False

    def send(self, client: Client):
        json = None
        data = None
        params = None
        headers = None
        if self.data_is_json:
            json = self.data
        elif self.data:
            data = self.data
        if self.headers:
            headers = self.headers
        if self.query_params:
            params = self.query_params
        return client.request(self.method.value, self.url, json=json, data=data, params=params, headers=headers)

async def serve_one_request(host: str, port: int, response_body: str) -> dict[str, str]:
    import aiohttp.web

    query: dict[str, str] = {}
    did_serve_once = asyncio.Semaphore(0)

    server = aiohttp.web.Application()

    async def index_handler(request: aiohttp.web.Request):
        if did_serve_once.locked():
            return aiohttp.web.Response(text="Already handled", status=500)
        for key, value in request.query.items():
            query[key] = value
        did_serve_once.release()
        return aiohttp.web.Response(text=response_body, content_type='text/html')
    server.router.add_get("/", index_handler)

    run_task_ = aiohttp.web._run_app(server, host=host, port=port) # type: ignore ## reportPrivateUsage
    run_task = asyncio.create_task(run_task_)

    await did_serve_once.acquire()
    run_task.cancel()
    try:
        # wait for cancel to finish
        await run_task
    except asyncio.exceptions.CancelledError:
        pass

    return query