from dataclasses import asdict
import sys, json, asyncio

from .oauth1 import OAuth1App, command_line_oauth1
from .oauth2 import OAuth2App, command_line_oauth2

args = sys.argv[1:]

match args:
    case ['grant', 'oauth1', app_file, out_file] \
       | ['oauth1-flow', app_file, out_file]:
        app = OAuth1App.from_json_file(app_file)
        user = asyncio.run(
            command_line_oauth1(app, 'localhost', 8080, False))
        
        with open(out_file, 'w') as f:
            json.dump(asdict(user), f, indent=4)

    case ['grant', 'oauth2', app_file, out_file, *scopes] \
       | ['oauth2-flow', app_file, out_file, *scopes]:
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
        print("""
        Usage:
            SlyAPI scaffold <oauth1|oauth2> <APP JSON>
                Set up an example JSON file for your client/app.
            ---
            SlyAPI grant <oauth1|oauth2> <APP JSON> <USER JSON> [scopes...]
                Grant a single OAuth1/2 user token with the local flow.
                Scopes only apply to OAuth2.
                Scopes are space-separated, and may be required!
                A web browser may be opened to complete the flow.
                <USER JSON> will be overwritten with the new token.
                oauth1-flow and auth2-flow are aliases for this.
        """)