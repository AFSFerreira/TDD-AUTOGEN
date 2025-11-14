
def knight_move(pos: str) -> list:
    """
    Calcula as casas que um cavalo pode se mover a partir de uma posição no tabuleiro de xadrez.
    
    Args:
        pos: A posição atual do cavalo, representada como uma string (ex: 'e4').
    
    Returns:
        list: Uma lista de casas para onde o cavalo pode se mover.
    """
    # Mapeia as colunas e linhas do tabuleiro
    columns = 'abcdefgh'
    row = int(pos[1]) - 1
    col = columns.index(pos[0])
    
    # Movimentos possíveis do cavalo
    moves = [
        (2, 1), (2, -1), (-2, 1), (-2, -1),
        (1, 2), (1, -2), (-1, 2), (-1, -2)
    ]
    
    possible_moves = []
    
    for move in moves:
        new_row = row + move[0]
        new_col = col + move[1]
        if 0 <= new_row < 8 and 0 <= new_col < 8:
            possible_moves.append(columns[new_col] + str(new_row + 1))
    
    return possible_moves
