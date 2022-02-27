from SlyAPI import *

class Scope(EnumParam):
    READONLY     = "test.readonly"
    MEMBERS      = "test.channel-memberships.creator"

def test_to_dict():
    param = Scope.READONLY
    assert param.to_dict() == { 'scope': 'test.readonly' }

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