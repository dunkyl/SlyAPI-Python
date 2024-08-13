'''
Implemenation of OAuth1.0a as the `Auth` interface
https://datatracker.ietf.org/doc/html/rfc5849
'''
import base64, hmac, secrets
import json
from datetime import datetime
from hashlib import sha1
from typing import Any

from dataclasses import dataclass

import aiohttp
from aiohttp import ClientSession as Client

from .auth import Auth
from .web import Method, Request, serve_once

# https://datatracker.ietf.org/doc/html/rfc5849#section-3.6
def percentEncode(s: str):
    result = ''
    URLSAFE = b'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._~'
    for c in s.encode('utf8'):
        result += chr(c) if c in URLSAFE else F'%{c:02X}'
    return result

# https://datatracker.ietf.org/doc/html/rfc5849#section-3.4.1.3.2
def paramString(params: dict[str, Any]) -> str:
    results: list[str] = []
    encoded = {
        percentEncode(k): percentEncode(v) for k, v in params.items()
    }
    for k, v in sorted(encoded.items()):
        results.append(F'{k}={v}')
    return '&'.join(results)

# https://datatracker.ietf.org/doc/html/rfc5849#section-3.4.2
def _hmac_sign(request: Request, signing_params: dict[str, Any], appSecret: str, userSecret: str|None = None) -> str:
        if not request.data_is_json:
            if isinstance(request.data, dict):
                all_params = { **request.data }
            else:
                raise TypeError(F"Expected dict, got {type(request.data)}")
        else:
            all_params = {}
        all_params |= request.query_params | signing_params
        base = F"{request.method.value.upper()}&{percentEncode(request.url.lower())}&{percentEncode(paramString(all_params))}"
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
    timestamp = str(int(datetime.now().timestamp()))
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
class OAuth1User:
    key: str
    secret: str
            
    @classmethod
    def from_json_obj(cls, obj: dict[str, str]) -> 'OAuth1User':
        '''Read an app from a JSON object'''
        match obj:
            case { # asdict(self)
                'key': key,
                'secret': secret
            }:
                return cls(key, secret)
            case { # OAuth1 grant
                'oauth_token': key, 
                'oauth_token_secret': secret
            }:
                return cls(key, secret)
            case _:
                raise ValueError(F"Unknown format for OAuth1User: {obj}")

    @classmethod
    def from_json_file(cls, path: str) -> 'OAuth1User':
        '''Read an app from a JSON file path'''
        with open(path, 'rb') as f:
            return cls.from_json_obj(json.load(f))

@dataclass
class OAuth1App:
    key: str
    secret: str

    request_uri: str # step 1
    authorize_uri: str # step 2
    access_uri: str # step 3

    @classmethod
    def from_json_obj(cls, obj: dict[str, str]) -> 'OAuth1App':
        '''Read an app from a JSON object'''
        match obj:
            case { # asdict(self)
                'key': key,
                'secret': secret,
                'request_uri': request_uri,
                'authorize_uri': authorize_uri,
                'access_uri': access_uri
            }: 
                return cls(key, secret, request_uri, authorize_uri, access_uri)
            case _:
                raise ValueError(F"Unknown format for OAuth1App: {obj}")

    @classmethod
    def from_json_file(cls, path: str) -> 'OAuth1App':
        '''Read an app from a JSON file path'''
        with open(path, 'rb') as f:
            return cls.from_json_obj(json.load(f))
        
    def sign(self, request: Request, user: OAuth1User|None=None) -> Request:
        signing_params = _common_oauth_params(self.key)
        if user:
            signing_params['oauth_token'] = user.key
            user_secret = user.secret
        else:
            user_secret = None

        signature = _hmac_sign(request, signing_params, self.secret, user_secret)

        oauth_params = signing_params | { 'oauth_signature': signature }
        oauth_params_str = ', '.join(F'{percentEncode(k)}="{percentEncode(v)}"' for k, v in sorted(oauth_params.items()))
        oauth_headers =  {
            'Authorization': F"OAuth {oauth_params_str}",
        }
        
        request.headers |= oauth_headers

        return request
    
@dataclass
class OAuth1(Auth):
    """Provides the Auth interface implementation for OAuth1"""
    app: OAuth1App
    user: OAuth1User

    def __init__(self, app: OAuth1App|str, user: OAuth1User|str):
        """Load an OAuth1 app and user from JSON files or existing objects."""
        if isinstance(app, str):
            app = OAuth1App.from_json_file(app)
        if isinstance(user, str):
            user = OAuth1User.from_json_file(user)
        self.app = app
        self.user = user

    async def sign(self, client: Client, request: Request) -> Request:
        return self.app.sign(request, self.user)
    
    

async def command_line_oauth1(
        app: OAuth1App,
        redirect_host: str,
        redirect_port: int,
        usePin: bool
        ) -> OAuth1User:
    import webbrowser
    import urllib.parse

    redirect_uri = F'http://{redirect_host}:{redirect_port}'

    # step 1: get a token to ask the user for authorization
    request = Request(
        Method.POST,
        app.request_uri,
        {'oauth_callback': 'oob' if usePin else percentEncode(redirect_uri)}
    )

    signed_request = app.sign(request)
    
    oauth_token = None
    async with aiohttp.ClientSession() as session:
        async with signed_request.send(session) as resp:
            content = await resp.text()
            resp_params = urllib.parse.parse_qs(content)
            if 'oauth_token' not in resp_params:
                print(F"Response did not provide authorization:\n{content}")
                print("\nThis is probably because the credentials for the app are invalid.")
                exit(1)
                # raise ValueError(F"Response did not provide authorization:\n{content}")
            oauth_token = resp_params['oauth_token'][0]
            # oauth_token_secret = resp_params['oauth_token_secret'][0]
            if resp_params['oauth_callback_confirmed'][0] != 'true':
                raise ValueError("oauth_callback_confirmed was not true")

    # step 2: get the user to authorize the application
    grant_link = F"{app.authorize_uri}?{urllib.parse.urlencode({'oauth_token': oauth_token})}"

    webbrowser.open(grant_link, new=1, autoraise=True)

    # step 2 (cont.): wait for the user to be redirected with the code
    if usePin:
        pin = input("Enter the PIN: ")
        oauth_verifier = pin

    else:
        query = await serve_once(redirect_host, redirect_port, 'step2.html')

        oauth_token = query['oauth_token']
        oauth_verifier = query['oauth_verifier']

    # step 3: exchange the code for access token
    # this step does not use the OAuth authorization headers
    async with aiohttp.request('POST', app.access_uri, params = {
        'oauth_token': oauth_token,
        'oauth_verifier': oauth_verifier
    }) as resp:
        content = await resp.text()
        resp_params = urllib.parse.parse_qs(content)
        return OAuth1User.from_json_obj(
            {k: v[0] for k, v in resp_params.items()})
