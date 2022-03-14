from abc import ABC, abstractmethod
from typing import Any, TypeVar
import json

import aiohttp

from .web import Request

TSelf = TypeVar('TSelf')

class Auth(ABC):

    @abstractmethod
    async def refresh(self, session: aiohttp.ClientSession): pass

    @abstractmethod
    async def sign_request(self, session: aiohttp.ClientSession, request: Request) -> Request: pass

    @abstractmethod
    async def user_auth_flow(self, redirect_host: str, redirect_port: int, **kwargs: str): pass


class APIKey(Auth):
    params: dict[str, str]

    def __init__(self, param_name: str, secret: str):
        self.params = {param_name: secret}

    @classmethod
    def from_file(cls, path: str):
        with open(path) as f:
            data = json.load(f)
        if len(data.keys()) != 1:
            raise ValueError('Unknown API Key format. Should be JSON: {ParamName: Key}')
        return cls(*data.items().pop())

    async def refresh(self, *args: Any, **kwargs: Any): raise NotImplemented()

    async def sign_request(self, session: aiohttp.ClientSession, request: Request) -> Request:
        request.query_params |= self.params
        return request

    async def user_auth_flow(self, *args: Any, **kwargs: Any): raise NotImplemented()

    # @classmethod
    # async def flow(cls: type[TSelf], **kwargs: str) -> TSelf:
        
    #     print('Please retrieve an API key from the service provider.')
    #     input("Press Enter to continue...")
        
    #     destination_file = kwargs.get('destination')
    #     if destination_file is None:
    #         destination_file = input('Enter destination file path: ')

    #     api_key_param = kwargs.get('param_name')
    #     if api_key_param is None:
    #         api_key_param = input('Enter query parameter name: ')

    #     api_key_secret = kwargs.get('secret')
    #     if api_key_secret is None:
    #         api_key_secret = input('Enter API key secret: ')

    #     obj = cls(api_key_param, api_key_secret)

    #     with open(destination_file, 'w') as f:
    #         json.dump(obj.to_dict(), f)

    #     print(f'API key saved to {destination_file}')

    #     return obj


