from SlyAPI import *
from SlyAPI.webapi import combine_params

class Scope(EnumParam):
    READONLY     = "test.readonly"
    MEMBERS      = "test.channel-memberships.creator"

def test_to_dict():
    param = Scope.READONLY
    assert combine_params(param) == { 'scope': 'test.readonly' }

# def test_str():
#     param = Scope.READONLY
#     assert str(param) == "test.readonly"

def test_in():
    param = Scope.READONLY
    assert Scope.READONLY in param
    assert Scope.MEMBERS not in param

    param += Scope.MEMBERS
    assert Scope.READONLY in param
    assert Scope.MEMBERS in param

def test_eq():
    param = Scope.READONLY
    assert param == Scope.READONLY
    assert param != Scope.MEMBERS

    param += Scope.MEMBERS
    assert param != Scope.READONLY
    assert param != Scope.MEMBERS

    assert param == (Scope.READONLY + Scope.MEMBERS)