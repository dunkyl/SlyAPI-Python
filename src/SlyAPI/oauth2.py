import asyncio
from datetime import datetime
from dataclasses import dataclass
import secrets
from typing import cast

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

@dataclass
class OAuth2User:
    token: str
    refresh_token: str
    expires_at: datetime


def Step1_Provide_Grant_Link(client: OAuth2Client, redirect_uri: str, state: str, scopes: str):
    challenge = secrets.token_urlsafe(54)
    params = {
        'client_id': client.id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'state': state+challenge,
        'scope': scopes
        }
    return F"{client.auth_uri}?{urllib.parse.urlencode(params)}", challenge

async def Step2_Exchange_Grant_Code(client: OAuth2Client, redirect_uri: str, code: str, scopes: str):
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': client.id,
        'client_secret': client.secret,
        'redirect_uri': redirect_uri,
        'scope': scopes
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    async with aiohttp.ClientSession() as session:
        async with session.post(client.token_uri, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise Exception('OAuth2 step 2 failed')
            result = await resp.json()
            return OAuth2User(**result)

async def Step3_Refresh_Token(client: OAuth2Client, user: OAuth2User):
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': user.refresh_token,
        'client_id': client.id,
        'client_secret': client.secret,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    async with aiohttp.ClientSession() as session:
        async with session.post(client.token_uri, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise Exception('OAuth2 step 3 failed')
            result = await resp.json()
            return OAuth2User(**result)

async def localhost_flow(client: OAuth2Client, scopes: str) -> OAuth2User:
    '''
    Set up an http server and open a browser to make one grant.
    '''

    # step 1: get the user to authorize the application
    grant_link, challenge = Step1_Provide_Grant_Link(client, 'http://localhost:8080', '', scopes)

    webbrowser.open(grant_link, new=1, autoraise=True)

    # step 1 (cont.): wait for the user to be redirected with the code
    query: dict[str, str] = {}

    server = aiohttp.web.Application()

    async def close_after():
        await asyncio.sleep(0.5)
        raise GracefulExit
    async def index_handler(request: aiohttp.web.Request):
        nonlocal query
        query = cast(dict[str, str], request.query)
        asyncio.create_task(close_after())
        return aiohttp.web.Response(text='<html><body>You can close this window now.</body></html>')
    server.router.add_get("/", index_handler)
    await aiohttp.web._run_app(server, host='localhost', port=8080) # type: ignore ## reportPrivateUsage

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
    user = await Step2_Exchange_Grant_Code(client, 'http://localhost:8080', code, scopes)

    return user