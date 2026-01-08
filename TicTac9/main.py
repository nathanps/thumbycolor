import engine_main
import engine
import engine_draw
import engine_io
from engine_nodes import Rectangle2DNode, Text2DNode, CameraNode, Circle2DNode
from engine_math import Vector2

# === Constants ===
EMPTY = 0
PLAYER_X = 1
PLAYER_O = 2

BOARD_ACTIVE = 0
BOARD_WON_X = 1
BOARD_WON_O = 2
BOARD_TIED = 3

STATE_PLAYING = 0
STATE_GAME_OVER = 1

WIN_PATTERNS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
    (0, 4, 8), (2, 4, 6)              # Diagonals
]

# Layout constants (camera centered at 0,0)
GRID_START_X = -57
GRID_START_Y = -49
BOARD_SIZE = 38
BOARD_GAP = 2
CELL_SIZE = 12

# === Game State ===
cells = [EMPTY] * 81
board_states = [BOARD_ACTIVE] * 9
current_player = PLAYER_X
required_board = -1
cursor_board = 4
cursor_cell = 4
game_state = STATE_PLAYING
game_winner = EMPTY
input_cooldown = 0

# === Camera ===
camera = CameraNode()

# === Helper Functions ===
def get_board_pos(board_idx):
    """Get top-left pixel position of a board"""
    bx = board_idx % 3
    by = board_idx // 3
    px = GRID_START_X + bx * (BOARD_SIZE + BOARD_GAP)
    py = GRID_START_Y + by * (BOARD_SIZE + BOARD_GAP)
    return px, py

def get_cell_pos(board_idx, cell_idx):
    """Get center pixel position of a cell"""
    bpx, bpy = get_board_pos(board_idx)
    cx = cell_idx % 3
    cy = cell_idx // 3
    px = bpx + cx * CELL_SIZE + CELL_SIZE // 2 + 1
    py = bpy + cy * CELL_SIZE + CELL_SIZE // 2 + 1
    return px, py

# === Create Visual Elements ===

# Turn indicator
turn_text = Text2DNode()
turn_text.position = Vector2(-25, -60)
turn_text.color = engine_draw.red
turn_text.text = "X's Turn"

