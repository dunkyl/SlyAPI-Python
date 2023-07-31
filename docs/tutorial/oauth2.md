# Getting OAuth2 Credentials

As a first step, it may be good to add the two JSON files made later to your `.gitignore`, since they will need to be kept secret. Alternatively, you can keep them outside of version control. Of course, they should be named more appropriately:

```ini
# ./.gitignore
my_app_credentials.json
my_user_credentials.json
# ...
```

To aquire client/app credentials, please visit the 3rd party service you are implementing.

Links to some places to get OAuth2 credentials:
- [Google Cloud Console](https://console.cloud.google.com)
- [Discord Developers](https://discord.com/developers)

After you have the credentials, save them in a protected JSON file.

```{admonition} Google provides client JSON files.
:class: info
If you are using Google APIs, you can just download the client credentials file directly and use it. You can skip any scaffolding.
```

You can create a template for it with SlyAPI from the command line:

```sh
py -m SlyAPI scaffold
```

The format of the JSON file is as follows:

```json
{
    "id": "...",
    "secret": "...",
    "auth_uri": "...",
    "token_uri": "..."
}
```

Note that you may have to search the documentation of the 3rd party for the relevate URI's.
A specific Sly library may already fill these URI fields already.

## One-time grant

For development or personal purposes, you can authorized just one user. Once the app file is set up, you can use SlyAPI to grant credentials:

```sh
py -m SlyAPI grant
```

You will need to specify the app credentials mentioned earlier. A web browser window will be opened to bring you to the OAuth conset page if possible. Assuming it succeeds, it will write a new or overwrite a JSON file with the user credentials in the correct format.

Now, to use these credentials, the easiest way is to pass both of the file paths to the `OAuth2` contructor.

```py
from SlyAPI import *

my_auth = OAuth2("my_app_credentials.json", "my_user_credentials.json")
```
`WebAPI` implementations which use OAuth2 should take an instance of `OAuth2` in their constructor.

## Many grants for many users

If you are giving strangers the ability to generate credentials with your app, it is probably unreasonable to manually grant each on the command line. Additionally, client credentials should not be distributed with apps.

Instead, you can use methods on `OAuth2App` to integrate an authorization flow with your website or app.

Generate a URL to redirect the user to with [`OAuth2App.auth_url_with_pkce`](SlyAPI.oauth2.OAuth2App.auth_url_with_pkce), and after recieving and parsing the redirect after the consent page on the 3rd party website, use [`OAuth2App.exchange_code`](SlyAPI.oauth2.OAuth2App.exchange_code) to get a `OAuth2User` object.

It may be appropriate to **set up a callback for refreshed tokens** in the constructor for `OAuth2App` in this case, so that credentials do not need to be refreshed every time!