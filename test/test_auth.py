from datetime import datetime, timedelta
from dataclasses import asdict
from SlyAPI import *


def test_oauth1_serialize():

    obj = {
        'key': 'example_key',
        'secret': 'example_secret'
    }

    user1 = OAuth1User(obj)

    assert asdict(user1) == obj

    user2 = OAuth1User({
        'oauth_token': 'example_key',
        'oauth_token_secret': 'example_secret',
        'some_service_add_thing': 'example_thing'
    })

    user3 = OAuth1User("test/ex_oauth1_user.json")

    assert user1 == user2 == user3

    err_invalid = None
    try:
        _err_user_inv = OAuth1User({ "bad": "format" })
    except Exception as e :
        err_invalid = e

    assert err_invalid is not None
    assert isinstance(err_invalid, ValueError)

    err_not_found = None
    try:
        _err_user_not_found = OAuth1User("test/not_exists.json")
    except Exception as e:
        err_not_found = e

    assert err_not_found is not None
    assert isinstance(err_not_found, FileNotFoundError)

    obj = {
        'key': 'example_key',
        'secret': 'example_secret',
        'request_uri': 'https://example.com/request_token',
        'authorize_uri': 'https://example.com/authorize',
        'access_uri': 'https://example.com/access_token'
    }

    app1 = OAuth1(obj)

    app2 = OAuth1("test/ex_oauth1.json")

    assert app1 == app2

def test_oauth2_serialize():

    expiry = datetime.utcnow() + timedelta(seconds=3600)

    obj = {
        'token': 'example_token',
        'refresh_token': 'example_token',
        'expires_at': expiry.strftime("%Y-%m-%dT%H:%M:%SZ"),
        'token_type': 'Bearer',
        'scopes': ['read', 'write']
    }

    user1 = OAuth2User(obj)

    assert user1.to_dict() == obj

    user2 = OAuth2User({
        'access_token': 'example_token',
        'refresh_token': 'example_token',
        'expires_in': 3600,
        'token_type': 'Bearer',
        'scope': 'read write'
    })

    # user3 = OAuth2User("test/ex_oauth2_user.json")

    assert user1 == user2 # == user3

    err_invalid = None
    try:
        _err_user_inv = OAuth2User({ "bad": "format" })
    except Exception as e :
        err_invalid = e

    assert err_invalid is not None
    assert isinstance(err_invalid, ValueError)

    err_not_found = None
    try:
        _err_user_not_found = OAuth1User("test/not_exists.json")
    except Exception as e:
        err_not_found = e

    assert err_not_found is not None
    assert isinstance(err_not_found, FileNotFoundError)

    obj = {
        'id': 'example_client_id',
        'secret': 'example_secret',
        'token_uri': 'https://example.com/request_token',
        'auth_uri': 'https://example.com/authorize',
    }

    app1 = OAuth2(obj)

    app2 = OAuth2("test/ex_oauth2.json")

    assert app1 == app2

