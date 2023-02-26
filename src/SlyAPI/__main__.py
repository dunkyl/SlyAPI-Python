from dataclasses import asdict
import sys, json, asyncio

from .oauth1 import OAuth1App, command_line_oauth1
from .oauth2 import OAuth2App, command_line_oauth2

args = sys.argv[1:]

match args:
    case ['oauth1-flow', app_file, out_file]:
        app = OAuth1App.from_json_file(app_file)
        user = asyncio.run(
            command_line_oauth1(app, 'localhost', 8080, True))
        
        with open(out_file, 'w') as f:
            json.dump(asdict(user), f, indent=4)

    case ['oauth2-flow', app_file, out_file, *scopes]:
        app = OAuth2App.from_json_file(app_file)
        user = asyncio.run(
            command_line_oauth2(app, 'localhost', 8080, False, scopes))
        
        with open(out_file, 'w') as f:
            json.dump(user.to_dict(), f, indent=4)

    case ['scaffold', 'oauth1', app_file]:
        with open(app_file, 'w') as f:
            json.dump({
                'key': '',
                'secret': '',
                'request_uri': '',
                'authorize_uri': '',
                'access_uri': ''
            }, f, indent=4)
    case ['scaffold', 'oauth2', app_file]:
        with open(app_file, 'w') as f:
            json.dump({
                'id': '',
                'secret': '',
                'token_uri': '',
                'auth_uri': ''
            }, f, indent=4)
    case _:
        print("Usage:")
        print("  SlyAPI <command> [<args>]")
        print("")
        print("Commands:")
        print("  oauth1-flow APP_FILE USER_FILE: grant a single OAuth1 user token with the local flow.")
        print("")
        print("  oauth2-flow APP_FILE USER_FILE [SCOPES...]: grant a single OAuth2 user token with the local flow.")
        print("")
        print("  scaffold KIND APP_FILE: create an example application json file for filling in manually.")
        print("                  KIND is one of 'oauth1' or 'oauth2'.")
        print("")
        print("  help: this dialog.")