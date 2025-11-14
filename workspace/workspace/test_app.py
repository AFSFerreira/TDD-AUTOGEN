
import pytest
from app_code import knight_move

def test_knight_move_from_e4():
    """Testar o movimento do cavalo a partir da posição 'e4'"""
    assert knight_move('e4') == ['d2', 'd6', 'f2', 'f6', 'c3', 'c5', 'g3', 'g5']

def test_knight_move_from_a1():
    """Testar o movimento do cavalo a partir da posição 'a1'"""
    assert knight_move('a1') == ['b3', 'c2']

def test_knight_move_from_h8():
    """Testar o movimento do cavalo a partir da posição 'h8'"""
    assert knight_move('h8') == ['g6', 'f7']

def test_knight_move_from_d4():
    """Testar o movimento do cavalo a partir da posição 'd4'"""
    assert knight_move('d4') == ['c2', 'c6', 'e2', 'e6', 'b3', 'b5', 'f3', 'f5']
