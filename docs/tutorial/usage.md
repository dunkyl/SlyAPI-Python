# Usage

## Installation

SlyAPI is available though pip:

```sh
pip install slyapi
```

## Implementation

SlyAPI should be used either in it's own file, module, or package to implement one set of web APIs.
If there are multiple sets of endpoints, each base URL and version should have its own class. If possible, expose a public interface of only one.

`from SlyAPI import *` brings the classes and functions described below into scope.

### `WebAPI`

The most important class to derive from and provides most of the nessecary core functionality.
Derive from this class for your web API class.

### `OAuth2`, `OAuth2App`, and `OAuth2User`

Since OAuth is such a common authentication method, implementations are provided for using it.
WebAPI's that use OAuth should take only an `OAuth2` instance as a constructor for authorization.
This allows users of the library to choose their own method of retrieving the credentials.

`OAuth1`, `OAuth1App`, and `OAuth1User` are also provided but not recommended in most cases.

### `UrlApiKey` and `HeaderApiKey`

Two more simple and common authentication methods. Like the above `OAuth2`, these implement the `Auth` interface.

An instance of `Auth` must be passed to the base constructor. In most cases that is all that is needed to handle authorization as a library.

```py
def __init__(self, auth: OAuth2, other_thing: int):
    super().__init__(auth)
    # ...
```

### `@requires_scopes()`

Decorator for functions to mark them as requring specific OAuth2 scopes to be called.

### `AsyncLazy` and `AsyncTrans`

Returned from `WebAPI.paginated()`, these niche utility types provide an easy way to expose either async generators OR eager lists. `AsyncTrans.map()` returns an `AsyncTrans` which also applies a function lazily to each result.

```py
lazy = AsyncLazy( _your_async_generator_ )
async for item in lazy:
    print(item)
# or
list_of_items = await lazy
```

---

### Your web API class

Each public member of the class should correspond to a single logical action.

The constructor should take, at least, a derived class of [`Auth`](SlyAPI.auth.Auth).

Public members should return built-in collections (`list`, `set`, etc.), [`AsyncLazy`](SlyAPI.asyncy.AsyncLazy), or [`AsyncTrans`](SlyAPI.asyncy.AsyncTrans), or domain-specific classes defined in your libarary. It should not return `JsonMap` or `Response`, which should be handled in private methods.

---

For a development installation, see [the contribution guide](../contributing.md).