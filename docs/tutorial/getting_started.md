# Getting Started

SlyAPI is created as a foundation for building manual API clients, usually RESTful ones. If you intend on using any of the following API's specifically, consider depending on these libraries instead:

* [SlyYTDAPI](https://github.com/dunkyl/SlyPyYTDAPI) and [SlyYTAAPI](https://github.com/dunkyl/SlyPyYTAAPI): for the YouTube APIs
* [SlyTwitter](https://github.com/dunkyl/SlyPyTwitter)
* [SlySheets](https://github.com/dunkyl/SlyPySheets): for Google Sheets
* [SlyGmail](https://github.com/dunkyl/SlyPyGmail)

If you want to create your own library or module for accessing some other API, you are in the right place.

## Getting credentials for your project

A good place to start is to get some test credentials for the service you're wrapping. SlyAPI comes with some common authentication methods out of the box. They are as follows:

### An API Key

The [Auth module](SlyAPI.auth) contains a base class that all authentication methods conform to. The simplest is [APIKey](SlyAPI.auth.APIKey) which is intended for passing one simple string with each request to the API. Your implementation just specifies a url parameter that is filled.

```py
# ... somewhere in YourAPIClass

auth = APIKey("key_param_name", secret_key_value)

# ...
```

```{admonition} Keep your secrets secret
:class: warning

The `secret_key_value` should be loaded from some secrets file, perhaps JSON or plaintext, which is **omitted from your git repository**.
A common alternative is to store this secret in an environment variable and loading it from there.
Do not paste it into your source code if you use any kind of version control or intend on sharing your code, built or not.
```

### With OAuth 2

TODO: this

### With OAuth 1

TODO: this

### Something else

If your service uses some other kind of authentication, subclass [Auth](SlyAPI.auth.Auth) with your own type.


TODO: this