/* ═══════════════════════════════════════════════════
   METROPOLIS CHESS CLUB — Interactive Board Client
   ═══════════════════════════════════════════════════ */

const socket = io();

// ── Piece image map ──────────────────────────────────────────────────────────
const PIECE_IMG = {
    K:'/static/pieces/wK.svg', Q:'/static/pieces/wQ.svg',
    R:'/static/pieces/wR.svg', B:'/static/pieces/wB.svg',
    N:'/static/pieces/wN.svg', P:'/static/pieces/wP.svg',
    k:'/static/pieces/bK.svg', q:'/static/pieces/bQ.svg',
    r:'/static/pieces/bR.svg', b:'/static/pieces/bB.svg',
    n:'/static/pieces/bN.svg', p:'/static/pieces/bP.svg',
};

const FILES = 'abcdefgh';
const RANKS = '87654321';   // index 0 = rank 8 (top when unflipped)

// Piece sort order for captured pieces display (high value first)
const CAPTURED_ORDER_WHITE = ['Q','R','B','N','P'];
const CAPTURED_ORDER_BLACK = ['q','r','b','n','p'];
const STARTING_COUNTS = {K:1,Q:1,R:2,B:2,N:2,P:8,k:1,q:1,r:2,b:2,n:2,p:8};

// ── App state ────────────────────────────────────────────────────────────────
const G = {
    mode:             'vs_viktor',
    depth:            3,
    playerName:       '',
    player2Name:      'Black',
    fen:              null,
    legalMovesUci:    [],
    pieces:           {},
    selectedSq:       null,
    lastMove:         null,
    isCheck:          false,
    currentPlayerSide:'white',
    boardFlipped:     false,
    isPlayerTurn:     true,
    gameOver:         false,
    waitingMove:      false,
    startTime:        null,
    moveCount:        0,
    msgCount:         0,
};

// ── Drag state ───────────────────────────────────────────────────────────────
let potentialDrag = null;   // { sq, x, y } — awaiting threshold
let drag          = null;   // { sq, ghost } — dragging in progress

/* ════════════════════════════════════════
   SCREEN MANAGEMENT
════════════════════════════════════════ */
function showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    document.getElementById(id).classList.add('active');
    document.getElementById('mute-btn-global').classList.toggle('in-game', id === 'game-screen');
}

/* ════════════════════════════════════════
   SETUP SCREEN
════════════════════════════════════════ */
document.querySelectorAll('.mode-btn:not([disabled])').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.mode-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        G.mode = btn.dataset.mode;

        const isViktor = G.mode === 'vs_viktor';
        document.getElementById('difficulty-row').style.display = isViktor ? '' : 'none';

        const p2    = document.getElementById('player2-name');
        const p2lbl = document.getElementById('player2-label');
        if (G.mode === 'vs_human') {
            p2.style.display = p2lbl.style.display = '';
            document.getElementById('name-label').textContent = 'White player name';
            document.getElementById('player-name').placeholder = 'White';
            document.getElementById('viktor-quote').style.display = 'none';
        } else {
            p2.style.display = p2lbl.style.display = 'none';
            document.getElementById('name-label').textContent = 'Your name';
            document.getElementById('player-name').placeholder = 'Enter your name';
            document.getElementById('viktor-quote').style.display = '';
        }
    });
});

document.querySelectorAll('.diff-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.diff-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        G.depth = +btn.dataset.depth;
    });
});

/* ════════════════════════════════════════
   FEN PARSER
════════════════════════════════════════ */
function parseFen(fen) {
    const pieces = {};
    const rows = fen.split(' ')[0].split('/');
    for (let ri = 0; ri < 8; ri++) {
        let fi = 0;
        for (const ch of rows[ri]) {
            if (isNaN(ch)) { pieces[FILES[fi] + RANKS[ri]] = ch; fi++; }
            else fi += +ch;
        }
    }
    return pieces;
}

