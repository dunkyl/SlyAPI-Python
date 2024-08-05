from dataclasses import dataclass, field
from datetime import datetime, timedelta
import asyncio
import json

from aiohttp import ClientSession as Client, formdata

from .web import JsonMap, Request
from .auth import Auth
import jwt

@dataclass
class ServiceGrant:
    'Temporary (hours to days), secret value used to sign requests'
    access_token: str
    expires_at: datetime # must be tz-aware
    token_type: str

@dataclass
class ServiceAccount:
    'Used to acquire grants for Google Cloud service accounts'
    client_email: str
    client_id: str
    private_key: str
    auth_uri: str
    token_uri: str

    async def grant(self, client: Client, scopes: list[str]) -> ServiceGrant:
        now_stamp = datetime.now().timestamp()
        token: str = jwt.encode({
            "iss": self.client_email,
            "scope": " ".join(scopes),
            "aud": "https://oauth2.googleapis.com/token",
            "exp": now_stamp + 1800, # 30 minutes from now
            "iat": now_stamp
        }, self.private_key, algorithm="RS256")
        data = formdata.FormData({
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": token
        })
        async with client.request('POST', self.token_uri, data=data) as req:
            obj = await req.json()
            return ServiceGrant(
                obj["access_token"],
                datetime.now() + timedelta(seconds = float(obj["expires_in"])),
                obj["token_type"]
            )

    @classmethod
    def from_json_obj(cls, obj: JsonMap) -> 'ServiceAccount':
        '''Create from a JSON object in the Google Console JSON format'''
        match obj:
            case { # google json or to_dict(self)
                'client_email': str(client_email),
                'client_id': str(client_id),
                'private_key': str(private_key),
                'auth_uri': str(auth_uri),
                'token_uri': str(token_uri),
                **_rest
            }: 
                return cls(client_email, client_id, private_key, auth_uri, token_uri)
            case _:
                raise ValueError(F"Unknown format for Service Account: {obj}")

    @classmethod
    def from_json_file(cls, path: str) -> 'ServiceAccount':
        '''Create from a JSON file path'''
        with open(path, 'rb') as f:
            return cls.from_json_obj(json.load(f))

@dataclass
class OAuth2ServiceAccount(Auth):
    'Google Cloud service account'
    account: ServiceAccount
    scopes: list[str]
    _grant: ServiceGrant | None = None
    _refreshed: asyncio.Semaphore = asyncio.Semaphore()

    def __init__(self, account: str | ServiceAccount, scopes: list[str]):
        if isinstance(account, str):
            account = ServiceAccount.from_json_file(account)
        self.account = account
        self.scopes = scopes
        self._grant = None
        self._refreshed = asyncio.Semaphore()

    async def sign(self, client: Client, request: Request) -> Request:
        await self._refreshed.acquire()
        if self._grant is None or datetime.now() > self._grant.expires_at:
            self._grant = await self.account.grant(client, self.scopes)
        self._refreshed.release()
        request.headers['Authorization'] = \
            F"{self._grant.token_type} {self._grant.access_token}"
        return request