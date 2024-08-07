# Getting Started

SlyAPI is created as a foundation for building manual API clients, usually RESTish ones. If you intend on using any of the following API's specifically, consider depending on these libraries instead:

* [SlyYTDAPI](https://github.com/dunkyl/SlyYTDAPI-Python) and [SlyYTAAPI](https://github.com/dunkyl/SlyYTAAPI-Python): for the YouTube APIs
* [SlyTwitter](https://github.com/dunkyl/SlyTwitter-Python)
* [SlySheets](https://github.com/dunkyl/SlySheets-Python): for Google Sheets
* [SlyGmail](https://github.com/dunkyl/SlyGmail-Python)

If you want to create your own library or module for accessing some other API, you are in the right place.

## Getting credentials for your project

A good place to start is to get some test credentials for the service you're wrapping. SlyAPI comes with some common authentication methods out of the box. They are as follows:

### An API Key

The [Auth module](SlyAPI.auth.Auth) contains a base class that all authentication methods conform to. The simplest is [UrlApiKey](SlyAPI.auth.UrlApiKey) which is intended for passing one simple string with each request to the API. Your implementation just specifies a url parameter that is filled.

```py
# ... somewhere in YourAPIClass

auth = UrlApiKey("key_param_name", secret_key_value)

# ...
```

```{admonition} Keep your secrets secret
:class: warning

The `secret_key_value` should be loaded from some secrets file, perhaps JSON or plaintext, which is **omitted from your git repository**.
A common alternative is to store this secret in an environment variable and loading it from there.
Do not paste it into your source code if you use any kind of version control or intend on sharing your code, built or not.
```

### With a Google "Service Account"

If you are using a Google API to perform some automated task, you should use this. Most of the Google Cloud services support both this, and an OAuth2 grant on behalf of a normal Google account. This method can be much simpler.

There are two ways to use a Service Account. The Google-recommended method, by using "workload federation", only works when you are running your code in a handful of specific managed cloud environments, such as AWS or Azure. This library offers no support for this yet. 

To acquire a basic key for your Service Account, create a Google Cloud Project. Under "IAM & Admin", you can find a Service Accounts section. You may need to grant it permission to use a particular service scope. You can download a JSON key for the account after it is created. Pass the path for this key to the `OAuth2ServiceAccount` constructor along with the scopes for whatever service you are using.

For example, to use a service account with Google Sheets:

```py
import SlyAPI, SlySheets
# ...
auth = SlyAPI.OAuth2ServiceAccount(
            "service_account.json",
            ["https://www.googleapis.com/auth/spreadsheets"])
sheet = await SlySheets.Spreadsheet(auth, MY_SHEET_ID)
# ...
```

Like with API keys, the JSON credentials contain secrets that should never be shared.

### With OAuth 1 or 2

There are two items required to sign requests with OAuth1. Client credentials, or app credentials, are provided by the 3rd party service/website to developers. Usually there is additional set up for getting approved or agreeing to terms of use. In some cases, you may need to submit a live URL with a privacy policy detailing how you will use the credentials.

The other kind of credential is for a specific user account, and can be generated by SlyAPI.

OAuth2 specifics: [Getting OAuth2 Credentials →](oauth1.md)

OAuth1 specifics: [Getting OAuth2 Credentials →](oauth2.md)

### Something else

If your service uses some other kind of authentication, subclass [Auth](SlyAPI.auth.Auth) with your own type.

It only needs to implement on async method, `sign`, which transforms a [Request](SlyAPI.web.Request).

Example:

```py
class OtherAuth(Auth):
    # ...

    async def sign(request):
        key, secret = await self.complex_negotiaions()
        request.query_params |= { key+'5': str(rev(secret))}
        return request
```