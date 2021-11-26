import asyncio, json
from datetime import datetime, timedelta
from dataclasses import dataclass
import secrets
from typing import Any, cast
from .asyncy import end_loop_workaround

import aiohttp, aiohttp.web
# import http.server
import webbrowser

import urllib.parse

from aiohttp.web_runner import GracefulExit

@dataclass
class OAuth2Client:
    id: str
    secret: str
    token_uri: str
    auth_uri: str

    def get_auth_url(self, redirect_uri: str, state: str, scopes: str) -> tuple[str, str]:
        challenge = secrets.token_urlsafe(54)
        params = {
            'client_id': self.id,
            'redirect_uri': redirect_uri,
            'response_type': 'code',
            'state': state+challenge,
            'scope': scopes,
            'access_type': 'offline'
            }
        return F"{self.auth_uri}?{urllib.parse.urlencode(params)}", challenge

    async def grant(self, redirect_uri: str, code: str, scopes: str) -> 'OAuth2User':
        data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.id,
            'client_secret': self.secret,
            'redirect_uri': redirect_uri,
            'scope': scopes
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        print(data)
        print(headers)

        async with aiohttp.ClientSession() as session:
            async with session.post(self.token_uri, data=data, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f'Grant failed: {resp.status}')
                result = await resp.json()
                print(result)
                return OAuth2User(result)

    @staticmethod
    def from_file(filename: str) -> 'OAuth2Client':
        with open(filename, 'r') as f:
            data = json.load(f)
        match data:
            case {'web': {
                    'client_id': id,
                    'client_secret': secret, 'token_uri': token_uri,
                    'auth_uri': auth_uri }}: # google flavour
                return OAuth2Client(id, secret, token_uri, auth_uri)
            case _:
                raise ValueError(f"Unknown client format in: {filename}")
          

class OAuth2User:
    token: str
    refresh_token: str
    expires_at: datetime
    token_type: str = 'Bearer'

    def __init__(self, token_response: dict[str, Any]):
        self.token = token_response['access_token']
        self.refresh_token = token_response['refresh_token']
        self.expires_at = datetime.now() + timedelta(seconds=token_response['expires_in'])
        self.token_type = token_response['token_type']

    def get_headers(self) -> dict[str, str]:
        return {
            'Authorization': f'{self.token_type} {self.token}',
        }

    async def refresh(self, client: OAuth2Client):
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.refresh_token,
            'client_id': client.id,
            'client_secret': client.secret,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        async with aiohttp.ClientSession() as session:
            async with session.post(client.token_uri, data=data, headers=headers) as resp:
                if resp.status != 200:
                    raise Exception(f'Refresh failed: {resp.status}')
                result = await resp.json()
                return OAuth2User(result)

    def to_dict(self) -> dict[str, Any]:
        return {
            'token': self.token,
            'refresh_token': self.refresh_token,
            'expires_at': self.expires_at.isoformat(),
            'token_type': self.token_type
        }

async def localhost_flow(client: OAuth2Client, scopes: str) -> OAuth2User:
    '''
    Set up an http server and open a browser to make one grant.
    '''

    end_loop_workaround()

    redirect_host = 'localhost'
    redirect_port = 8080
    redirect_uri = F'http://{redirect_host}:{redirect_port}'

    # step 1: get the user to authorize the application
    grant_link, challenge = client.get_auth_url(redirect_uri, '', scopes)

    webbrowser.open(grant_link, new=1, autoraise=True)

    # step 1 (cont.): wait for the user to be redirected with the code
    query: dict[str, str] = {}
    handled_req = False

    server = aiohttp.web.Application()

    # async def close_after():
    #     await asyncio.sleep(0.5)
    #     print('shutdown')
    #     await server.shutdown()
    #     await server.cleanup()
    #     print('shutdown2')

    async def index_handler(request: aiohttp.web.Request):
        nonlocal query, handled_req
        query = cast(dict[str, str], request.query)
        handled_req = True
        # asyncio.create_task(close_after())
        return aiohttp.web.Response(text='<html><body>You can close this window now.</body></html>', content_type='text/html')
    server.router.add_get("/", index_handler)

    run_task_ = aiohttp.web._run_app(server, host=redirect_host, port=redirect_port) # type: ignore ## reportPrivateUsage
    run_task = asyncio.create_task(run_task_)

    while not handled_req:
        await asyncio.sleep(0.1)
    run_task.cancel()
    try:
        await run_task
    except asyncio.exceptions.CancelledError:
        pass

    # run_task_.throw(aiohttp.web.GracefulExit())

    # await run_task

    # class RedirectHandler(http.server.BaseHTTPRequestHandler):
    #     def do_GET(self):
    #         self.send_response(200)
    #         self.send_header('Content-type', 'text/html')
    #         self.end_headers()
    #         self.wfile.write(b'<html><head><title>Sly API Redirect</title></head><body><p>The authentication flow has completed. You may close this window or tab.</p></body></html>')
    #         query = {
    #             k: v[0] for k, v in 
    #             urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query) 
    #         }
    # rhs = http.server.HTTPServer(('localhost', 8080), RedirectHandler)
    # rhs.handle_request()

    if 'state' not in query:
        raise PermissionError("Redirect did not return any state parameter.")
    if not query['state'] == challenge:
        raise PermissionError("Redirect did not return the correct state parameter.")

    code = query['code']

    # step 2: exchange the code for access token
    user = await client.grant(redirect_uri, code, scopes)

    return user