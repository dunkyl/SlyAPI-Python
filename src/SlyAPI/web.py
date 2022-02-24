import asyncio
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, cast

import aiohttp
import aiohttp.web

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
    query_params: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, Any] = field(default_factory=dict)
    data: dict[str, Any] = field(default_factory=dict)
    data_is_json: bool = False

    def send(self, session: aiohttp.ClientSession):
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
        return session.request(self.method.value, self.url, json=json, data=data, params=params, headers=headers)

async def serve_one_request(host: str, port: int, response_body: str) -> dict[str, str]:

    query: dict[str, str] = {}
    handled_req = False

    server = aiohttp.web.Application()

    async def index_handler(request: aiohttp.web.Request):
        nonlocal query, handled_req
        query = cast(dict[str, str], request.query)
        handled_req = True
        return aiohttp.web.Response(text=response_body, content_type='text/html')
    server.router.add_get("/", index_handler)

    run_task_ = aiohttp.web._run_app(server, host=host, port=port) # type: ignore ## reportPrivateUsage
    run_task = asyncio.create_task(run_task_)

    while not handled_req:
        await asyncio.sleep(0.1)
    run_task.cancel()
    try:
        await run_task
    except asyncio.exceptions.CancelledError:
        pass

    return query