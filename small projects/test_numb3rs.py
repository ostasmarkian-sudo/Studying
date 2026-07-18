import pytest
from numb3rs import validate
def test():
    assert validate("192.168.001.1") == False
    assert validate("255.255.255.255") == True
    assert validate("512.512.512.512") == False
    assert validate("1.2.3.1000") == False
def test_srt():
    assert validate("cat") == False