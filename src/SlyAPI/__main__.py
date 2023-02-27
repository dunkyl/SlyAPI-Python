import sys, asyncio, inspect

from .flow import *

async def main(args: list[str]):

    match args:
        # wizards
        case ['scaffold']: scaffold_wizard()
        case ['grant']: await grant_wizard(None)

        # explicit commands
        case ['scaffold', 'oauth1', file]: scaffold_oauth1(file)
        case ['scaffold', 'oauth2', file]: scaffold_oauth2(file)

        case ['grant', 'oauth1', app, user] \
           | ['oauth1-flow', app, user]:
            
            await grant_oauth1(app, user)
        
        case ['grant', 'oauth2', app, user, *scopes] \
           | ['oauth2-flow', app, user, *scopes]:
            
            await grant_oauth2(app, user, scopes)
        
        case _: # help
            print(inspect.cleandoc("""
            SlyAPI command line: tool for generic OAuth1/2.
            Usage:
                SlyAPI scaffold
                    Wizard to set up an example client/app JSON.

                SlyAPI grant
                    Wizard to grant a single OAuth1/2 user token.

                --- Explicit ---
                SlyAPI scaffold <oauth1|oauth2> <APP JSON>
                    Set up an example JSON for your client/app.

                SlyAPI grant <oauth1|oauth2> <APP JSON> <USER JSON> [scopes...]
                    Grant a single OAuth1/2 user token with the local flow.
                    Scopes only apply to OAuth2.
                    Scopes are space-separated, and may be required!
            """))

if __name__ == '__main__':
    asyncio.run(main(sys.argv[1:]))
    