/* ════════════════════════════════════════
   BOARD RENDERING
════════════════════════════════════════ */
function renderBoard() {
    const boardEl = document.getElementById('chess-board');
    boardEl.innerHTML = '';

    // Always render from white's perspective. CSS rotateZ(180deg) on #chess-board
    // handles the visual flip for black — no DOM reordering needed.
    const flip = false;
    const checkKing = G.isCheck
        ? (G.currentPlayerSide === 'white' ? 'K' : 'k')
        : null;

    for (let ri = 0; ri < 8; ri++) {
        for (let fi = 0; fi < 8; fi++) {
            const actualRi = flip ? 7 - ri : ri;
            const actualFi = flip ? 7 - fi : fi;
            const sq      = FILES[actualFi] + RANKS[actualRi];
            const isLight = (actualFi + actualRi) % 2 === 0;
            const piece   = G.pieces[sq];

            const div = document.createElement('div');
            div.className = 'sq ' + (isLight ? 'light' : 'dark');
            div.dataset.sq = sq;

            if (G.lastMove && (sq === G.lastMove.from || sq === G.lastMove.to))
                div.classList.add('last-move');
            if (sq === G.selectedSq)
                div.classList.add('selected');
            if (checkKing && piece === checkKing)
                div.classList.add('in-check');

            if (G.selectedSq) {
                const legal = G.legalMovesUci.some(
                    m => m.startsWith(G.selectedSq) && m.slice(2,4) === sq
                );
                if (legal) div.classList.add(piece ? 'legal-cap' : 'legal-empty');
            }

            if (!G.gameOver && !G.waitingMove && isOwnPiece(piece))
                div.classList.add('own-piece');

            if (drag && drag.sq === sq)
                div.classList.add('drag-source');

            // Rank/file coord labels
            if (actualFi === 0) {
                const r = document.createElement('span');
                r.className = 'sq-coord rank';
                r.textContent = RANKS[actualRi];
                div.appendChild(r);
            }
            if (actualRi === 7) {
                const f = document.createElement('span');
                f.className = 'sq-coord file';
                f.textContent = FILES[actualFi];
                div.appendChild(f);
            }

            if (piece) {
                const img = document.createElement('img');
                img.className = 'piece';
                img.src = PIECE_IMG[piece];
                img.alt = piece;
                img.draggable = false;
                div.appendChild(img);
            }

            boardEl.appendChild(div);
        }
    }
}

/* ════════════════════════════════════════
   CAPTURED PIECES
════════════════════════════════════════ */
function computeCaptured(pieces) {
    const current = {};
    for (const p of Object.values(pieces)) current[p] = (current[p] || 0) + 1;
    const captured = {};
    for (const [p, count] of Object.entries(STARTING_COUNTS)) {
        if (p === 'K' || p === 'k') continue;
        const diff = count - (current[p] || 0);
        if (diff > 0) captured[p] = diff;
    }
    return captured;
}

function updateCapturedDisplay() {
    const captured = computeCaptured(G.pieces);

    // Top bar shows white pieces captured (taken by black/Viktor)
    const topEl = document.getElementById('top-captured');
    const botEl = document.getElementById('bottom-captured');
    if (!topEl || !botEl) return;

    function renderCaptures(el, order) {
        el.innerHTML = '';
        for (const p of order) {
            const count = captured[p] || 0;
            for (let i = 0; i < count; i++) {
                const img = document.createElement('img');
                img.className = 'captured-piece';
                img.src = PIECE_IMG[p];
                img.alt = p;
                el.appendChild(img);
            }
        }
    }

    renderCaptures(topEl, CAPTURED_ORDER_WHITE);   // white pieces lost (black captured them)
    renderCaptures(botEl, CAPTURED_ORDER_BLACK);   // black pieces lost (white captured them)
}

/* ════════════════════════════════════════
   MOVE FLASH
════════════════════════════════════════ */
function flashSquare(sq) {
    const el = document.querySelector(`.sq[data-sq="${sq}"]`);
    if (!el) return;
    const overlay = document.createElement('div');
    overlay.className = 'flash-overlay';
    el.appendChild(overlay);
    overlay.addEventListener('animationend', () => overlay.remove());
}

function flashMove(from, to) {
    flashSquare(from);
    flashSquare(to);
}

function isOwnPiece(piece) {
    if (!piece) return false;
    if (G.mode === 'vs_human')
        return G.currentPlayerSide === 'white'
            ? piece === piece.toUpperCase()
            : piece === piece.toLowerCase();
    return piece === piece.toUpperCase(); // player is always white vs Viktor
}

