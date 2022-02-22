import base64
from datetime import datetime
from hashlib import sha1
import hmac
import secrets
from typing import Any

from dataclasses import dataclass

from .auth import Auth

# https://datatracker.ietf.org/doc/html/rfc5849


# https://datatracker.ietf.org/doc/html/rfc5849#section-3.6
def percentEncode(s: str):
    result = ''
    URLSAFE = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~'
    for c in s.encode('utf8'):
        result += chr(c) if c in URLSAFE else f'%{c:02X}'
    return result

# https://datatracker.ietf.org/doc/html/rfc5849#section-3.4.1.3.2
def paramString(params: dict[str, Any]) -> str:
    results: list[str] = []
    encoded = {
        percentEncode(k): percentEncode(v) for k, v in params.items()
    }
    for k, v in sorted(encoded.items()):
        results.append(f'{k}={v}')
    return '&'.join(results)

# https://datatracker.ietf.org/doc/html/rfc5849#section-3.4.2
def _hmac_sign(url: str, method: str, all_params: dict[str, Any], appSecret: str, userSecret: str|None = None) -> str:
        base = F"{method.upper()}&{percentEncode(url)}&{percentEncode(paramString(all_params))}"
        # NOTE:
        #  2.  An "&" character (ASCII code 38), which MUST be included
        #        even when either secret is empty.
        signingKey = percentEncode(appSecret) + '&'
        if userSecret is not None:
            signingKey +=  percentEncode(userSecret)

        hashed = hmac.new( bytes(signingKey,'ascii'),bytes(base, 'ascii'), sha1).digest() #.rstrip(b'\n')
        return base64.b64encode(hashed).decode('ascii')

def _common_oauth_params(appKey: str):
    nonce = base64.b64encode(secrets.token_bytes(32)).strip(b'+/=').decode('ascii')
    timestamp = str(int(datetime.utcnow().timestamp()))
    # nonce = base64.b64encode(b'a'*32).strip(b'+/=').decode('ascii')
    # timestamp = '1'
    return {
        'oauth_consumer_key': appKey,
        'oauth_nonce': nonce,
        'oauth_signature_method': 'HMAC-SHA1',
        'oauth_timestamp': timestamp,
        'oauth_version': '1.0'
    }

@dataclass
class OAuth1App:
    key: str
    secret: str

    def sign(self, url: str, method: str, params_and_formdata: dict[str, Any]) -> dict[str, str]:
        signing_params = _common_oauth_params(self.key)
        all_params = params_and_formdata | signing_params

        signature = _hmac_sign(url, method, all_params, self.secret)

        return signing_params | { 'oauth_signature': signature }

    @staticmethod
    def from_file(filename: str) -> 'OAuth1App':
        with open(filename, 'r') as f:
            data = json.load(f)
        match data:
            case { 'key': key, 'secret': secret }:
                return OAuth1App(key, secret)
            case _:
                raise ValueError(f"Unknown client format in: {filename}")

@dataclass
class OAuth1User:
    key: str
    secret: str

class OAuth1(Auth):

    def __init__(self, app: OAuth1App, user: OAuth1User):
        self.app = app
        self.user = user

    def sign(self, url: str, method: str, params_and_formdata: dict[str, Any]) -> dict[str, str]:
        signing_params = _common_oauth_params(self.app.key) | {
            'oauth_token': self.user.key
        }
        all_params = params_and_formdata | signing_params

        signature = _hmac_sign(url, method, all_params, self.app.secret, self.user.secret)

        return signing_params | { 'oauth_signature': signature }

    def get_headers(self, url: str, method: str, params_and_formdata: dict[str, Any]) -> dict[str, str]:
        oauth_params = self.sign(url, method, params_and_formdata)
        oauth_params_str = ', '.join(F'{percentEncode(k)}="{percentEncode(v)}"' for k, v in sorted(oauth_params.items()))
        return {
            'Authorization': F"OAuth {oauth_params_str}",
        }

    def get_common_params(self) -> dict[str, Any]:
        return {}

    def get_common_headers(self) -> dict[str, Any]:
        return {}

    @classmethod
    def from_file(cls, path: str) -> 'Auth': raise NotImplementedError()

    def to_dict(self) -> dict[str, Any]: raise NotImplementedError()

    async def refresh(self, *args: Any, **kwargs: Any) -> None: raise NotImplementedError()

import asyncio, json
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Any, cast
from .asyncy import end_loop_workaround

import aiohttp, aiohttp.web
# import http.server
import webbrowser

import urllib.parse

from aiohttp.web_runner import GracefulExit


# TODO: de-duplicate with OAuth2
async def localhost_flow(app: OAuth1App) -> OAuth1User:
    '''
    Set up an http server and open a browser to make one grant.
    '''

    end_loop_workaround()

    redirect_host = '127.0.0.1'
    redirect_port = 8080
    redirect_uri = F'http://{redirect_host}:{redirect_port}'

    session = aiohttp.ClientSession()
    oauth_req_url = 'https://api.twitter.com/oauth/request_token'

    

    # params = {'oauth_callback': redirect_uri}
    # params2 = {'oauth_callback': urllib.parse.quote(redirect_uri).replace('/', r'%2F')}
    params3 = {'oauth_callback': percentEncode(redirect_uri)}
    
    oauth_headers = OAuth1.get_headers(app, oauth_req_url, 'POST', params3)

    # print(oauth_headers)

    # import requests
    # resp = requests.post(oauth_req_url, headers=oauth_headers, params = params)
    # print(resp.headers)
    # print(oauth_headers)
    # print(resp.url)
    # # print(params2)
    # print(resp.text)


    # print(params)
    # print(params2)
    # print(oauth_headers)
    # print(urllib.parse.urlencode(params))

    # import sys; sys.exit(0)
    #+f'?{urllib.parse.urlencode(params)}'
    #+f"?oauth_callback={urllib.parse.quote(redirect_uri).replace('/', r'%2F')}"
    async with session.request('POST', oauth_req_url, params = params3, headers=oauth_headers) as resp:
        print(resp.url.raw_query_string)
        print(resp.status)
        content = await resp.text()
        print(content)
        resp_params = urllib.parse.parse_qs(content)
        oauth_token = resp_params['oauth_token'][0]
        print(oauth_token)
        oauth_token_secret = resp_params['oauth_token_secret'][0]
        print(oauth_token_secret)
        oauth_callback_confirmed = resp_params['oauth_callback_confirmed'][0]
        print(oauth_callback_confirmed)

    

    # step 1: get the user to authorize the application
    # TODO: make generic for any OAuth1App
    grant_link = 'https://api.twitter.com/oauth/authenticate?' + urllib.parse.urlencode({'oauth_token': oauth_token})

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

    oauth_token = query['oauth_token']
    oauth_verifier = query['oauth_verifier']


    # step 2: exchange the code for access token
    access_url = 'https://api.twitter.com/oauth/access_token'

    async with session.request('POST', access_url, params = {
        'oauth_token': oauth_token,
        'oauth_verifier': oauth_verifier
    }) as resp:
        content = await resp.text()
        print(content)
        resp_params = urllib.parse.parse_qs(content)
        oauth_token = resp_params['oauth_token'][0]
        print(oauth_token)
        oauth_token_secret = resp_params['oauth_token_secret'][0]
        print(oauth_token_secret)

    return OAuth1User(oauth_token, oauth_token_secret)