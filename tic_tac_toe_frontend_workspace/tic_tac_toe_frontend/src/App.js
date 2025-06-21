import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE = 'https://vscode-internal-7743-qa.qa01.cloud.kavia.ai:3001';

// Helper: Initial empty board state for fallback UI hydration
const EMPTY_BOARD = [
  [null, null, null],
  [null, null, null],
  [null, null, null]
];

// Board Cell Component
function BoardCell({ value, onClick, disabled }) {
  return (
    <button
      className="ttt-cell"
      onClick={onClick}
      disabled={disabled || value !== null}
      aria-label={value ? `${value} placed` : 'Empty cell'}
    >
      {value}
    </button>
  );
}

// Board Component
function Board({ board, onCellClick, disabled }) {
  return (
    <div className="ttt-board">
      {board.map((row, i) =>
        row.map((cell, j) => (
          <BoardCell
            key={`${i},${j}`}
            value={cell}
            onClick={() => onCellClick(i, j)}
            disabled={disabled}
          />
        ))
      )}
    </div>
  );
}

// Status Display Component
function StatusBar({ currentTurn, status, winner, mode }) {
  let text = '';
  if (status === 'won') {
    text = winner
      ? (mode === 'ai' && winner === 'O'
          ? 'AI wins!'
          : `${winner} wins!`)
      : 'Winner!';
  } else if (status === 'draw') {
    text = "It's a draw!";
  } else {
    text = mode === 'ai'
      ? (currentTurn === 'O'
        ? "AI's turn..." 
        : "Your turn (X)")
      : `Next: ${currentTurn}`;
  }
  return (
    <div className="ttt-status-bar">
      {text}
    </div>
  );
}

function ModeSelector({ mode, setMode, inGame }) {
  return (
    <div className="ttt-mode-selector">
      <button
        className={`btn${mode === 'ai' ? ' btn-selected' : ''}`}
        onClick={() => setMode('ai')}
        disabled={inGame}
      >
        Single Player (vs AI)
      </button>
      <button
        className={`btn${mode === 'pvp' ? ' btn-selected' : ''}`}
        onClick={() => setMode('pvp')}
        disabled={inGame}
      >
        Two Player
      </button>
    </div>
  );
}

// Scoreboard (frontend-only session-based)
function ScoreDisplay({ scores }) {
  return (
    <div className="ttt-scoreboard">
      <span>X: {scores.X}</span>
      <span>O: {scores.O}</span>
      <span>Draws: {scores.draws}</span>
    </div>
  );
}