function updateBoard(boardData, animateTo = null) {
    G.fen           = boardData.fen;
    G.legalMovesUci = boardData.legal_moves_uci || [];
    G.isCheck       = boardData.is_check || false;
    G.moveCount     = boardData.move_count || 0;
    G.pieces        = parseFen(G.fen);

    G.currentPlayerSide = G.fen.split(' ')[1] === 'w' ? 'white' : 'black';

    if (G.mode === 'vs_human') {
        G.boardFlipped = G.currentPlayerSide === 'black';
        // Defer the class toggle one frame so renderBoard() finishes first.
        // The transition then fires on already-existing elements, not fresh ones,
        // preventing flicker on re-renders during black's turn.
        const _bf = G.boardFlipped;
        requestAnimationFrame(() =>
            document.getElementById('chess-board').classList.toggle('board-black-turn', _bf)
        );
    }

    if (boardData.last_move)
        G.lastMove = { from: boardData.last_move.slice(0,2), to: boardData.last_move.slice(2,4) };

    if (G.mode === 'vs_viktor')
        G.isPlayerTurn = G.currentPlayerSide === 'white';

    renderBoard();
    updateCapturedDisplay();
    if (animateTo) {
        const pieceEl = document.querySelector(`.sq[data-sq="${animateTo}"] .piece`);
        if (pieceEl) { pieceEl.classList.remove('land'); void pieceEl.offsetWidth; pieceEl.classList.add('land'); }
    }

    updateStatus(boardData);
    updatePlayerBars(boardData);
    updateMoveLog(boardData.move_history_san || []);
    document.getElementById('move-counter').textContent = `Move ${G.moveCount}`;
    document.getElementById('stat-moves').textContent   = G.moveCount;
    document.getElementById('phase-badge').textContent  =
        boardData.phase ? capitalize(boardData.phase) : 'Opening';
}

function updateStatus(boardData) {
    const turnEl  = document.getElementById('turn-status');
    const checkEl = document.getElementById('check-badge');

    if (boardData.is_checkmate) {
        turnEl.textContent = 'Checkmate';
        checkEl.textContent = 'CHECKMATE';
        checkEl.className = 'check-badge is-checkmate';
        checkEl.style.display = '';
    } else if (boardData.is_stalemate) {
        turnEl.textContent = 'Stalemate — Draw'; checkEl.style.display = 'none';
    } else if (boardData.is_check) {
        turnEl.textContent = `${capitalize(G.currentPlayerSide)} · CHECK!`;
        checkEl.textContent = 'CHECK';
        checkEl.className = 'check-badge';
        checkEl.style.display = '';
        Audio.playCheck();
    } else {
        checkEl.style.display = 'none';
        checkEl.className = 'check-badge';
        if (G.waitingMove) {
            turnEl.textContent = G.mode === 'vs_viktor' ? 'Viktor is thinking...' : 'Processing...';
        } else if (G.mode === 'vs_human') {
            const name = G.currentPlayerSide === 'white' ? G.playerName : G.player2Name;
            turnEl.textContent = `${name}'s turn`;
        } else {
            turnEl.textContent = G.isPlayerTurn ? 'White · Your turn' : 'Black · Viktor';
        }
    }
}

function updatePlayerBars(boardData) {
    if (G.mode !== 'vs_human') return;
    const top    = document.getElementById('top-name');
    const bottom = document.getElementById('bottom-name');
    const topSub = document.getElementById('top-sub');
    if (!G.boardFlipped) {
        top.textContent = G.player2Name; bottom.textContent = G.playerName; topSub.textContent = 'Black';
    } else {
        top.textContent = G.playerName; bottom.textContent = G.player2Name; topSub.textContent = 'White';
    }
}

function updateMoveLog(sanMoves) {
    const log = document.getElementById('move-log');
    log.innerHTML = '';
    const recent = 4;
    sanMoves.forEach((mv, i) => {
        const pill = document.createElement('span');
        pill.className = 'mpill' + (i >= sanMoves.length - recent ? ' recent' : '');
        const moveNum = Math.floor(i / 2) + 1;
        const prefix  = i % 2 === 0 ? `${moveNum}.` : '';
        pill.textContent = prefix ? `${prefix}${mv}` : mv;
        log.appendChild(pill);
    });
    log.scrollLeft = log.scrollWidth;
}

