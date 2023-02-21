import base64, hmac, secrets
import json
from datetime import datetime
from hashlib import sha1
from typing import Any

from dataclasses import dataclass

import aiohttp

from .auth import Auth
from .web import Method, Request, serve_one_request

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
def _hmac_sign(request: Request, signing_params: dict[str, Any], appSecret: str, userSecret: str|None = None) -> str:
        if not request.data_is_json:
            all_params = { **request.data }
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
class OAuth1User:
    key: str
    secret: str

    def __init__(self, source: str | dict[str, Any]):
        match source:
            case str(): # json file path
                with open(source) as f:
                    self.__init__(json.load(f))
            case { 'key': key, 'secret': secret }: # dumps
                self.key = key
                self.secret = secret
            case {
                'oauth_token': key, 
                'oauth_token_secret': secret,
                **_others
            }: # OAuth1 grant
                self.key = key
                self.secret = secret
            case _:
                raise ValueError(F"Invalid OAuth1User source: {source}")

@dataclass
class OAuth1(Auth):
    key: str
    secret: str

    request_uri: str # flow step 1
    authorize_uri: str # flow step 2
    access_uri: str # flow step 3

    user: OAuth1User | None = None

    def __init__(self, source: str | dict[str, Any], user: OAuth1User | None = None) -> None:
        match source:
            case str(): # file path
                with open(source, 'r') as f:
                    self.__init__(json.load(f))
            case { 'key': key, 'secret': secret, 'request_uri': request_uri, 'authorize_uri': authorize_uri, 'access_uri': access_uri }: # dumps
                self.key = key
                self.secret = secret
                self.request_uri = request_uri
                self.authorize_uri = authorize_uri
                self.access_uri = access_uri
            case _:
                raise ValueError(F"Invalid OAuth1 source: {source}")
        self.user = user

    async def sign(self, client: aiohttp.ClientSession, request: Request) -> Request:
        signing_params = _common_oauth_params(self.key)
        user_secret = None
        if self.user is not None:
            signing_params['oauth_token'] = self.user.key
            user_secret = self.user.secret

        signature = _hmac_sign(request, signing_params, self.secret, user_secret)

        oauth_params = signing_params | { 'oauth_signature': signature }
        oauth_params_str = ', '.join(F'{percentEncode(k)}="{percentEncode(v)}"' for k, v in sorted(oauth_params.items()))
        oauth_headers =  {
            'Authorization': F"OAuth {oauth_params_str}",
        }
        
        request.headers |= oauth_headers

        return request

async def command_line_oauth1(oauth1: OAuth1, redirect_host: str, redirect_port: int, usePin: bool):
    import webbrowser
    import urllib.parse

    redirect_uri = F'http://{redirect_host}:{redirect_port}'

    session = aiohttp.ClientSession()

    # step 1: get a token to ask the user for authorization
    request = Request(
        Method.POST,
        oauth1.request_uri,
        {'oauth_callback': 'oob' if usePin else percentEncode(redirect_uri)}
    )
    assert oauth1.user is None
    signed_request = await oauth1.sign(session, request)
    
    oauth_token = None
    async with signed_request.send(session) as resp:
        content = await resp.text()
        resp_params = urllib.parse.parse_qs(content)
        if 'oauth_token' not in resp_params:
            print(F"Response did not provide authorization:\n{content}")
            print("\nThis is probably because the credentials for the app are invalid.")
            await session.close()
            exit(1)
            # raise ValueError(F"Response did not provide authorization:\n{content}")
        oauth_token = resp_params['oauth_token'][0]
        # oauth_token_secret = resp_params['oauth_token_secret'][0]
        if resp_params['oauth_callback_confirmed'][0] != 'true':
            raise ValueError(f"oauth_callback_confirmed was not true")

    # step 2: get the user to authorize the application
    grant_link = F"{oauth1.authorize_uri}?{urllib.parse.urlencode({'oauth_token': oauth_token})}"

    webbrowser.open(grant_link, new=1, autoraise=True)

    # step 2 (cont.): wait for the user to be redirected with the code
    if usePin:
        pin = input("Enter the PIN: ")
        oauth_verifier = pin

    else:
        query = await serve_one_request(redirect_host, redirect_port, '<html><body>You can close this window now.</body></html>')

        oauth_token = query['oauth_token']
        oauth_verifier = query['oauth_verifier']

    # step 3: exchange the code for access token
    # this step does not use the OAuth authorization headers
    async with session.request('POST', oauth1.access_uri, params = {
        'oauth_token': oauth_token,
        'oauth_verifier': oauth_verifier
    }) as resp:
        content = await resp.text()
        resp_params = urllib.parse.parse_qs(content)
        oauth1.user = OAuth1User({k: v[0] for k, v in resp_params.items()})

    await session.close()
