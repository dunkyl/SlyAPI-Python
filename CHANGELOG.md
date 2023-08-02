# Change Log

## [Unreleased]

### Changes
- `AsyncLazy.map` returns `AsyncLazy` so that it can be mapped more than once.
- `AsyncTrans` is now just a type alias for `AsyncLazy`

---

## [0.5.0] - 2023-07-30

### Changes/Improvements
- `WebAPI` no longer needs to be constructed after an event loop is running.
- `unmanage_async_context_sync` renamed to `unmanage_async_context`
    - unused async version removed
    - returns a `asyncio.Event` instead of `asyncio.Semaphore` for releasing context
    - returns a `asyncio.Task[T]` instead of `T` and does not assume `__aenter__` returns self

### Removed
- unused `run_sync_ensured`

## [0.4.5] - 2023-03-03

### Added

- `WebAPI._get_, _post, _put, _patch, _delete` methods with serialization and deserialization
    - Return type can have `from_json` classmethod for deserialization. None for no deserialization, str for text content, or a single-parameter constructor which will get the JSON response object.
    - Data parameter can have `to_json` method for serialization, asdict for dataclasses, or passed as-is.
    - `TypedDict` is one good way to define the JSON response type, and will work without any extra code.
- `WebAPI._use_form_data` is used for the above methods.

## [0.4.4] - 2023-03-02

### Added
- `delete_json` (for HTTP DELETE) method

## [0.4.3] - 2023-02-26

### Changed
- `OAuth2App` and `OAuth2User` no longer overload the dataclass constructor
    - use `.from_json_obj()` or `.from_json_file()` instead
- `WebAPI` is no longer `AsyncInit`, and should not be awaited
- `APIKey` renamed to `UrlApiKey`, `APIError` to `ApiError`
- `Auth.sign_request` renamed to `Auth.sign`
- `WebAPI` now requires an `Auth` object, not None
    - use `Auth.none()` for no auth
- `OAuth2User` no longer keeps a `source_path` and does not do any IO

### Added
- Interactive wizard for granting credentials
- Google flavor app/client JSON files can now be used to create `OAuth2`
- Success local flow page styling, light/dark
- `HeaderApiKey` for adding API keys to the `Authorization` header, or any other header
- `WebAPI._parameter_list_delimiter` for serialization. Only applies to URL parameters.
- `NoAuth` implementation of `Auth`
- `OAuth2` accepts a callback for when user tokens are refreshed.
- separate `METHOD_form()` methods for form-parameter requests

### Removed
- `EnumParam`, `EnumParams` types. Instead, use `set[str]` or `set[T]` where `T` is an enum type.
    - Make sure to convert any sets or lists to strings with the appropriate delimter for whichever API you are using.
    - Alternatively, set `WebAPI._parameter_list_delimiter` to the appropriate delimiter for your API.
- `APIObj` did not provide much value as a base class, and could make usage less clear.
- `Auth.refresh` and `Auth.flow`, which could not be implemented by many authorization schemes.
- `AsyncInit` base class, which was no longer needed.

## [0.2.4] - 2022-02-26

### Added
- `OAuth1` and `OAuth1User` constructors accept a string as a path to a JSON file.