/* ════════════════════════════════════════
   SQUARE HIT-DETECTION
   Uses elementFromPoint so hit boxes match what the user actually sees,
   even with perspective/rotateX applied to the board.
   Piece images have pointer-events:none so they're transparent to this.
════════════════════════════════════════ */
function squareAtPoint(clientX, clientY) {
    const el = document.elementFromPoint(clientX, clientY);
    if (el) {
        const sqEl = el.closest('.sq[data-sq]');
        if (sqEl) return sqEl.dataset.sq;
    }
    // Fallback: linear bounding-rect mapping (handles edge/border area)
    const boardEl = document.getElementById('chess-board');
    if (!boardEl) return null;
    const rect = boardEl.getBoundingClientRect();
    const x = (clientX - rect.left)  / rect.width;
    const y = (clientY - rect.top)   / rect.height;
    if (x < 0 || x > 1 || y < 0 || y > 1) return null;
    const fi = Math.min(7, Math.floor(x * 8));
    const ri = Math.min(7, Math.floor(y * 8));
    const actualFi = G.boardFlipped ? 7 - fi : fi;
    const actualRi = G.boardFlipped ? 7 - ri : ri;
    return FILES[actualFi] + RANKS[actualRi];
}

/* ════════════════════════════════════════
   DRAG-AND-DROP
════════════════════════════════════════ */
function startDrag(sq, clientX, clientY) {
    const piece = G.pieces[sq];
    if (!piece) return;
    G.selectedSq = sq;

    const ghost = document.createElement('img');
    ghost.src = PIECE_IMG[piece];
    ghost.className = 'piece-ghost';
    ghost.style.left = clientX + 'px';
    ghost.style.top  = clientY + 'px';
    document.body.appendChild(ghost);

    drag = { sq, ghost };
    renderBoard();
}

function moveDrag(clientX, clientY) {
    if (!drag) return;
    drag.ghost.style.left = clientX + 'px';
    drag.ghost.style.top  = clientY + 'px';
}

function endDrag(clientX, clientY) {
    if (!drag) return;

    const targetSq = squareAtPoint(clientX, clientY);
    drag.ghost.remove();
    const sourceSq = drag.sq;
    drag = null;

    if (targetSq && targetSq !== sourceSq) {
        const prefix  = sourceSq + targetSq;
        const matches = G.legalMovesUci.filter(m => m.startsWith(prefix.slice(0,4)));
        if (matches.length > 0) {
            G.selectedSq = null;
            if (isPromotionMove(sourceSq, targetSq)) {
                showPromoDialog(sourceSq, targetSq, moveUci => executeMove(moveUci));
            } else {
                const move = matches.find(m => m.length === 4) || matches[0];
                executeMove(move);
            }
            return;
        }
    }

    G.selectedSq = null;
    renderBoard();
}

// ── Mouse event wiring ──────────────────────────────────────────────────────

document.getElementById('chess-board').addEventListener('mousedown', e => {
    if (e.button !== 0 || G.gameOver || G.waitingMove) return;
    const sq = squareAtPoint(e.clientX, e.clientY);
    if (!sq) return;
    const piece = G.pieces[sq];

    if (isOwnPiece(piece)) {
        potentialDrag = { sq, x: e.clientX, y: e.clientY };
        e.preventDefault();
    }
});

document.getElementById('chess-board').addEventListener('touchstart', e => {
    if (G.gameOver || G.waitingMove) return;
    const t  = e.touches[0];
    const sq = squareAtPoint(t.clientX, t.clientY);
    if (!sq) return;
    const piece = G.pieces[sq];
    if (isOwnPiece(piece)) {
        potentialDrag = { sq, x: t.clientX, y: t.clientY };
        e.preventDefault();
    }
}, { passive: false });

window.addEventListener('mousemove', e => {
    if (potentialDrag && !drag) {
        const dx = e.clientX - potentialDrag.x;
        const dy = e.clientY - potentialDrag.y;
        if (dx * dx + dy * dy > 25) { // 5px threshold
            startDrag(potentialDrag.sq, e.clientX, e.clientY);
            potentialDrag = null;
        }
        return;
    }
    moveDrag(e.clientX, e.clientY);
});

