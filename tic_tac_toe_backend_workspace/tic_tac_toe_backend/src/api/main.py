from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
import uuid
import random
from copy import deepcopy


app = FastAPI(
    title="Tic Tac Toe API",
    description=(
        "FastAPI backend for managing Tic Tac Toe games, supporting two-player and "
        "single-player vs AI logic."
    ),
    version="1.0.0",
    openapi_tags=[
        {"name": "game", "description": "Game state management and play"},
    ]
)

# Add CORSMiddleware to handle CORS preflight OPTIONS requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can change this to your frontend's origin for stricter security
    allow_credentials=True,
    allow_methods=["*"],  # Allows all HTTP methods
    allow_headers=["*"],  # Allows all HTTP headers
)


class StartGameRequest(BaseModel):
    mode: Literal['pvp', 'ai'] = Field(
        ...,
        description="Game mode: 'pvp' for 2 players, 'ai' for player vs AI."
    )
    player_starts: Literal['X', 'O'] = Field(
        'X', description="Which side starts the game. 'X' or 'O'."
    )


class GameState(BaseModel):
    game_id: str = Field(
        ..., description="Unique identifier for the game session."
    )
    board: List[List[Optional[str]]] = Field(
        ...,
        description="3x3 board (list of lists), values: 'X', 'O', or None."
    )
    current_turn: str = Field(
        ..., description="Whose turn: 'X' or 'O'."
    )
    status: Literal['in_progress', 'won', 'draw'] = Field(
        ..., description="Current state of the game."
    )
    winner: Optional[str] = Field(
        None, description="'X', 'O', or None if not applicable."
    )
    mode: Literal["pvp", "ai"] = Field(
        ..., description="Game mode (player-vs-player or AI)."
    )


class MoveRequest(BaseModel):
    row: int = Field(
        ..., ge=0, le=2, description="Row index of the move (0-2)"
    )
    col: int = Field(
        ..., ge=0, le=2, description="Column index of the move (0-2)"
    )
    player: str = Field(
        ..., pattern="^(X|O)$", description="'X' or 'O' making the move"
    )


class StatusResponse(GameState):
    pass


games = {}


def empty_board():
    return [[None, None, None] for _ in range(3)]


def check_win(board, symbol):
    # Rows, columns and diagonals
    for i in range(3):
        if all(board[i][j] == symbol for j in range(3)):
            return True
        if all(board[j][i] == symbol for j in range(3)):
            return True
    if all(board[i][i] == symbol for i in range(3)):
        return True
    if all(board[i][2 - i] == symbol for i in range(3)):
        return True
    return False


def is_draw(board):
    return all(cell in ['X', 'O'] for row in board for cell in row)


def available_moves(board):
    return [(i, j) for i in range(3) for j in range(3) if board[i][j] is None]


def ai_move(board):
    # Very simple AI: pick a random available cell
    moves = available_moves(board)
    if moves:
        return random.choice(moves)
    else:
        return None


def compute_game_status(board):
    for symbol in ['X', 'O']:
        if check_win(board, symbol):
            return {'status': 'won', 'winner': symbol}
    if is_draw(board):
        return {'status': 'draw', 'winner': None}
    return {'status': 'in_progress', 'winner': None}


# PUBLIC_INTERFACE
@app.get("/", tags=["game"], summary="Health check")
def health_check():
    """Simple health check endpoint."""
    return {"message": "Healthy"}


# PUBLIC_INTERFACE
@app.post(
    "/game/start",
    response_model=GameState,
    tags=["game"],
    summary="Start a new game"
)
def start_game(req: StartGameRequest):
    """
    Starts a new Tic Tac Toe game.

    - **mode**: "pvp" (2 players) or "ai" (single-player vs computer).
    - **player_starts**: 'X' or 'O' (who makes the first move).
    """
    game_id = str(uuid.uuid4())
    init_board = empty_board()
    mode = req.mode
    current_turn = req.player_starts
    status = "in_progress"
    winner = None

    # If AI mode and AI starts, let AI make the first move.
    if mode == "ai" and current_turn == "O":
        i, j = ai_move(init_board)
        init_board[i][j] = "O"
        # Update current turn after AI move
        current_turn = "X"
        game_status = compute_game_status(init_board)
        status = game_status['status']
        winner = game_status['winner']

    games[game_id] = {
        'board': deepcopy(init_board),
        'current_turn': current_turn,
        'status': status,
        'winner': winner,
        'mode': mode
    }

    return GameState(
        game_id=game_id,
        board=init_board,
        current_turn=current_turn,
        status=status,
        winner=winner,
        mode=mode
    )