// PUBLIC_INTERFACE
function App() {
  // State for game
  const [gameId, setGameId] = useState(null);
  const [board, setBoard] = useState(EMPTY_BOARD);
  const [currentTurn, setCurrentTurn] = useState('X');
  const [status, setStatus] = useState('in_progress');
  const [winner, setWinner] = useState(null);
  const [mode, setMode] = useState('ai');
  const [isLoading, setIsLoading] = useState(false);
  const [playerStarts, setPlayerStarts] = useState('X');
  // Session-based score
  const [scores, setScores] = useState({ X: 0, O: 0, draws: 0 });

  // Start a new game with mode (ai or pvp)
  const startNewGame = async (forceStarter) => {
    setIsLoading(true);
    try {
      const starter = forceStarter || playerStarts;
      const resp = await fetch(`${API_BASE}/game/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode, player_starts: starter })
      });
      const data = await resp.json();
      setGameId(data.game_id);
      setBoard(data.board);
      setCurrentTurn(data.current_turn);
      setStatus(data.status);
      setWinner(data.winner);
      setPlayerStarts(starter);
    } catch (e) {
      alert("Failed to start game. Please try again.");
    } finally {
      setIsLoading(false);
    }
  };

  // Make a move
  const makeMove = async (row, col) => {
    if (!gameId) return;
    setIsLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/game/${gameId}/move`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          row,
          col,
          player: currentTurn
        })
      });
      if (resp.status !== 200) {
        const err = await resp.json();
        alert(err.detail || "Invalid move");
        setIsLoading(false);
        return;
      }
      const data = await resp.json();
      setBoard(data.board);
      setCurrentTurn(data.current_turn);
      setStatus(data.status);
      setWinner(data.winner);

      if (data.status && data.status !== 'in_progress') {
        // Update scores if applicable
        if (data.status === 'won' && data.winner) {
          setScores(prev => ({ ...prev, [data.winner]: prev[data.winner] + 1 }));
        } else if (data.status === 'draw') {
          setScores(prev => ({ ...prev, draws: prev.draws + 1 }));
        }
      }
    } catch (e) {
      alert("Error submitting move.");
    } finally {
      setIsLoading(false);
    }
  };

  // Fetch status (optional: poll for opponent move in two-player online mode in future)
  const fetchStatus = async () => {
    if (!gameId) return;
    try {
      const resp = await fetch(`${API_BASE}/game/${gameId}/status`);
      if (resp.status === 200) {
        const data = await resp.json();
        setBoard(data.board);
        setCurrentTurn(data.current_turn);
        setStatus(data.status);
        setWinner(data.winner);
      }
    } catch (e) {
      // Silently continue
    }
  };

  // Reset game board, keep same mode
  const resetGame = async () => {
    if (!gameId) return startNewGame();
    setIsLoading(true);
    try {
      const resp = await fetch(`${API_BASE}/game/${gameId}/reset`, { method: 'POST' });
      const data = await resp.json();
      setBoard(data.board);
      setCurrentTurn(data.current_turn);
      setStatus(data.status);
      setWinner(data.winner);
    } catch (e) {
      alert('Failed to reset game.');
    } finally {
      setIsLoading(false);
    }
  };

  // Handle mode change (cannot during active game)
  const handleModeChange = (newMode) => {
    if (gameId && status === 'in_progress') {
      // Prevent mid-game mode switch
      alert('Finish the current game or reset first.');
      return;
    }
    setMode(newMode);
    setScores({ X: 0, O: 0, draws: 0 });
    setPlayerStarts('X');
    startNewGame('X');
  };

  // On mount, start with default mode
  useEffect(() => {
    startNewGame(playerStarts);
    // eslint-disable-next-line
  }, []);

  // UI: select which player starts (in AI mode, allow for X or O starts)
  const showStartSelector = status !== 'in_progress';

  // UI Layout: always centered, responsive
  return (
    <div className="app">
      <nav className="navbar">
        <div className="container" style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
          <div className="logo">
            <span className="logo-symbol">*</span> Tic Tac Toe
          </div>
        </div>
      </nav>

      <main>
        <div className="container" style={{ paddingTop: 110, paddingBottom: 32 }}>
          <div className="ttt-ui-outer">
            <h1 className="title" style={{ marginBottom: 12 }}>Tic Tac Toe</h1>
            <div className="subtitle">Play vs a friend or AI</div>
            <StatusBar currentTurn={currentTurn} status={status} winner={winner} mode={mode} />
            <ScoreDisplay scores={scores} />
            <ModeSelector mode={mode} setMode={handleModeChange} inGame={!!gameId && status === 'in_progress'} />

            <div style={{ margin: '30px 0 10px 0' }}>
              {/* Player starter, only show if game is over or before 1st game */}
              {mode === 'ai' && showStartSelector && (
                <div className="ttt-player-selector">
                  Who starts?&nbsp;
                  <button
                    className={`btn btn-small${playerStarts === 'X' ? ' btn-selected' : ''}`}
                    onClick={() => setPlayerStarts('X')}
                  >You (X)</button>
                  <button
                    className={`btn btn-small${playerStarts === 'O' ? ' btn-selected' : ''}`}
                    onClick={() => setPlayerStarts('O')}
                  >AI (O)</button>
                  <button
                    className="btn btn-small"
                    onClick={() => startNewGame(playerStarts)}
                  >Start</button>
                </div>
              )}
            </div>

            {/* Board */}
            <Board
              board={board}
              onCellClick={(i, j) => {
                if (status !== 'in_progress') return;
                if (board[i][j] !== null) return;
                if (mode === 'ai' && currentTurn === 'O') return; // Prevent clicking when AI is thinking
                makeMove(i, j);
              }}
              disabled={isLoading || (mode === 'ai' && currentTurn === 'O') || status !== 'in_progress'}
            />

            {/* Controls */}
            <div className="ttt-controls">
              <button className="btn btn-large" onClick={resetGame} disabled={isLoading}>
                {status === 'in_progress' ? "Restart Game" : "New Game"}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

export default App;