window.addEventListener('touchmove', e => {
    const t = e.touches[0];
    if (potentialDrag && !drag) {
        const dx = t.clientX - potentialDrag.x;
        const dy = t.clientY - potentialDrag.y;
        if (dx * dx + dy * dy > 25) {
            startDrag(potentialDrag.sq, t.clientX, t.clientY);
            potentialDrag = null;
        }
        return;
    }
    if (drag) { moveDrag(t.clientX, t.clientY); e.preventDefault(); }
}, { passive: false });

window.addEventListener('mouseup', e => {
    if (potentialDrag && !drag) {
        // Never became a drag — treat as a click
        handleClick(potentialDrag.sq);
        potentialDrag = null;
        return;
    }
    if (drag) endDrag(e.clientX, e.clientY);
});

window.addEventListener('touchend', e => {
    const t = e.changedTouches[0];
    if (potentialDrag && !drag) {
        handleClick(potentialDrag.sq);
        potentialDrag = null;
        return;
    }
    if (drag) endDrag(t.clientX, t.clientY);
});

// Click-to-select / click-to-move (shared between 2D and 3D modes)
function handleClick(sq) {
    if (G.gameOver || G.waitingMove) return;
    const piece = G.pieces[sq];

    if (G.selectedSq) {
        const prefix  = G.selectedSq + sq;
        const matches = G.legalMovesUci.filter(m => m.startsWith(prefix.slice(0,4)));
        if (matches.length > 0) {
            const fromSq = G.selectedSq;
            G.selectedSq = null;
            if (isPromotionMove(fromSq, sq)) {
                showPromoDialog(fromSq, sq, moveUci => executeMove(moveUci));
            } else {
                const move = matches.find(m => m.length === 4) || matches[0];
                executeMove(move);
            }
        } else if (isOwnPiece(piece)) {
            G.selectedSq = sq; renderBoard();
        } else {
            G.selectedSq = null; renderBoard();
        }
    } else if (isOwnPiece(piece)) {
        G.selectedSq = sq; renderBoard();
    }
}

/* ════════════════════════════════════════
   PROMOTION DIALOG
════════════════════════════════════════ */
function isPromotionMove(fromSq, toSq) {
    const piece = G.pieces[fromSq];
    if (!piece) return false;
    if (piece === 'P' && toSq[1] === '8') return true;
    if (piece === 'p' && toSq[1] === '1') return true;
    return false;
}

function showPromoDialog(fromSq, toSq, callback) {
    const overlay = document.getElementById('promo-overlay');
    const choices = document.getElementById('promo-choices');
    if (!overlay || !choices) { callback(fromSq + toSq + 'q'); return; }

    const isWhite = G.pieces[fromSq] === 'P';
    const pieces = isWhite
        ? [['q','Q'],['r','R'],['b','B'],['n','N']]
        : [['q','q'],['r','r'],['b','b'],['n','n']];
    const imgPrefix = isWhite ? 'w' : 'b';

    choices.innerHTML = '';
    for (const [letter, label] of pieces) {
        const btn = document.createElement('button');
        btn.className = 'promo-btn';
        btn.dataset.piece = letter;
        const img = document.createElement('img');
        img.src = PIECE_IMG[isWhite ? label : label.toLowerCase()];
        img.alt = label;
        btn.appendChild(img);
        btn.addEventListener('click', () => {
            overlay.style.display = 'none';
            callback(fromSq + toSq + letter);
        });
        choices.appendChild(btn);
    }

    overlay.style.display = 'flex';
}

function executeMove(moveUci) {
    G.waitingMove = true;
    G.selectedSq  = null;

    // Fade the board hint after first player move
    const hint = document.getElementById('board-hint');
    if (hint && hint.style.opacity !== '0') {
        hint.style.transition = 'opacity 0.6s ease';
        hint.style.opacity = '0';
    }

    const from = moveUci.slice(0,2);
    const to   = moveUci.slice(2,4);
    const isCapture = !!G.pieces[to];
    G.pieces[to]   = G.pieces[from];
    delete G.pieces[from];
    G.lastMove     = { from, to };
    if (G.mode === 'vs_viktor') G.isPlayerTurn = false;

    renderBoard();
    updateCapturedDisplay();
    flashMove(from, to);
    isCapture ? Audio.playCapture() : Audio.playMove();
    updateStatus({ is_check: false });
    if (G.mode === 'vs_viktor') showThinking();

    socket.emit('make_move', { move: moveUci });
}

