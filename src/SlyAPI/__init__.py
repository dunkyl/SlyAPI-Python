'''
Foundational library for implementing client libraries for web APIs.
'''
from .webapi import WebAPI as WebAPI
from .oauth2 import OAuth2 as OAuth2, OAuth2User as OAuth2User, OAuth2App as OAuth2App, requires_scopes as requires_scopes
from .oauth1 import OAuth1 as OAuth1, OAuth1User as OAuth1User, OAuth1App as OAuth1App
from .auth import UrlApiKey as UrlApiKey, HeaderApiKey as HeaderApiKey
from .asyncy import AsyncTrans as AsyncTrans, AsyncLazy as AsyncLazy
