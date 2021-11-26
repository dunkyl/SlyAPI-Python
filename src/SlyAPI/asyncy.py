def end_loop_workaround():
    # workaround for:
    # https://github.com/aio-libs/aiohttp/issues/4324#issuecomment-733884349

    # Replace the event loop destructor thing with one a wrapper which ignores
    # this specific exception on windows.
    import sys
    if sys.platform.startswith("win"):
        from asyncio.proactor_events import _ProactorBasePipeTransport # type: ignore

        base_del = _ProactorBasePipeTransport.__del__
        if not hasattr(base_del, '_once'):
            def quiet_delete(*args, **kwargs): # type: ignore
                try:
                    return base_del(*args, **kwargs) # type: ignore
                except RuntimeError as e:
                    if str(e) != 'Event loop is closed':
                        raise
            quiet_delete._once = True # type: ignore

            _ProactorBasePipeTransport.__del__ = quiet_delete