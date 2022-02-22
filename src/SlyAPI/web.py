from dataclasses import dataclass
from enum import Enum
from typing import Any

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
    query_params: dict[str, Any] | None = None
    headers: dict[str, Any]  | None = None
    data: dict[str, Any] | None = None