# Board backgrounds
board_bgs = []
for i in range(9):
    px, py = get_board_pos(i)
    bg = Rectangle2DNode()
    bg.position = Vector2(px + BOARD_SIZE // 2, py + BOARD_SIZE // 2)
    bg.width = BOARD_SIZE - 2
    bg.height = BOARD_SIZE - 2
    bg.color = engine_draw.darkgrey
    bg.layer = 0
    board_bgs.append(bg)

# Grid lines for each board
grid_lines = []
for board_idx in range(9):
    bpx, bpy = get_board_pos(board_idx)
    # 2 vertical lines
    for j in range(2):
        line = Rectangle2DNode()
        line.width = 1
        line.height = BOARD_SIZE - 4
        line.position = Vector2(bpx + CELL_SIZE * (j + 1) + 1, bpy + BOARD_SIZE // 2)
        line.color = engine_draw.lightgrey
        line.layer = 1
        grid_lines.append(line)
    # 2 horizontal lines
    for j in range(2):
        line = Rectangle2DNode()
        line.width = BOARD_SIZE - 4
        line.height = 1
        line.position = Vector2(bpx + BOARD_SIZE // 2, bpy + CELL_SIZE * (j + 1) + 1)
        line.color = engine_draw.lightgrey
        line.layer = 1
        grid_lines.append(line)

# Active board highlight (yellow border)
highlight = Rectangle2DNode()
highlight.width = BOARD_SIZE + 2
highlight.height = BOARD_SIZE + 2
highlight.color = engine_draw.yellow
highlight.layer = 2
highlight.opacity = 0

# Highlight inner (to create border effect)
highlight_inner = Rectangle2DNode()
highlight_inner.width = BOARD_SIZE - 2
highlight_inner.height = BOARD_SIZE - 2
highlight_inner.color = engine_draw.darkgrey
highlight_inner.layer = 3
highlight_inner.opacity = 0

# Cursor
cursor = Rectangle2DNode()
cursor.width = CELL_SIZE
cursor.height = CELL_SIZE
cursor.color = engine_draw.red
cursor.layer = 5

# Cursor inner (to create outline effect)
cursor_inner = Rectangle2DNode()
cursor_inner.width = CELL_SIZE - 4
cursor_inner.height = CELL_SIZE - 4
cursor_inner.color = engine_draw.darkgrey
cursor_inner.layer = 6

# Board win overlays (big X or O shown when board is won)
board_win_texts = []
for i in range(9):
    px, py = get_board_pos(i)
    txt = Text2DNode()
    txt.position = Vector2(px + BOARD_SIZE // 2 - 6, py + BOARD_SIZE // 2 - 6)
    txt.scale = Vector2(2, 2)
    txt.color = engine_draw.white
    txt.text = ""
    txt.layer = 8
    txt.opacity = 0
    board_win_texts.append(txt)

# Game over text
game_over_text = Text2DNode()
game_over_text.position = Vector2(-20, -10)
game_over_text.color = engine_draw.gold
game_over_text.scale = Vector2(2, 2)
game_over_text.text = ""
game_over_text.layer = 10
game_over_text.opacity = 0

restart_text = Text2DNode()
restart_text.position = Vector2(-30, 10)
restart_text.color = engine_draw.white
restart_text.text = "Press A"
restart_text.layer = 10
restart_text.opacity = 0

# X and O mark storage
x_marks = []  # List of (rect1, rect2) for X marks
o_marks = []  # List of Circle2DNode for O marks

# === Game Functions ===
def create_x_mark(px, py):
    """Create an X mark at screen position"""
    r1 = Rectangle2DNode()
    r1.width = 10
    r1.height = 2
    r1.color = engine_draw.red
    r1.position = Vector2(px, py)
    r1.rotation = 0.785  # 45 degrees
    r1.layer = 4

    r2 = Rectangle2DNode()
    r2.width = 10
    r2.height = 2
    r2.color = engine_draw.red
    r2.position = Vector2(px, py)
    r2.rotation = -0.785  # -45 degrees
    r2.layer = 4

    x_marks.append((r1, r2))

def create_o_mark(px, py):
    """Create an O mark at screen position"""
    # Outer circle
    c_outer = Circle2DNode()
    c_outer.radius = 5
    c_outer.color = engine_draw.blue
    c_outer.position = Vector2(px, py)
    c_outer.layer = 4

    # Inner circle (to create ring effect)
    c_inner = Circle2DNode()
    c_inner.radius = 3
    c_inner.color = engine_draw.darkgrey
    c_inner.position = Vector2(px, py)
    c_inner.layer = 4

    o_marks.append((c_outer, c_inner))

def init_game():
    """Reset all game state for new game"""
    global cells, board_states, current_player, required_board
    global cursor_board, cursor_cell, game_state, game_winner

    cells = [EMPTY] * 81
    board_states = [BOARD_ACTIVE] * 9
    current_player = PLAYER_X
    required_board = -1
    cursor_board = 4
    cursor_cell = 4
    game_state = STATE_PLAYING
    game_winner = EMPTY

    # Hide game over UI
    game_over_text.opacity = 0
    restart_text.opacity = 0

    # Reset board backgrounds
    for bg in board_bgs:
        bg.color = engine_draw.darkgrey

    # Hide board win texts
    for txt in board_win_texts:
        txt.opacity = 0
        txt.text = ""

    # Remove all marks
    for r1, r2 in x_marks:
        r1.opacity = 0
        r2.opacity = 0
    for c_outer, c_inner in o_marks:
        c_outer.opacity = 0
        c_inner.opacity = 0
    x_marks.clear()
    o_marks.clear()

    update_cursor()
    update_highlight()
    update_turn_text()

def is_valid_move(board_idx, cell_idx):
    """Check if a move is allowed"""
    if game_state != STATE_PLAYING:
        return False
    if required_board != -1 and board_idx != required_board:
        return False
    if board_states[board_idx] != BOARD_ACTIVE:
        return False
    cell_global = board_idx * 9 + cell_idx
    if cells[cell_global] != EMPTY:
        return False
    return True

def check_board_win(board_idx):
    """Check if a specific board has been won or tied"""
    global board_states

    base = board_idx * 9

    for pattern in WIN_PATTERNS:
        a, b, c = pattern
        if cells[base + a] != EMPTY and \
           cells[base + a] == cells[base + b] == cells[base + c]:
            if cells[base + a] == PLAYER_X:
                board_states[board_idx] = BOARD_WON_X
                board_bgs[board_idx].color = engine_draw.red
                board_win_texts[board_idx].text = "X"
                board_win_texts[board_idx].color = engine_draw.white
                board_win_texts[board_idx].opacity = 1
            else:
                board_states[board_idx] = BOARD_WON_O
                board_bgs[board_idx].color = engine_draw.blue
                board_win_texts[board_idx].text = "O"
                board_win_texts[board_idx].color = engine_draw.white
                board_win_texts[board_idx].opacity = 1
            return

    # Check for tie (all cells filled)
    all_filled = all(cells[base + i] != EMPTY for i in range(9))
    if all_filled:
        board_states[board_idx] = BOARD_TIED
        board_bgs[board_idx].color = engine_draw.lightgrey
        board_win_texts[board_idx].text = "T"
        board_win_texts[board_idx].color = engine_draw.darkgrey
        board_win_texts[board_idx].opacity = 1

def check_game_win():
    """Check if the overall game has been won (tied boards count for both)"""
    global game_state, game_winner

    for pattern in WIN_PATTERNS:
        a, b, c = pattern
        states = [board_states[a], board_states[b], board_states[c]]

        # X wins if all three are X or TIED, with at least one real X
        x_valid = [s in [BOARD_WON_X, BOARD_TIED] for s in states]
        x_real = [s == BOARD_WON_X for s in states]
        if all(x_valid) and any(x_real):
            game_state = STATE_GAME_OVER
            game_winner = PLAYER_X
            show_game_over()
            return

        # O wins if all three are O or TIED, with at least one real O
        o_valid = [s in [BOARD_WON_O, BOARD_TIED] for s in states]
        o_real = [s == BOARD_WON_O for s in states]
        if all(o_valid) and any(o_real):
            game_state = STATE_GAME_OVER
            game_winner = PLAYER_O
            show_game_over()
            return

    # Check for overall tie (all boards decided, no winner)
    all_decided = all(s != BOARD_ACTIVE for s in board_states)
    if all_decided:
        game_state = STATE_GAME_OVER
        game_winner = EMPTY
        show_game_over()

def make_move(board_idx, cell_idx):
    """Execute a move and update game state"""
    global current_player, required_board, cursor_board

    cell_global = board_idx * 9 + cell_idx
    cells[cell_global] = current_player

    # Create visual mark
    px, py = get_cell_pos(board_idx, cell_idx)
    if current_player == PLAYER_X:
        create_x_mark(px, py)
    else:
        create_o_mark(px, py)

    # Check if this board is now won
    check_board_win(board_idx)

    # Check if overall game is won
    check_game_win()

    if game_state == STATE_PLAYING:
        # Determine next required board
        next_board = cell_idx
        if board_states[next_board] != BOARD_ACTIVE:
            required_board = -1
        else:
            required_board = next_board

        # Switch player
        current_player = PLAYER_O if current_player == PLAYER_X else PLAYER_X

        # If cursor is in invalid position, move it
        if required_board != -1 and cursor_board != required_board:
            cursor_board = required_board

        update_cursor()
        update_highlight()
        update_turn_text()

def move_cursor(dx, dy):
    """Move cursor by delta, handling board transitions"""
    global cursor_board, cursor_cell

    cell_x = cursor_cell % 3
    cell_y = cursor_cell // 3
    board_x = cursor_board % 3
    board_y = cursor_board // 3

    new_cell_x = cell_x + dx
    new_cell_y = cell_y + dy

    if new_cell_x < 0 or new_cell_x > 2 or new_cell_y < 0 or new_cell_y > 2:
        if required_board == -1:
            # Can move to adjacent board
            new_board_x = board_x + dx
            new_board_y = board_y + dy
            new_board_x = max(0, min(2, new_board_x))
            new_board_y = max(0, min(2, new_board_y))
            new_board = new_board_y * 3 + new_board_x

            # Only move if new board is different and playable
            if new_board != cursor_board:
                cursor_board = new_board
                # Enter from opposite side
                if dx > 0:
                    new_cell_x = 0
                elif dx < 0:
                    new_cell_x = 2
                if dy > 0:
                    new_cell_y = 0
                elif dy < 0:
                    new_cell_y = 2
            else:
                # At edge of grid, wrap cell
                new_cell_x = max(0, min(2, new_cell_x))
                new_cell_y = max(0, min(2, new_cell_y))
        else:
            # Wrap within required board
            new_cell_x = (cell_x + dx) % 3
            new_cell_y = (cell_y + dy) % 3

    cursor_cell = new_cell_y * 3 + new_cell_x
    update_cursor()

def update_cursor():
    """Update cursor visual position and color"""
    px, py = get_cell_pos(cursor_board, cursor_cell)
    cursor.position = Vector2(px, py)
    cursor_inner.position = Vector2(px, py)

    if current_player == PLAYER_X:
        cursor.color = engine_draw.red
    else:
        cursor.color = engine_draw.blue

    # Update inner color based on board state
    if board_states[cursor_board] == BOARD_WON_X:
        cursor_inner.color = engine_draw.red
    elif board_states[cursor_board] == BOARD_WON_O:
        cursor_inner.color = engine_draw.blue
    elif board_states[cursor_board] == BOARD_TIED:
        cursor_inner.color = engine_draw.lightgrey
    else:
        cursor_inner.color = engine_draw.darkgrey

def update_highlight():
    """Update active board highlight"""
    if required_board == -1:
        highlight.opacity = 0
        highlight_inner.opacity = 0
    else:
        px, py = get_board_pos(required_board)
        highlight.position = Vector2(px + BOARD_SIZE // 2, py + BOARD_SIZE // 2)
        highlight_inner.position = Vector2(px + BOARD_SIZE // 2, py + BOARD_SIZE // 2)
        highlight.opacity = 1
        highlight_inner.opacity = 1

def update_turn_text():
    """Update turn indicator"""
    if current_player == PLAYER_X:
        turn_text.text = "X's Turn"
        turn_text.color = engine_draw.red
    else:
        turn_text.text = "O's Turn"
        turn_text.color = engine_draw.blue

def show_game_over():
    """Display game over screen"""
    if game_winner == PLAYER_X:
        game_over_text.text = "X Wins!"
        game_over_text.color = engine_draw.red
    elif game_winner == PLAYER_O:
        game_over_text.text = "O Wins!"
        game_over_text.color = engine_draw.blue
    else:
        game_over_text.text = "Tie!"
        game_over_text.color = engine_draw.white

    game_over_text.opacity = 1
    restart_text.opacity = 1
    highlight.opacity = 0
    highlight_inner.opacity = 0

# === Initialize ===
update_cursor()
update_highlight()
update_turn_text()

# === Main Game Loop ===
while True:
    if engine.tick():
        if input_cooldown > 0:
            input_cooldown -= 1

        if game_state == STATE_PLAYING:
            if input_cooldown == 0:
                # D-pad navigation
                if engine_io.UP.is_just_pressed:
                    move_cursor(0, -1)
                    input_cooldown = 5
                elif engine_io.DOWN.is_just_pressed:
                    move_cursor(0, 1)
                    input_cooldown = 5
                elif engine_io.LEFT.is_just_pressed:
                    move_cursor(-1, 0)
                    input_cooldown = 5
                elif engine_io.RIGHT.is_just_pressed:
                    move_cursor(1, 0)
                    input_cooldown = 5
                elif engine_io.A.is_just_pressed:
                    if is_valid_move(cursor_board, cursor_cell):
                        make_move(cursor_board, cursor_cell)
                    input_cooldown = 10

        elif game_state == STATE_GAME_OVER:
            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                init_game()
                input_cooldown = 15

        # Exit on MENU
        if engine_io.MENU.is_just_pressed:
            engine.end()
            break
