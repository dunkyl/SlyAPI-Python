from dataclasses import asdict
import sys, json, asyncio

from .webapi import *
from .oauth1 import OAuth1
from .oauth2 import OAuth2

args = sys.argv[1:]

match args:
    case ['oauth1-flow', app_file, out_file]:
        app = OAuth1(json.load(open(app_file, 'rb')))
        asyncio.run(
            app.user_auth_flow('127.0.0.1', 8080, True))
        with open(out_file, 'w') as f:
            json.dump(asdict(app.user), f, indent=4)
    case ['oauth2-flow', app_file, out_file, *scopes]:
        app = OAuth2(json.load(open(app_file, 'rb')))
        scopes = ' '.join(scopes)
        asyncio.run(
            app.user_auth_flow('localhost', 8080, scopes=scopes))
        assert(app.user is not None)
        with open(out_file, 'w') as f:
            json.dump(app.user.to_dict(), f, indent=4)
    case ['scaffold', kind, app_file]:
        if kind == 'oauth1':
            example = {
                'key': '',
                'secret': '',
                'request_uri': '',
                'authorize_uri': '',
                'access_uri': ''
            }
        elif kind == 'oauth2':
            example = {
                'id': '',
                'secret': '',
                'token_uri': '',
                'auth_uri': ''
            }
        else:
            raise ValueError(f"Unknown kind: {kind}")
        with open(app_file, 'w') as f:
            json.dump(example, f, indent=4)
    case _:
        print("Usage:")
        print("  SlyAPI <command> [<args>]")
        print("")
        print("Commands:")
        print("  oauth1-flow APP_FILE USER_FILE [--host HOST] [--port PORT]: grant a single OAuth1 user token with the local flow.")
        print("")
        print("  oauth2-flow APP_FILE USER_FILE SCOPES... [--host HOST] [--port PORT] : grant a single OAuth2 user token with the local flow.")
        print("")
        print("  scaffold KIND APP_FILE: create an example application json file for filling in manually.")
        print("                  KIND is one of 'oauth1' or 'oauth2'.")
        print("")
        print("  help: this dialog.")