
import pytest
from app_code import km_to_mp

def test_km_to_mp_conversion_1():
    """Testar a conversão de 1 km/h para milhas/h"""
    assert abs(km_to_mp(1) - 0.621371) < 1e-6

def test_km_to_mp_conversion_100():
    """Testar a conversão de 100 km/h para milhas/h"""
    assert abs(km_to_mp(100) - 62.1371) < 1e-6

def test_km_to_mp_conversion_0():
    """Testar a conversão de 0 km/h para milhas/h"""
    assert km_to_mp(0) == 0

def test_km_to_mp_conversion_negative():
    """Testar a conversão de -1 km/h para milhas/h"""
    assert abs(km_to_mp(-1) + 0.621371) < 1e-6
