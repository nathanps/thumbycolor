import engine_main
import engine
import engine_draw
import engine_io
import engine_physics
from engine_nodes import (Rectangle2DNode, Text2DNode, CameraNode,
                          Circle2DNode, PhysicsRectangle2DNode,
                          PhysicsCircle2DNode)
from engine_math import Vector2
import urandom

# === Constants ===
STATE_SELECT_1 = 0   # Select first name
STATE_SELECT_2 = 1   # Select second name
STATE_COUNTDOWN = 2  # 3-2-1 countdown
STATE_PLAYING = 3    # Physics simulation
STATE_RESULT = 4     # Winner display

ALL_NAMES = ["Nathan", "Helen", "Kaylee", "Luke", "Mochi", "Lara", "Antonella"]

# Physics constants
BALL_RADIUS = 5
PIN_RADIUS = 3
PIN_SPACING_X = 24
PIN_SPACING_Y = 20
PIN_START_X = -48
PIN_START_Y = -30
PIN_ROWS = 3
PIN_COLS = 5

# Bucket constants
BUCKET_Y = 45
BUCKET_LEFT = -8
BUCKET_RIGHT = 8
BUCKET_WALL_HEIGHT = 15
BUCKET_SPEED = 0.5
BUCKET_MIN_X = -45
BUCKET_MAX_X = 45

# Ball spawn positions (offset)
BALL1_START_X = -15
BALL2_START_X = 15
BALL_START_Y = -55

# === Game State ===
state = STATE_SELECT_1
selected_names = [-1, -1]  # Indices of selected names
current_selection = 0      # Current cursor position
winner = -1
countdown_value = 3
countdown_timer = 0
input_cooldown = 0
bucket_x = 0.0  # Current bucket center position
bucket_direction = 1  # 1 = right, -1 = left

# === Physics Setup ===
engine.fps_limit(60)
engine_physics.set_gravity(0, -0.2)  # Even slower falling

# === Camera ===
camera = CameraNode()

# === Create Walls ===
def create_wall(x, y, width, height, color=engine_draw.darkgrey):
    wall = PhysicsRectangle2DNode(
        position=Vector2(x, y),
        width=width,
        height=height,
        dynamic=False,
        bounciness=0.3
    )
    visual = Rectangle2DNode()
    visual.width = width
    visual.height = height
    visual.color = color
    wall.add_child(visual)
    return wall, visual  # Return both physics and visual

# Side walls
left_wall, left_wall_vis = create_wall(-60, 0, 4, 128)
right_wall, right_wall_vis = create_wall(60, 0, 4, 128)

# Bucket walls and floor
bucket_left_wall, bucket_left_vis = create_wall(BUCKET_LEFT - 5, BUCKET_Y + 5, 6, BUCKET_WALL_HEIGHT, engine_draw.green)
bucket_right_wall, bucket_right_vis = create_wall(BUCKET_RIGHT + 5, BUCKET_Y + 5, 6, BUCKET_WALL_HEIGHT, engine_draw.green)
bucket_floor, bucket_floor_vis = create_wall(0, BUCKET_Y + BUCKET_WALL_HEIGHT, BUCKET_RIGHT - BUCKET_LEFT, 4, engine_draw.green)

