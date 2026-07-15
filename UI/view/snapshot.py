from dataclasses import dataclass

@dataclass(frozen=True)
class GameSnapshot:
    grid: list
    game_over: bool

    @classmethod
    def from_board(cls, board, game_over):
        return cls(grid=board.snapshot(), game_over=game_over)
