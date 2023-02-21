from abc import ABC, abstractmethod

from aiohttp import ClientSession as Client

from .web import Request

class Auth(ABC):
    'Implement for any authentication scheme.'
    @abstractmethod
    async def sign(self, client: Client, request: Request) -> Request: pass

    @staticmethod
    def none() -> 'NoAuth': return NoAuth()


class UrlApiKey(Auth):
    'URL parameter with a secret to authorize requests.'
    params: dict[str, str]

    def __init__(self, param_name: str, secret: str):
        self.params = {param_name: secret}

    async def sign(self, _, request: Request) -> Request:
        request.query_params |= self.params
        return request

class HeaderApiKey(Auth):
    'Header with a secret to authorize requests.'
    headers: dict[str, str]

    def __init__(self, param_name: str, secret: str):
        self.headers = {param_name: secret}

    async def sign(self, _, request: Request) -> Request:
        request.headers |= self.headers
        return request

class NoAuth(Auth):
    'Does nothing.'

    async def sign(self, _, request: Request) -> Request: return request



