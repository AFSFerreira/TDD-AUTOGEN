
from typing import List

def knight_move(pos: str) -> List[str]:
    """Calcula os movimentos possíveis do cavalo a partir de uma posição no tabuleiro de xadrez.
    
    Args:
        pos: Posição no formato de coluna e linha (ex: 'e4').
    
    Returns:
        List[str]: Lista de posições para onde o cavalo pode se mover.
    """
    column, row = pos[0], int(pos[1])
    moves = []
    column_index = ord(column) - ord('a')
    
    # Movimentos possíveis do cavalo
    knight_moves = [
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2)
    ]
    
    for move in knight_moves:
        new_column_index = column_index + move[0]
        new_row = row + move[1]
        if 0 <= new_column_index < 8 and 1 <= new_row <= 8:
            new_column = chr(new_column_index + ord('a'))
            moves.append(f"{new_column}{new_row}")
    
    return moves