# === Create Pins ===
pins = []
pin_visuals = []
for row in range(PIN_ROWS):
    # Offset every other row for staggered effect
    offset_x = (PIN_SPACING_X // 2) if (row % 2 == 1) else 0
    cols_this_row = PIN_COLS if (row % 2 == 0) else PIN_COLS - 1

    for col in range(cols_this_row):
        x = PIN_START_X + offset_x + (col * PIN_SPACING_X)
        y = PIN_START_Y + (row * PIN_SPACING_Y)

        pin = PhysicsCircle2DNode(
            position=Vector2(x, y),
            radius=PIN_RADIUS,
            dynamic=False,
            bounciness=5.0
        )

        pin_visual = Circle2DNode()
        pin_visual.radius = PIN_RADIUS
        pin_visual.color = engine_draw.white
        pin.add_child(pin_visual)
        pins.append(pin)
        pin_visuals.append(pin_visual)

# === Create Balls ===
STUCK_THRESHOLD = 0.1  # Velocity threshold to consider "stuck"
STUCK_FRAMES = 120     # 2 seconds at 60fps

class Ball:
    def __init__(self, player_id, color, start_x):
        self.player_id = player_id
        self.start_x = start_x
        self.color = color
        self.stuck_counter = 0  # Frames spent stuck

        # Use constructor parameters for physics to work properly
        self.physics = PhysicsCircle2DNode(
            position=Vector2(start_x, BALL_START_Y),
            radius=BALL_RADIUS,
            velocity=Vector2(0, 0),
            dynamic=True,
            bounciness=1.0,
            density=0.3,
            gravity_scale=Vector2(1, 1)
        )

        self.visual = Circle2DNode()
        self.visual.radius = BALL_RADIUS
        self.visual.color = color
        self.physics.add_child(self.visual)

    def reset(self):
        self.physics.position = Vector2(self.start_x, BALL_START_Y)
        self.physics.velocity = Vector2(0, 0)
        self.stuck_counter = 0

    def respawn_random(self):
        self.physics.position.x = (urandom.getrandbits(6) - 32)
        self.physics.position.y = BALL_START_Y
        self.physics.velocity = Vector2(0, 0)
        self.stuck_counter = 0

    def check_stuck(self):
        vel = self.physics.velocity
        speed = abs(vel.x) + abs(vel.y)
        if speed < STUCK_THRESHOLD:
            self.stuck_counter += 1
            if self.stuck_counter >= STUCK_FRAMES:
                self.bump()
                self.stuck_counter = 0
        else:
            self.stuck_counter = 0

    def bump(self):
        # Random upward bump with random horizontal direction
        bump_x = (urandom.getrandbits(4) - 8) * 0.3  # -2.4 to 2.1
        bump_y = -2.0  # Strong upward
        self.physics.velocity = Vector2(bump_x, bump_y)

    def show(self):
        self.visual.opacity = 1.0

    def hide(self):
        self.visual.opacity = 0.0
        # Move off-screen to prevent physics interaction
        self.physics.position = Vector2(0, -100)
        self.physics.velocity = Vector2(0, 0)

ball1 = Ball(0, engine_draw.red, BALL1_START_X)
ball2 = Ball(1, engine_draw.blue, BALL2_START_X)
balls = [ball1, ball2]

# Hide balls initially
ball1.hide()
ball2.hide()

# === UI Elements ===
title_text = Text2DNode()
title_text.position = Vector2(-10, -58)
title_text.color = engine_draw.white
title_text.text = "Select Player 1"

# Name selection texts
name_texts = []
for i, name in enumerate(ALL_NAMES):
    nt = Text2DNode()
    nt.position = Vector2(-30, -40 + i * 12)
    nt.color = engine_draw.white
    nt.text = name
    name_texts.append(nt)

# Selection indicator
selector = Rectangle2DNode()
selector.width = 4
selector.height = 10
selector.color = engine_draw.yellow
selector.position = Vector2(-38, -40)

# Countdown text (large, centered)
countdown_text = Text2DNode()
countdown_text.position = Vector2(-5, -10)
countdown_text.color = engine_draw.yellow
countdown_text.scale = Vector2(3, 3)
countdown_text.text = ""
countdown_text.opacity = 0

# Winner text
winner_text = Text2DNode()
winner_text.position = Vector2(5, -10)
winner_text.color = engine_draw.gold
winner_text.scale = Vector2(1.5, 1.5)
winner_text.text = ""
winner_text.opacity = 0

# Instruction text
instruction_text = Text2DNode()
instruction_text.position = Vector2(-35, 50)
instruction_text.color = engine_draw.white
instruction_text.text = "UP/DOWN + A"

# Player name labels during play
player1_label = Text2DNode()
player1_label.position = Vector2(-38, -58)
player1_label.color = engine_draw.red
player1_label.text = ""
player1_label.opacity = 0

player2_label = Text2DNode()
player2_label.position = Vector2(25, -58)
player2_label.color = engine_draw.blue
player2_label.text = ""
player2_label.opacity = 0

vs_text = Text2DNode()
vs_text.position = Vector2(-10, -58)
vs_text.color = engine_draw.white
vs_text.text = "vs"
vs_text.opacity = 0

# === Helper Functions ===
def show_selection_ui():
    title_text.opacity = 1.0
    selector.opacity = 1.0
    instruction_text.opacity = 1.0
    for nt in name_texts:
        nt.opacity = 1.0
    # Hide play elements
    countdown_text.opacity = 0
    winner_text.opacity = 0
    player1_label.opacity = 0
    player2_label.opacity = 0
    vs_text.opacity = 0
    # Hide pins during selection (use visual references)
    for pv in pin_visuals:
        pv.opacity = 0
    left_wall_vis.opacity = 0
    right_wall_vis.opacity = 0
    bucket_left_vis.opacity = 0
    bucket_right_vis.opacity = 0
    bucket_floor_vis.opacity = 0

def hide_selection_ui():
    title_text.opacity = 0
    selector.opacity = 0
    instruction_text.opacity = 0
    for nt in name_texts:
        nt.opacity = 0

def show_play_ui():
    hide_selection_ui()
    player1_label.opacity = 1.0
    player2_label.opacity = 1.0
    vs_text.opacity = 1.0
    # Show pins and walls (use visual references)
    for pv in pin_visuals:
        pv.opacity = 1.0
    left_wall_vis.opacity = 1.0
    right_wall_vis.opacity = 1.0
    bucket_left_vis.opacity = 1.0
    bucket_right_vis.opacity = 1.0
    bucket_floor_vis.opacity = 1.0

def update_name_colors():
    for i, nt in enumerate(name_texts):
        if i == selected_names[0]:
            nt.color = engine_draw.darkgrey  # Already selected
        else:
            nt.color = engine_draw.white

def move_bucket():
    global bucket_x, bucket_direction
    bucket_x += BUCKET_SPEED * bucket_direction
    # Bounce off edges
    if bucket_x > BUCKET_MAX_X:
        bucket_x = BUCKET_MAX_X
        bucket_direction = -1
    elif bucket_x < BUCKET_MIN_X:
        bucket_x = BUCKET_MIN_X
        bucket_direction = 1
    # Update bucket physics positions
    bucket_left_wall.position.x = bucket_x + BUCKET_LEFT - 5
    bucket_right_wall.position.x = bucket_x + BUCKET_RIGHT + 5
    bucket_floor.position.x = bucket_x

def check_winner():
    global winner, state
    for ball in balls:
        pos = ball.physics.position
        if pos.y > BUCKET_Y:
            if (bucket_x + BUCKET_LEFT) < pos.x < (bucket_x + BUCKET_RIGHT):
                winner = ball.player_id
                state = STATE_RESULT
                return True
    return False

def check_respawn():
    for ball in balls:
        pos = ball.physics.position
        # Off bottom but not in bucket
        if pos.y > 70:
            in_bucket = (bucket_x + BUCKET_LEFT) < pos.x < (bucket_x + BUCKET_RIGHT)
            if not in_bucket:
                ball.respawn_random()

def reset_game():
    global state, selected_names, current_selection, winner, countdown_value, countdown_timer, bucket_x
    state = STATE_SELECT_1
    selected_names = [-1, -1]
    current_selection = 0
    winner = -1
    countdown_value = 3
    countdown_timer = 0
    bucket_x = 0.0  # Reset bucket to center
    ball1.hide()
    ball2.hide()
    show_selection_ui()
    # Reset name colors
    for nt in name_texts:
        nt.color = engine_draw.white

# Initialize UI
show_selection_ui()

# === Main Game Loop ===
while True:
    if engine.tick():
        # Input cooldown
        if input_cooldown > 0:
            input_cooldown -= 1

        if state == STATE_SELECT_1:
            title_text.text = "Select Player 1"

            if input_cooldown == 0:
                if engine_io.UP.is_just_pressed:
                    current_selection = (current_selection - 1) % len(ALL_NAMES)
                    input_cooldown = 5
                elif engine_io.DOWN.is_just_pressed:
                    current_selection = (current_selection + 1) % len(ALL_NAMES)
                    input_cooldown = 5
                elif engine_io.A.is_just_pressed:
                    selected_names[0] = current_selection
                    state = STATE_SELECT_2
                    # Move to next available name
                    current_selection = (current_selection + 1) % len(ALL_NAMES)
                    update_name_colors()
                    input_cooldown = 10

            selector.position.y = -40 + current_selection * 12

        elif state == STATE_SELECT_2:
            title_text.text = "Select Player 2"

            if input_cooldown == 0:
                if engine_io.UP.is_just_pressed:
                    current_selection = (current_selection - 1) % len(ALL_NAMES)
                    # Skip already selected name
                    if current_selection == selected_names[0]:
                        current_selection = (current_selection - 1) % len(ALL_NAMES)
                    input_cooldown = 5
                elif engine_io.DOWN.is_just_pressed:
                    current_selection = (current_selection + 1) % len(ALL_NAMES)
                    # Skip already selected name
                    if current_selection == selected_names[0]:
                        current_selection = (current_selection + 1) % len(ALL_NAMES)
                    input_cooldown = 5
                elif engine_io.A.is_just_pressed:
                    selected_names[1] = current_selection
                    # Set up player labels
                    player1_label.text = ALL_NAMES[selected_names[0]]
                    player2_label.text = ALL_NAMES[selected_names[1]]
                    state = STATE_COUNTDOWN
                    countdown_value = 3
                    countdown_timer = 0
                    show_play_ui()
                    countdown_text.opacity = 1.0
                    input_cooldown = 10
                elif engine_io.B.is_just_pressed:
                    # Go back to player 1 selection
                    state = STATE_SELECT_1
                    selected_names[0] = -1
                    for nt in name_texts:
                        nt.color = engine_draw.white
                    input_cooldown = 10

            selector.position.y = -40 + current_selection * 12

        elif state == STATE_COUNTDOWN:
            countdown_timer += 1
            if countdown_value > 0:
                countdown_text.text = str(countdown_value)
            else:
                countdown_text.text = "GO!"

            if countdown_timer >= 60:  # 1 second per count
                countdown_timer = 0
                countdown_value -= 1
                if countdown_value < -1:  # After "GO!" displays for 1 second
                    state = STATE_PLAYING
                    countdown_text.opacity = 0
                    # Reset and show balls
                    ball1.reset()
                    ball2.reset()
                    ball1.show()
                    ball2.show()
                    # Randomize bucket direction
                    bucket_direction = 1 if urandom.getrandbits(1) else -1

        elif state == STATE_PLAYING:
            move_bucket()
            check_winner()
            check_respawn()
            # Bumper buttons nudge balls
            if engine_io.LB.is_pressed:
                for ball in balls:
                    ball.physics.velocity.x -= 0.75
                    ball.physics.velocity.y -= 0.5
            if engine_io.RB.is_pressed:
                for ball in balls:
                    ball.physics.velocity.x += 0.75
                    ball.physics.velocity.y -= 0.5

        elif state == STATE_RESULT:
            winner_text.opacity = 1.0
            winner_name = ALL_NAMES[selected_names[winner]]
            winner_text.text = winner_name + " wins!"
            instruction_text.text = "Press A"
            instruction_text.opacity = 1.0

            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                instruction_text.text = "UP/DOWN + A"
                reset_game()
                input_cooldown = 15

        # Exit on MENU
        if engine_io.MENU.is_just_pressed:
            engine.end()
            break