/* ════════════════════════════════════════
   CHAT
════════════════════════════════════════ */
function addMessage(role, content, tone = null, thinking = null, meta = {}) {
    const box = document.getElementById('chat-messages');
    const msg = document.createElement('div');
    const toneClass = tone ? ` tone-${tone}` : '';
    msg.className = `cmsg ${role}${toneClass}`;

    // Memory surfaced pill — shows before the bubble, very subtle
    if (role === 'agent' && meta.memories_surfaced > 0) {
        const pill = document.createElement('div');
        pill.className = 'cmsg-memory-pill';
        pill.textContent = meta.memories_surfaced === 1
            ? '· memory surfaced'
            : `· ${meta.memories_surfaced} memories surfaced`;
        msg.appendChild(pill);
    }

    const bubble = document.createElement('div');
    bubble.className = 'cmsg-bubble';
    bubble.textContent = content;
    msg.appendChild(bubble);

    if (tone) {
        const t = document.createElement('div');
        t.className = 'cmsg-tone';
        t.textContent = '· ' + tone;
        msg.appendChild(t);
    }

    if (thinking && role === 'agent') {
        const toggle = document.createElement('div');
        toggle.className = 'cmsg-thinking-toggle';
        toggle.textContent = '› show thinking';
        const think = document.createElement('div');
        think.className = 'cmsg-thinking';
        think.textContent = thinking;
        toggle.addEventListener('click', () => {
            const v = think.classList.toggle('visible');
            toggle.textContent = v ? '› hide thinking' : '› show thinking';
        });
        msg.appendChild(toggle);
        msg.appendChild(think);
    }

    box.appendChild(msg);

    // If Viktor saved a memory, add a small system note below
    if (role === 'agent' && meta.memory_saved) {
        const note = document.createElement('div');
        note.className = 'cmsg system';
        note.innerHTML = '<div class="cmsg-bubble cmsg-memory-note">· memory noted</div>';
        box.appendChild(note);
    }

    box.scrollTop = box.scrollHeight;
    G.msgCount++;
    document.getElementById('stat-messages').textContent = G.msgCount;
}

function addSystemMsg(text) {
    const box    = document.getElementById('chat-messages');
    const el     = document.createElement('div');
    el.className = 'cmsg system';
    const bubble = document.createElement('div');
    bubble.className = 'cmsg-bubble';
    bubble.textContent = text;
    el.appendChild(bubble);
    box.appendChild(el);
    box.scrollTop = box.scrollHeight;
}

function showThinking() {
    removeThinking();
    const box = document.getElementById('chat-messages');
    const el  = document.createElement('div');
    el.className  = 'thinking-row';
    el.id         = 'thinking-indicator';
    el.innerHTML  = `<div class="dots"><span></span><span></span><span></span></div>
                     <span class="thinking-lbl">Viktor is thinking...</span>`;
    box.appendChild(el);
    box.scrollTop = box.scrollHeight;
}

function removeThinking() {
    document.getElementById('thinking-indicator')?.remove();
}

/* ════════════════════════════════════════
   TIMER
════════════════════════════════════════ */
G._timerInterval = setInterval(() => {
    if (!G.startTime || G.gameOver) return;
    const s = Math.floor((Date.now() - G.startTime) / 1000);
    document.getElementById('stat-duration').textContent =
        `${Math.floor(s/60)}:${String(s%60).padStart(2,'0')}`;
}, 1000);

/* ════════════════════════════════════════
   SOCKET EVENTS
════════════════════════════════════════ */
socket.on('connect', () => console.log('[MCC] connected'));

