from abc import ABC
from typing import Any
import json


class Auth(ABC):

    @classmethod
    def from_file(cls, path: str) -> 'Auth': raise NotImplemented

    def to_dict(self) -> dict[str, Any]: raise NotImplemented

    async def refresh(self, *args: Any, **kwargs: Any): raise NotImplemented

    def get_common_params(self) -> dict[str, Any]: raise NotImplemented

    def get_common_headers(self) -> dict[str, Any]: raise NotImplemented


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

    def to_dict(self) -> dict[str, Any]:
        return self.params

    async def refresh(self, *args: Any, **kwargs: Any): raise NotImplemented

    def get_common_params(self) -> dict[str, Any]:
        return self.params

    def get_common_headers(self) -> dict[str, Any]:
        return {}
