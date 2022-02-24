from datetime import datetime, timedelta
from dataclasses import dataclass
import secrets
from typing import Any

from .auth import Auth
from .web import Request, serve_one_request

import aiohttp, aiohttp.web

import urllib.parse

@dataclass
class OAuth2User:
    token: str
    refresh_token: str
    expires_at: datetime
    token_type: str = 'Bearer'

    def __init__(self, source: dict[str, Any]) -> None:
        match source:
            case {
                'token': token,
                'refresh_token': refresh_token,
                'expires_at': expires_at_str,
                'token_type': token_type,
            }: #dumps
                self.token = token
                self.refresh_token = refresh_token
                self.expires_at = datetime.strptime(expires_at_str, '%Y-%m-%dT%H:%M:%S.%fZ')
                self.token_type = token_type
            case {
                'access_token': token,
                'refresh_token': refresh_token,
                'expires_in': expires_str,
                'token_type': token_type,
                **_others
            }: # OAuth 2 grant response OR refresh response
                expiry = datetime.utcnow() + timedelta(seconds=int(expires_str))
                self.token = token
                self.refresh_token = refresh_token
                self.expires_at = expiry
                self.token_type = token_type
            case _:
                raise ValueError(F"Invalid OAuth2User source: {source}")

    def to_dict(self) -> dict[str, str]:
        return {
            'token': self.token,
            'refresh_token': self.refresh_token,
            'expires_at': self.expires_at.strftime('%Y-%m-%dT%H:%M:%S.%fZ'),
            'token_type': self.token_type,
        }

@dataclass
class OAuth2(Auth):
    id: str
    secret: str

    auth_uri: str # flow step 1
    token_uri: str # flow step 2

    user: OAuth2User | None = None

    def __init__(self, source: dict[str, Any], user: OAuth2User | None = None) -> None:
        match source:
            case { 'id': id_, 'secret': secret, 'auth_uri': auth_uri, 'token_uri': token_uri}: # dumps
                self.id = id_
                self.secret = secret
                self.auth_uri = auth_uri
                self.token_uri = token_uri
            case _:
                raise ValueError(F"Invalid OAuth1 source: {source}")
        self.user = user

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

    def sign_request(self, request: Request, do_user: bool = True) -> Request:
        if self.user is not None and do_user:
            request.headers['Authorization'] = F"{self.user.token_type} {self.user.token}"
        else:
            raise NotImplemented("OAuth request signing without user is not yet implemented.")
        return request

    async def refresh(self, session: aiohttp.ClientSession):
        if self.user is None:
            raise NotImplemented("Refresh without user is not implemented.")
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': self.user.refresh_token,
            'client_id': self.id,
            'client_secret': self.secret,
        }
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        async with session.post(self.token_uri, data=data, headers=headers) as resp:
            if resp.status != 200:
                raise Exception(f'Refresh failed: {resp.status}')
            result = await resp.json()
            user = OAuth2User(result)
        self.user = user
    # @staticmethod
    # def from_file(filename: str) -> 'OAuth2':
    #     with open(filename, 'r') as f:
    #         data = json.load(f)
    #     match data:
    #         case {'web': {
    #                 'client_id': id,
    #                 'client_secret': secret, 'token_uri': token_uri,
    #                 'auth_uri': auth_uri }}: # google flavour
    #             return OAuth2(id, secret, token_uri, auth_uri)
    #         case _:
    #             raise ValueError(f"Unknown client format in: {filename}")
         
    async def user_auth_flow(self, redirect_host: str, redirect_port: int, **kwargs: str):
        import webbrowser

        redirect_uri = F'http://{redirect_host}:{redirect_port}'

        session = aiohttp.ClientSession()

        scopes: str = kwargs['scopes']

        # step 1: get the user to authorize the application
        grant_link, challenge = self.get_auth_url(redirect_uri, '', scopes)

        webbrowser.open(grant_link, new=1, autoraise=True)

        # step 1 (cont.): wait for the user to be redirected with the code
        query = await serve_one_request(redirect_host, redirect_port, '<html><body>You can close this window now.</body></html>')

        if 'state' not in query:
            raise PermissionError("Redirect did not return any state parameter.")
        if not query['state'] == challenge:
            raise PermissionError("Redirect did not return the correct state parameter.")
        code = query['code']

        # step 2: exchange the code for access token
        grant_data = {
            'grant_type': 'authorization_code',
            'code': code,
            'client_id': self.id,
            'client_secret': self.secret,
            'redirect_uri': redirect_uri,
            'scope': scopes
        }
        grant_headers = {'Content-Type': 'application/x-www-form-urlencoded'}

        async with session.post(self.token_uri, data=grant_data, headers=grant_headers) as resp:
            if resp.status != 200:
                raise Exception(f'Grant failed: {resp.status}')
            result = await resp.json()
            print(F"Step 2 response:\n{result}")
            user = OAuth2User(result)

        self.user = user