socket.on('game_started', data => {
    G.startTime    = Date.now();
    G.playerName   = data.player_name;
    G.player2Name  = data.player2_name || 'Black';
    G.mode         = data.mode || 'vs_viktor';
    G.boardFlipped = false;

    document.getElementById('bottom-name').textContent = G.playerName;
    document.getElementById('stat-duration').textContent = '0:00';

    const viktorAvatar = document.getElementById('viktor-avatar');

    if (G.mode === 'vs_human') {
        document.getElementById('top-name').textContent    = G.player2Name;
        document.getElementById('top-sub').textContent     = 'Black';
        document.getElementById('chat-hdr-title').textContent = 'Local Game';
        document.getElementById('chat-input-row').style.display = 'none';
        if (viktorAvatar) viktorAvatar.style.display = 'none';
        addSystemMsg(`${G.playerName} (White) vs ${G.player2Name} (Black)`);
        addSystemMsg("White's turn");
    } else {
        document.getElementById('top-name').textContent    = 'Viktor Petrov';
        document.getElementById('top-sub').textContent     = 'Chess Master · Minsk';
        document.getElementById('chat-hdr-title').textContent = 'Metropolis Chess Club';
        if (viktorAvatar) viktorAvatar.style.display = '';
    }

    updateBoard(data.board);
    Audio.dimAmbient();
    Audio.playGameStart();
    if (data.message)
        addMessage('agent', data.message.content, data.message.tone, data.message.thinking, data.message);
    showScreen('game-screen');
});

socket.on('move_made', data => {
    removeThinking();
    G.waitingMove = false;

    // Capture Viktor's move info before the board update wipes the DOM
    let viktorFrom = null, viktorTo = null, viktorIsCapture = false;
    if (data.board?.last_move && G.mode === 'vs_viktor') {
        viktorFrom = data.board.last_move.slice(0,2);
        viktorTo   = data.board.last_move.slice(2,4);
        const lastSan = (data.board.move_history_san || []).slice(-1)[0] || '';
        viktorIsCapture = lastSan.includes('x');
    }

    // vs_human: skip animateTo — the land animation conflicts with piece counter-rotation.
    // vs_viktor: pass animateTo for the landing piece bounce.
    updateBoard(data.board, G.mode !== 'vs_human' ? data.board?.last_move?.slice(2,4) : null);

    if (viktorFrom) {
        flashMove(viktorFrom, viktorTo);
        viktorIsCapture ? Audio.playCapture() : Audio.playMove();
    }

    if (G.mode === 'vs_human') {
        const mover = G.currentPlayerSide === 'white' ? G.playerName : G.player2Name;
        addSystemMsg(`${mover}'s turn`);
    }

    if (data.player_message?.content)
        addMessage('agent', data.player_message.content, data.player_message.tone, data.player_message.thinking, data.player_message);
    if (data.game_over) {
        if (data.agent_message?.content)
            addMessage('agent', data.agent_message.content, data.agent_message.tone, data.agent_message.thinking, data.agent_message);
        endGame(data.result);
    }
});

socket.on('game_over', data => {
    removeThinking(); G.waitingMove = false;
    updateBoard(data.board);
    if (data.player_message?.content)
        addMessage('agent', data.player_message.content, data.player_message.tone, data.player_message.thinking, data.player_message);
    if (data.agent_message?.content)
        addMessage('agent', data.agent_message.content, data.agent_message.tone, data.agent_message.thinking, data.agent_message);
    endGame(data.result);
});

socket.on('move_error', data => {
    removeThinking(); G.waitingMove = false; G.isPlayerTurn = true;
    renderBoard();
    if (G.mode === 'vs_viktor') addMessage('agent', `Illegal move: ${data.error}`);
});

socket.on('message_sent', data => {
    removeThinking();
    if (data.agent_message?.content)
        addMessage('agent', data.agent_message.content, data.agent_message.tone, data.agent_message.thinking, data.agent_message);
});

socket.on('idle_message', data => {
    if (data.agent_message?.content)
        addMessage('agent', data.agent_message.content, data.agent_message.tone, data.agent_message.thinking, data.agent_message);
});

socket.on('error', data => {
    console.error('[MCC]', data);
    removeThinking();
    addMessage('agent', `Error: ${data.message}`);
});

