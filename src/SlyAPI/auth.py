from abc import ABC
from typing import Any


class Auth(ABC):

    def from_file(self, path: str): raise NotImplemented

    def to_dict(self) -> dict[str, Any]: raise NotImplemented

    def get_headers(self) -> dict[str, str]: raise NotImplemented

    async def refresh(self, *args, **kwargs): raise NotImplemented

    def get_common_params(self) -> dict[str, Any]: raise NotImplemented

    def get_common_headers(self) -> dict[str, Any]: raise NotImplemented
