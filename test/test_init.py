from SlyAPI import *

class TestAPI(WebAPI):

    def __init__(self):
        super().__init__()
        self.attr_initialized_after_await = None

    async def _async_init(self):
        await super()._async_init()
        self.attr_initialized_after_await = 1

async def test_error_uninitialized():

    api_unawaited = TestAPI()

    error = None

    try:
        print( api_unawaited.attr_initialized_after_await )
    except RuntimeError as e:
        error = e

    assert error is not None

    api_awaited = await api_unawaited

    print( api_awaited.attr_initialized_after_await )