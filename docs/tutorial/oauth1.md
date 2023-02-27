# Getting OAuth1 Credentials

```{admonition} OAuth1 is superceded.
:class: info
Most modern services *do not* require the use of OAuth1, and it is not recommended. If possible use OAuth2 instead.
```

As a first step, it may be good to add the two JSON files made later to your `.gitignore`, since they will need to be kept secret. Alternatively, you can keep them outside of version control. Of course, they should be named more appropriately:

```conf
   # ./.gitignore
   my_app_credentials.json
   my_user_credentials.json
   # ...
```

To aquire app credentials, please visit the 3rd party service you are implementing.

For Twitter, follow instructions on [Twitter Developers](https://dev.twitter.com) to create a developer account, and to create a project with credentials. Note that you can create different kinds of credentials for different sets of endpoints. Twitter V1.1 uses OAuth1, but V2 does not!

After you have the credentials, save them in a protected JSON file.

You can create a template for it with SlyAPI from the command line:

```sh
py -m SlyAPI scaffold
```

The format of the JSON file is as follows:

```json
{
    "key": "...",
    "secret": "...",
    "request_uri": "...",
    "authorize_uri": "...",
    "access_uri": "..."
}
```

Note that you may have to search the documentation of the 3rd party for the relevate URI's.
A specific Sly library may already fill these URI fields already, though:

```sh
py -m SlyTwitter v1 scaffold
```

## One-time grant

For development or personal purposes, you can authorized just one user. Once the app file is set up, you can use SlyAPI to grant credentials:

```sh
py -m SlyAPI grant
```

You will need to specify the app credentials mentioned earlier. A web browser window will be opened to bring you to the OAuth conset page if possible. Assuming it succeeds, it will write a new or overwrite a JSON file with the user credentials in the correct format.

Now, to use these credentials, the easiest way is to pass both of the file paths to the `OAuth1` contructor.

```py
from SlyAPI import *

my_auth = OAuth1("my_app_credentials.json", "my_user_credentials.json")
```
`WebAPI` implementations which use OAuth1 should take an instance of `OAuth1` in their constructor.

## Many grants for many users

If you are giving strangers the ability to generate credentials with your app, it is probably unreasonable to manually grant each on the command line.

# TODO: programatic grants

At this time SlyAPI does not implement other ways to authorize users with OAuth1.