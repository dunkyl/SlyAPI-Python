import asyncio
from dataclasses import dataclass, field
import datetime
from enum import Enum
import collections.abc
from aiohttp import ClientSession as Client, ClientResponse as Response

ParamType = \
        int | str | Enum | None \
        | collections.abc.Set['ParamType'] \
        | collections.abc.Sequence['ParamType']
# Mapping is covariant in the value type, allowing for subclasses of Enum as values.
# dict is invariant in the value type, so we need to use Mapping instead.
ParamsDict = collections.abc.Mapping[str, ParamType]

JsonScalar = int | float | bool | str | None
JsonType = JsonScalar | collections.abc.Sequence['JsonType'] | collections.abc.Mapping[str, 'JsonType']
JsonMap = dict[str, JsonType]

TomlType = \
        JsonScalar \
        | datetime.datetime | datetime.date | datetime.time \
        | collections.abc.Sequence['TomlType'] \
        | collections.abc.Mapping[str, 'TomlType']
TomlMap = collections.abc.Mapping[str, TomlType]

class ApiError(Exception):
    status: int
    reason: str|None
    response: Response|None

    def __init__(self, status: int, reason: str|None, response: Response|None):
        super().__init__()
        self.status = status
        self.reason = reason
        self.response = response

    @classmethod
    async def from_resposnse(cls, response: Response) -> 'ApiError':
        reason = None
        try:
            reason = await response.text()
        except Exception: pass
        raise cls(response.status, reason, response)

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

async def serve_once(host: str, port: int, html_file: str) -> dict[str, str]:
    import aiohttp.web
    import os

    query: dict[str, str] = {}
    did_serve_once = asyncio.Semaphore(0)

    server = aiohttp.web.Application()

    html = open(os.path.join(os.path.dirname(__file__), html_file), 'r').read()

    async def index_handler(request: aiohttp.web.Request):
        if not did_serve_once.locked(): # did_serve_once has already been released
            return aiohttp.web.Response(text="Already handled", status=500)
        for key, value in request.query.items():
            query[key] = value
        did_serve_once.release()
        return aiohttp.web.Response(text=html, content_type='text/html')
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

    await asyncio.sleep(1) # wait for server to close?

    return query