/* ════════════════════════════════════════
   GAME OVER
════════════════════════════════════════ */
function endGame(result) {
    G.gameOver = true; G.waitingMove = false;
    clearInterval(G._timerInterval);
    renderBoard();

    let icon = '♟', text = 'Game Over', outcome = 'draw';
    if (result === '1-0') {
        icon = '♔'; outcome = 'win';
        text = G.mode === 'vs_viktor' ? 'You Win' : `${G.playerName} Wins`;
    } else if (result === '0-1') {
        icon = '♚'; outcome = G.mode === 'vs_viktor' ? 'lose' : 'win';
        text = G.mode === 'vs_viktor' ? 'Viktor Wins' : `${G.player2Name} Wins`;
    } else if (result === '1/2-1/2') {
        icon = '½'; text = 'Draw';
    }

    Audio.playGameOver(outcome);

    // Show inline result banner — stays on the game screen
    const banner = document.getElementById('result-banner');
    if (banner) {
        document.getElementById('result-banner-icon').textContent = icon;
        document.getElementById('result-banner-text').textContent = text;
        banner.dataset.outcome = outcome;
        banner.style.display = '';
    }

    // Hide resign button, hide chat input
    document.getElementById('resign-btn').style.display = 'none';
    document.getElementById('chat-input-row').style.display = 'none';
}

/* ════════════════════════════════════════
   UI BINDINGS
════════════════════════════════════════ */
document.getElementById('start-btn').addEventListener('click', () => {
    const name  = document.getElementById('player-name').value.trim()  || (G.mode === 'vs_human' ? 'White' : 'Player');
    const name2 = document.getElementById('player2-name').value.trim() || 'Black';
    G.playerName = name; G.player2Name = name2;
    socket.emit('start_game', { player_name: name, player2_name: name2, mode: G.mode, depth: G.depth });
});

document.getElementById('player-name').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('start-btn').click();
});

document.getElementById('send-btn').addEventListener('click', () => {
    const input = document.getElementById('message-input');
    const text  = input.value.trim();
    if (!text) return;
    addMessage('player', text);
    socket.emit('send_message', { message: text });
    input.value = '';
    if (G.mode === 'vs_viktor') showThinking();
});

document.getElementById('message-input').addEventListener('keydown', e => {
    if (e.key === 'Enter') document.getElementById('send-btn').click();
});

document.getElementById('resign-btn').addEventListener('click', () => {
    if (G.gameOver) return;
    if (!confirm('Resign this game?')) return;
    socket.emit('resign');
});

document.getElementById('play-again-inline').addEventListener('click', () => location.reload());

document.getElementById('mute-btn-global').addEventListener('click', () => {
    const muted = Audio.toggleMute();
    const btn = document.getElementById('mute-btn-global');
    btn.textContent = muted ? '♪̶' : '♪';
    btn.classList.toggle('muted', muted);
});

/* ════════════════════════════════════════
   ISOMETRIC PARALLAX
   Mouse movement gently shifts the perspective-origin — creates the
   illusion of looking at a real 3D object from slightly different angles.
   No rotation; just a subtle depth cue.
════════════════════════════════════════ */
(function setupParallax() {
    const scene = document.getElementById('board-scene');
    if (!scene) return;

    const BASE_OX = 50, BASE_OY = -10;   // default perspective-origin
    const SWAY_X  =  6, SWAY_Y  =  4;   // max shift in %

    let cx = BASE_OX, cy = BASE_OY;      // current (lerped)
    let tx = BASE_OX, ty = BASE_OY;      // target

    function tick() {
        cx += (tx - cx) * 0.07;
        cy += (ty - cy) * 0.07;
        scene.style.perspectiveOrigin = `${cx.toFixed(2)}% ${cy.toFixed(2)}%`;
        requestAnimationFrame(tick);
    }

    document.addEventListener('mousemove', e => {
        const nx = e.clientX / window.innerWidth;
        const ny = e.clientY / window.innerHeight;
        tx = BASE_OX + (nx - 0.5) * SWAY_X * 2;
        ty = BASE_OY + (ny - 0.5) * SWAY_Y * 2;
    });

    document.addEventListener('mouseleave', () => { tx = BASE_OX; ty = BASE_OY; });

    requestAnimationFrame(tick);
})();

/* ════════════════════════════════════════
   UTILS
════════════════════════════════════════ */
function capitalize(s) { return s ? s[0].toUpperCase() + s.slice(1) : ''; }

showScreen('setup-screen');

// Attempt ambient immediately — Howler's autoUnlock will play it on the
// first user gesture (click, key, touch) without us needing to wait.
Audio.startAmbient(true);
