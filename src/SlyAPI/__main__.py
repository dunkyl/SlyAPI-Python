from dataclasses import asdict
import sys, json, asyncio

from .webapi import *
from .oauth1 import OAuth1
from .oauth2 import OAuth2
from .asyncy import end_loop_workaround

end_loop_workaround()

args = sys.argv[1:]

match args:
    case ['oauth1-flow', app_file, user_file, *scopes]:
        app = OAuth1(**json.load(open(app_file, 'r')))
        scopes = ' '.join(scopes)
        asyncio.run(
            app.user_auth_flow('127.0.0.1', 8080, scopes=scopes))
        with open(user_file, 'w') as f:
            json.dump(asdict(app.user), f, indent=4)
    case ['oauth2-flow', app_file, user_file, *scopes]:
        app = OAuth2(**json.load(open(app_file, 'r')))
        scopes = ' '.join(scopes)
        asyncio.run(
            app.user_auth_flow('localhost', 8080, scopes=scopes))
        with open(user_file, 'w') as f:
            json.dump(asdict(app.user), f, indent=4)
    case _:
        print("Usage:")
        print("  SlyAPI <command> [<args>]")
        print("")
        print("Commands:")
        print("  oauth1-flow APP_FILE USER_FILE [--host HOST] [--port PORT]: grant a single OAuth1 user token with the local flow.")
        print("")
        print("  oauth2-flow APP_FILE USER_FILE SCOPES... [--host HOST] [--port PORT] : grant a single OAuth2 user token with the local flow.")
        print("")
        print("  help: this dialog.")