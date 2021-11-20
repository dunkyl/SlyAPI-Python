import base64
from hashlib import sha1
import hmac
import secrets

from urllib.parse import urlencode


# https://tools.ietf.org/html/rfc5849#section-3.4.2

class OAuth1Client:
    id: str
    secret: str

class OAuth1User:
    pass