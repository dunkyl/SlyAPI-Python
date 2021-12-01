from typing import Callable
from .asyncy import *
from .webapi import *
import functools

Endpoint = Callable[[WebAPI, T], Coroutine[Any, None, U]]

def ratelimit(bucket: str, bucket_params: list[str]) -> Callable[[Endpoint[Any, T]], Endpoint[Any, T]]:
    def decorator(func: Endpoint[Any, T]) -> Endpoint[Any, T]:
        @functools.wraps(func)
        async def wrapper(self: WebAPI, params: dict[str, Any]) -> T:
            # TODO
            return await func(self, params)
        return wrapper
    return decorator