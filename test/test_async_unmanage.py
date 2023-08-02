import asyncio
from SlyAPI.asyncy import unmanage_async_context

async def test_unmanage_async_context():

    class FiveManager:
        was_entered = False
        was_exited = False

        async def __aenter__(self):
            self.was_entered = True
            return 5

        async def __aexit__(self, *_):
            self.was_exited = True

    five_factory_managed = FiveManager()

    async with five_factory_managed as five:
        assert five == 5
        assert five_factory_managed.was_entered
    assert five_factory_managed.was_exited

    five_factory_unmanaged = FiveManager()
    five_once_entered, close_ctx = unmanage_async_context(five_factory_unmanaged)

    five = await five_once_entered # yield to background context to run __aenter__

    assert five == 5
    assert five_factory_unmanaged.was_entered
    assert not five_factory_unmanaged.was_exited

    close_ctx.set()

    await asyncio.sleep(0) # yield to background context to run __aexit__

    assert five_factory_unmanaged.was_exited