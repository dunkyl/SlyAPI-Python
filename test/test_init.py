import warnings
from SlyAPI import *

class _TestAPI(WebAPI):

    attr_initialized_after_await = None

    async def __init__(self):
        await super().__init__()
        self.attr_initialized_after_await = 1

async def test_error_uninitialized():

    api_unawaited = _TestAPI()

    error = None

    try:
        print( api_unawaited.attr_initialized_after_await )
    except RuntimeError as e:
        error = e

    assert error is not None

    api_awaited = await api_unawaited

    print( api_awaited.attr_initialized_after_await )

async def test_warn_not_awaited():
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")

        _TestAPI()
        # gc'd before awaited

        assert len(w) == 1
        assert issubclass(w[-1].category, RuntimeWarning)
        assert "AsyncInit" in str(w[-1].message)