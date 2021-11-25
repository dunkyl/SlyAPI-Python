import sys, json, asyncio

from .webapi import *
from .oauth2 import OAuth2Client, localhost_flow

args = sys.argv[1:]

if args[0] == "--help" or len(args) == 0:
    print("Usage:")
    print("  SlyAPI <command> [<args>]")
    print("")
    print("Commands:")
    print("  flow <client_file> [<scopes>]: grant a single oauth2 user token with the local flow.")
    print("  --help: this dialog.")
    sys.exit(0)

async def flow(client: OAuth2Client, scopes: str):
    user = await localhost_flow(client, scopes)
    print(json.dumps(user.to_dict(), indent=2))

if args[0] == "flow":
    if len(args) < 3:
        print("Usage:")
        print("  SlyAPI flow <client_file> [<scopes>]")
        sys.exit(1)
    client_file = args[1]
    scopes = ' '.join(args[2:])
    asyncio.run(flow(OAuth2Client.from_file(client_file), scopes))
else:
    print("Unknown command:", args[0])
    print("Use --help for help.")
    sys.exit(1)