# PUBLIC_INTERFACE
@app.post(
    "/game/{game_id}/move",
    response_model=GameState,
    tags=["game"],
    summary="Make a move"
)
def make_move(game_id: str, req: MoveRequest):
    """
    Make a move for the specified player at the given coordinates.

    For AI mode, responds with updated board including the AI's move after player's turn.

    - **row**: 0-2
    - **col**: 0-2
    - **player**: "X" or "O"
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found.")

    if game['status'] != 'in_progress':
        raise HTTPException(
            status_code=400, detail="Game is already over."
        )

    board = game['board']
    current_turn = game['current_turn']
    mode = game['mode']

    if req.player != current_turn:
        raise HTTPException(
            status_code=400,
            detail=f"It is {current_turn}'s turn."
        )

    if not (0 <= req.row < 3 and 0 <= req.col < 3):
        raise HTTPException(
            status_code=400, detail="Invalid move coordinates."
        )

    if board[req.row][req.col] is not None:
        raise HTTPException(
            status_code=400, detail="Cell already taken."
        )

    # Make player move
    board[req.row][req.col] = req.player

    game_status = compute_game_status(board)
    if game_status['status'] == 'in_progress':
        # Continue game
        if mode == "ai" and req.player == "X":
            # AI (O) moves next
            ai_pos = ai_move(board)
            if ai_pos:
                i, j = ai_pos
                board[i][j] = "O"
                game_status = compute_game_status(board)
                next_turn = (
                    "X"
                    if game_status['status'] == 'in_progress'
                    else current_turn
                )
            else:
                next_turn = "X"
        else:
            # PvP mode or O's move in AI mode
            next_turn = "O" if req.player == "X" else "X"
    else:
        # If win or draw, doesn't matter
        next_turn = current_turn

    # Update game state
    game['board'] = deepcopy(board)
    game['status'] = game_status['status']
    game['winner'] = game_status['winner']
    game['current_turn'] = (
        next_turn if game_status['status'] == 'in_progress'
        else current_turn
    )

    return GameState(
        game_id=game_id,
        board=deepcopy(board),
        current_turn=game['current_turn'],
        status=game_status['status'],
        winner=game_status['winner'],
        mode=mode
    )


# PUBLIC_INTERFACE
@app.get(
    "/game/{game_id}/status",
    response_model=StatusResponse,
    tags=["game"],
    summary="Get game status"
)
def get_game_status(game_id: str):
    """
    Returns the current state of the game.

    - **game_id**: Game to check.
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(
            status_code=404, detail="Game not found."
        )
    return GameState(
        game_id=game_id,
        board=deepcopy(game['board']),
        current_turn=game['current_turn'],
        status=game['status'],
        winner=game['winner'],
        mode=game['mode']
    )


# PUBLIC_INTERFACE
@app.post(
    "/game/{game_id}/reset",
    response_model=GameState,
    tags=["game"],
    summary="Reset game"
)
def reset_game(game_id: str):
    """
    Resets the game to an empty board and the same mode.
    The starting player is set to 'X' unless AI mode with AI starting ('O').
    """
    game = games.get(game_id)
    if not game:
        raise HTTPException(
            status_code=404, detail="Game not found."
        )
    mode = game.get('mode')
    # Default player to start after reset is X (unless AI mode with O)
    player_starts = "X"
    status = "in_progress"
    winner = None
    init_board = empty_board()
    if mode == "ai":
        # If last winner was O, maybe let AI start after reset, otherwise always X start
        # for simplicity
        if player_starts == "O":
            i, j = ai_move(init_board)
            init_board[i][j] = "O"
            current_turn = "X"
            stat = compute_game_status(init_board)
            status = stat['status']
            winner = stat['winner']
        else:
            current_turn = "X"
    else:
        current_turn = "X"

    games[game_id] = {
        'board': deepcopy(init_board),
        'current_turn': current_turn,
        'status': status,
        'winner': winner,
        'mode': mode
    }
    return GameState(
        game_id=game_id,
        board=init_board,
        current_turn=current_turn,
        status=status,
        winner=winner,
        mode=mode
    )
