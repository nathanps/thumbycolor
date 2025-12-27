import engine_main
import engine
import engine_draw
import engine_io
import engine_save
from engine_nodes import Rectangle2DNode, Text2DNode, CameraNode
from engine_math import Vector2
import urandom
import time

# Constants
STATE_PACKAGE = 0
STATE_REVEAL = 1
STATE_MAIN = 2
STATE_DEAD = 3

HUNGER_DECAY_MS = 45000  # 45 seconds
HAPPY_DECAY_MS = 60000   # 60 seconds
DEATH_TIMER_MS = 30000   # 30 seconds at 0 hunger
SAVE_INTERVAL_MS = 10000 # Save every 10 seconds
REVEAL_DURATION_MS = 1500 # 1.5 second reveal
ANIM_DURATION_MS = 500    # Animation duration
IDLE_CHECK_MS = 2000      # Check for idle anim every 2 sec
JUMP_DURATION_MS = 500    # Happy jump duration
JUMP_HEIGHT = 10          # Pixels to jump

MAX_STAT = 5
BAR_WIDTH = 40
BAR_HEIGHT = 6

# Labubu types: name, body_color, accent_color, weight
LABUBU_TYPES = [
    {"name": "Love", "body": engine_draw.red, "accent": engine_draw.pink, "weight": 15},
    {"name": "Happiness", "body": engine_draw.pink, "accent": engine_draw.magenta, "weight": 15},
    {"name": "Loyalty", "body": engine_draw.magenta, "accent": engine_draw.yellow, "weight": 15},
    {"name": "Serenity", "body": engine_draw.green, "accent": engine_draw.cyan, "weight": 15},
    {"name": "Hope", "body": engine_draw.blue, "accent": engine_draw.cyan, "weight": 15},
    {"name": "Luck", "body": engine_draw.pink, "accent": engine_draw.cyan, "weight": 15},
    {"name": "Secret", "body": engine_draw.darkgrey, "accent": engine_draw.lightgrey, "weight": 10},
]

# Initialize save system
engine_save._init_saves_dir("Saves/Games/Labubu")
engine_save.set_location("save")

# Game state
state = STATE_PACKAGE
labubu_type = 0
hunger = 0
happiness = 3
last_hunger_tick = 0
last_happy_tick = 0
death_timer_start = 0
last_save_time = 0
reveal_start_time = 0
menu_selection = 0  # 0 = Feed, 1 = Play
input_cooldown = 0
anim_start_time = 0
anim_type = 0  # 0 = none, 1 = feed, 2 = play
idle_anim_type = 0  # 0 = none, 1 = happy_jump, 2 = sleeping
idle_anim_start = 0
idle_anim_check = 0
BASE_BODY_Y = 5
BASE_HEAD_Y = -20

def weighted_random_choice():
    """Select a random Labubu based on weights"""
    total_weight = sum(t["weight"] for t in LABUBU_TYPES)
    roll = urandom.getrandbits(8) % total_weight
    cumulative = 0
    for i, t in enumerate(LABUBU_TYPES):
        cumulative += t["weight"]
        if roll < cumulative:
            return i
    return 0

def save_game():
    """Save current game state"""
    engine_save.save("labubu_type", labubu_type)
    engine_save.save("hunger", hunger)
    engine_save.save("happiness", happiness)
    engine_save.save("save_time", time.ticks_ms())

def load_game():
    """Load game state and apply time-based decay"""
    global labubu_type, hunger, happiness, last_hunger_tick, last_happy_tick
    global state, death_timer_start

    saved_type = engine_save.load("labubu_type", None)
    if saved_type is None:
        return False

    labubu_type = saved_type
    hunger = engine_save.load("hunger", 0)
    happiness = engine_save.load("happiness", 3)
    saved_time = engine_save.load("save_time", 0)

    # Calculate elapsed time and apply decay
    current_time = time.ticks_ms()
    elapsed = time.ticks_diff(current_time, saved_time)

    # Handle negative elapsed time (device restart resets ticks)
    if elapsed < 0:
        elapsed = 0

    # Apply hunger decay
    hunger_ticks = elapsed // HUNGER_DECAY_MS
    hunger = max(0, hunger - hunger_ticks)

    # Apply happiness decay
    happy_ticks = elapsed // HAPPY_DECAY_MS
    happiness = max(0, happiness - happy_ticks)

    # Reset timers
    last_hunger_tick = current_time
    last_happy_tick = current_time

    # Check if should be dead (was at 0 hunger for too long)
    if hunger == 0 and elapsed > DEATH_TIMER_MS:
        state = STATE_DEAD
        return True

    if hunger == 0:
        death_timer_start = current_time - (elapsed % DEATH_TIMER_MS)
    else:
        death_timer_start = 0

    state = STATE_MAIN
    return True

def clear_save():
    """Delete all save data"""
    engine_save.delete("labubu_type")
    engine_save.delete("hunger")
    engine_save.delete("happiness")
    engine_save.delete("save_time")

def update_labubu_visuals():
    """Update Labubu colors based on type"""
    ltype = LABUBU_TYPES[labubu_type]
    labubu_body.color = ltype["body"]
    labubu_head.color = ltype["accent"]
    name_text.text = ltype["name"]

def update_status_bars():
    """Update status bar fill widths and positions"""
    hunger_fill.width = int((hunger / MAX_STAT) * BAR_WIDTH)
    hunger_fill.position.x = 5 + hunger_fill.width / 2  # Left edge at x=5
    happy_fill.width = int((happiness / MAX_STAT) * BAR_WIDTH)
    happy_fill.position.x = 5 + happy_fill.width / 2    # Left edge at x=5

def hide_animations():
    """Hide all animation elements"""
    food_block.opacity = 0
    food_block.width = 12
    food_block.height = 12
    for line in action_lines:
        line.opacity = 0

def reset_idle_anim():
    """Reset idle animation state"""
    global idle_anim_type
    idle_anim_type = 0
    labubu_body.position.x = 0
    labubu_body.position.y = BASE_BODY_Y
    labubu_head.position.x = 0
    labubu_head.position.y = BASE_HEAD_Y
    labubu_body.rotation = 0
    labubu_head.rotation = 0
    sleep_text.opacity = 0
    disco_ball.opacity = 0
    disco_ball.position.y = -60
    for ray in disco_rays:
        ray.opacity = 0
    for tear in cry_tears:
        tear.opacity = 0

def show_package():
    """Show package, hide other elements"""
    package_box.opacity = 1.0
    package_text.opacity = 1.0
    prompt_text.opacity = 1.0
    prompt_text.text = "Press A to Open"

    labubu_body.opacity = 0
    labubu_head.opacity = 0
    name_text.opacity = 0
    hunger_bg.opacity = 0
    hunger_fill.opacity = 0
    hunger_label.opacity = 0
    happy_bg.opacity = 0
    happy_fill.opacity = 0
    happy_label.opacity = 0
    menu_text.opacity = 0
    selector.opacity = 0
    death_text.opacity = 0
    hide_animations()
    reset_idle_anim()

def show_reveal():
    """Show Labubu reveal"""
    package_box.opacity = 0
    package_text.opacity = 0
    prompt_text.opacity = 0

    labubu_body.opacity = 1.0
    labubu_head.opacity = 1.0
    name_text.opacity = 1.0

    hunger_bg.opacity = 0
    hunger_fill.opacity = 0
    hunger_label.opacity = 0
    happy_bg.opacity = 0
    happy_fill.opacity = 0
    happy_label.opacity = 0
    menu_text.opacity = 0
    selector.opacity = 0
    death_text.opacity = 0
    hide_animations()
    reset_idle_anim()

def show_main():
    """Show main gameplay screen"""
    package_box.opacity = 0
    package_text.opacity = 0
    prompt_text.opacity = 0

    labubu_body.opacity = 1.0
    labubu_head.opacity = 1.0
    name_text.opacity = 1.0
    hunger_bg.opacity = 1.0
    hunger_fill.opacity = 1.0
    hunger_label.opacity = 1.0
    happy_bg.opacity = 1.0
    happy_fill.opacity = 1.0
    happy_label.opacity = 1.0
    menu_text.opacity = 1.0
    selector.opacity = 1.0
    death_text.opacity = 0
    hide_animations()
    reset_idle_anim()

def show_death():
    """Show death screen"""
    package_box.opacity = 0
    package_text.opacity = 0
    prompt_text.opacity = 1.0
    prompt_text.text = "Press any button"

    labubu_body.opacity = 0.3
    labubu_head.opacity = 0.3
    name_text.opacity = 0.3
    hunger_bg.opacity = 0
    hunger_fill.opacity = 0
    hunger_label.opacity = 0
    happy_bg.opacity = 0
    happy_fill.opacity = 0
    happy_label.opacity = 0
    menu_text.opacity = 0
    selector.opacity = 0
    death_text.opacity = 1.0
    hide_animations()
    reset_idle_anim()

# Create camera
camera = CameraNode()

# Package visuals
package_box = Rectangle2DNode()
package_box.width = 40
package_box.height = 50
package_box.color = engine_draw.orange
package_box.position = Vector2(0, -5)

package_text = Text2DNode()
package_text.text = "??"
package_text.position = Vector2(-6, -10)
package_text.color = engine_draw.white

prompt_text = Text2DNode()
prompt_text.text = "Press A to Open"
prompt_text.position = Vector2(-5, 45)
prompt_text.color = engine_draw.white

# Labubu visuals (stacked shapes)
labubu_body = Rectangle2DNode()
labubu_body.width = 28
labubu_body.height = 32
labubu_body.color = engine_draw.green
labubu_body.position = Vector2(0, 5)
labubu_body.opacity = 0

labubu_head = Rectangle2DNode()
labubu_head.width = 22
labubu_head.height = 18
labubu_head.color = engine_draw.green
labubu_head.position = Vector2(0, -20)
labubu_head.opacity = 0

name_text = Text2DNode()
name_text.text = ""
name_text.position = Vector2(-10, 30)
name_text.color = engine_draw.white
name_text.opacity = 0

# Status bars
hunger_label = Text2DNode()
hunger_label.text = "Hunger:"
hunger_label.position = Vector2(-40, -50)
hunger_label.color = engine_draw.white
hunger_label.opacity = 0

hunger_bg = Rectangle2DNode()
hunger_bg.width = BAR_WIDTH
hunger_bg.height = BAR_HEIGHT
hunger_bg.color = engine_draw.darkgrey
hunger_bg.position = Vector2(25, -50)
hunger_bg.opacity = 0

hunger_fill = Rectangle2DNode()
hunger_fill.width = 0
hunger_fill.height = BAR_HEIGHT
hunger_fill.color = engine_draw.red
hunger_fill.position = Vector2(25 - BAR_WIDTH // 2, -50)
hunger_fill.opacity = 0

happy_label = Text2DNode()
happy_label.text = "Happy:"
happy_label.position = Vector2(-40, -40)
happy_label.color = engine_draw.white
happy_label.opacity = 0

happy_bg = Rectangle2DNode()
happy_bg.width = BAR_WIDTH
happy_bg.height = BAR_HEIGHT
happy_bg.color = engine_draw.darkgrey
happy_bg.position = Vector2(25, -40)
happy_bg.opacity = 0

happy_fill = Rectangle2DNode()
happy_fill.width = 0
happy_fill.height = BAR_HEIGHT
happy_fill.color = engine_draw.yellow
happy_fill.position = Vector2(25 - BAR_WIDTH // 2, -40)
happy_fill.opacity = 0

# Menu
menu_text = Text2DNode()
menu_text.text = "Feed  Play  Ignore"
menu_text.position = Vector2(-10, 50)
menu_text.color = engine_draw.white
menu_text.opacity = 0

# Underline selector
selector = Rectangle2DNode()
selector.width = 26
selector.height = 2
selector.color = engine_draw.yellow
selector.opacity = 0
selector.position = Vector2(-42, 58)

# Feed animation - brown food block
food_block = Rectangle2DNode()
food_block.width = 12
food_block.height = 12
food_block.color = engine_draw.orange
food_block.opacity = 0
food_block.position = Vector2(-35, 0)

# Play animation - action lines (4 lines around labubu)
action_lines = []
line_positions = [(-25, -10), (25, -10), (-25, 15), (25, 15)]
for pos in line_positions:
    line = Rectangle2DNode()
    line.width = 8
    line.height = 3
    line.color = engine_draw.yellow
    line.opacity = 0
    line.position = Vector2(pos[0], pos[1])
    action_lines.append(line)

# Death text
death_text = Text2DNode()
death_text.text = "Your Labubu died!"
death_text.position = Vector2(-5, -40)
death_text.color = engine_draw.red
death_text.opacity = 0

# Sleep animation text
sleep_text = Text2DNode()
sleep_text.text = "zzz"
sleep_text.position = Vector2(25, -25)
sleep_text.color = engine_draw.white
sleep_text.opacity = 0

# Disco ball and rays
disco_ball = Rectangle2DNode()
disco_ball.width = 12
disco_ball.height = 12
disco_ball.color = engine_draw.white
disco_ball.position = Vector2(40, -60)
disco_ball.opacity = 0

disco_rays = []
for i in range(4):
    ray = Rectangle2DNode()
    ray.width = 20
    ray.height = 2
    ray.color = engine_draw.white
    ray.opacity = 0
    ray.position = Vector2(40, -30)
    disco_rays.append(ray)

# Crying tears (blue lines from head)
cry_tears = []
tear_offsets = [(-12, -15), (12, -15), (-8, -12), (8, -12)]  # Positions relative to head
for offset in tear_offsets:
    tear = Rectangle2DNode()
    tear.width = 3
    tear.height = 8
    tear.color = engine_draw.cyan
    tear.opacity = 0
    tear.position = Vector2(offset[0], offset[1])
    cry_tears.append(tear)

# Try to load existing save
if not load_game():
    state = STATE_PACKAGE
    show_package()
else:
    if state == STATE_DEAD:
        update_labubu_visuals()
        show_death()
    else:
        update_labubu_visuals()
        update_status_bars()
        show_main()

# Main game loop
while True:
    if engine.tick():
        current_time = time.ticks_ms()

        # Input cooldown
        if input_cooldown > 0:
            input_cooldown -= 1

        if state == STATE_PACKAGE:
            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                # Open package - select random Labubu
                labubu_type = weighted_random_choice()
                hunger = 0  # Starts hungry
                happiness = 3
                last_hunger_tick = current_time
                last_happy_tick = current_time
                death_timer_start = current_time  # Start death timer since hunger is 0

                update_labubu_visuals()
                show_reveal()
                reveal_start_time = current_time
                state = STATE_REVEAL
                input_cooldown = 10

        elif state == STATE_REVEAL:
            # Auto-advance after reveal duration
            if time.ticks_diff(current_time, reveal_start_time) > REVEAL_DURATION_MS:
                update_status_bars()
                show_main()
                last_save_time = current_time
                save_game()
                state = STATE_MAIN

        elif state == STATE_MAIN:
            # Time-based decay (faster if other stat is empty)
            hunger_decay_time = HUNGER_DECAY_MS // 2 if happiness == 0 else HUNGER_DECAY_MS
            if time.ticks_diff(current_time, last_hunger_tick) >= hunger_decay_time:
                hunger = max(0, hunger - 1)
                last_hunger_tick = current_time
                update_status_bars()

            happy_decay_time = HAPPY_DECAY_MS // 2 if hunger == 0 else HAPPY_DECAY_MS
            if time.ticks_diff(current_time, last_happy_tick) >= happy_decay_time:
                happiness = max(0, happiness - 1)
                last_happy_tick = current_time
                update_status_bars()

            # Death timer check
            if hunger == 0:
                if death_timer_start == 0:
                    death_timer_start = current_time
                elif time.ticks_diff(current_time, death_timer_start) >= DEATH_TIMER_MS:
                    clear_save()
                    show_death()
                    state = STATE_DEAD
                    input_cooldown = 20
            else:
                death_timer_start = 0

            # Menu navigation (0=Feed, 1=Play, 2=Ignore)
            if input_cooldown == 0:
                if engine_io.LEFT.is_just_pressed:
                    menu_selection = (menu_selection - 1) % 3
                    input_cooldown = 5
                elif engine_io.RIGHT.is_just_pressed:
                    menu_selection = (menu_selection + 1) % 3
                    input_cooldown = 5
                elif engine_io.A.is_just_pressed:
                    if menu_selection == 0:  # Feed
                        hunger = min(MAX_STAT, hunger + 2)
                        if hunger > 0:
                            death_timer_start = 0
                        # Start feed animation
                        anim_type = 1
                        anim_start_time = current_time
                        food_block.opacity = 1.0
                        food_block.width = 12
                        food_block.height = 12
                    elif menu_selection == 1:  # Play
                        happiness = min(MAX_STAT, happiness + 2)
                        # Start play animation
                        anim_type = 2
                        anim_start_time = current_time
                        for line in action_lines:
                            line.opacity = 1.0
                    else:  # Ignore - drain stats for testing
                        hunger = max(0, hunger - 3)
                        happiness = max(0, happiness - 3)
                    update_status_bars()
                    last_hunger_tick = current_time  # Reset decay timer on action
                    last_happy_tick = current_time
                    input_cooldown = 10

            # Update selector position (Feed=-42, Play=-12, Ignore=18)
            if menu_selection == 0:
                selector.position.x = -42
            elif menu_selection == 1:
                selector.position.x = -12
            else:
                selector.position.x = 18

            # Update animations
            if anim_type > 0:
                anim_elapsed = time.ticks_diff(current_time, anim_start_time)
                if anim_elapsed >= ANIM_DURATION_MS:
                    # Animation finished
                    anim_type = 0
                    hide_animations()
                else:
                    progress = anim_elapsed / ANIM_DURATION_MS
                    if anim_type == 1:  # Feed - shrink food block
                        size = int(12 * (1.0 - progress))
                        food_block.width = max(1, size)
                        food_block.height = max(1, size)
                    elif anim_type == 2:  # Play - fade out action lines
                        for line in action_lines:
                            line.opacity = 1.0 - progress

            # Idle animations
            # Priority: Crying (both 0) > Disco (both MAX) > Sleep (hunger MAX) > Jump (happiness MAX)
            if hunger == 0 and happiness == 0:
                # Start crying if not already
                if idle_anim_type != 4:
                    idle_anim_type = 4
                    idle_anim_start = current_time
            elif idle_anim_type == 4:
                # Was crying but stats improved
                reset_idle_anim()
            elif hunger == MAX_STAT and happiness == MAX_STAT:
                # Start disco if not already
                if idle_anim_type != 3:
                    idle_anim_type = 3
                    idle_anim_start = current_time
            elif idle_anim_type == 3:
                # Was disco but one stat dropped
                reset_idle_anim()

            if idle_anim_type == 0:
                # Check if we should start an idle animation
                if time.ticks_diff(current_time, idle_anim_check) > IDLE_CHECK_MS:
                    idle_anim_check = current_time
                    if hunger == MAX_STAT:
                        # Start sleeping
                        idle_anim_type = 2
                        idle_anim_start = current_time
                    elif happiness == MAX_STAT:
                        # 30% chance to start happy jump
                        if urandom.getrandbits(8) % 100 < 30:
                            idle_anim_type = 1
                            idle_anim_start = current_time
            elif idle_anim_type == 1:
                # Happy jump animation
                idle_elapsed = time.ticks_diff(current_time, idle_anim_start)
                if idle_elapsed >= JUMP_DURATION_MS:
                    # Jump finished
                    reset_idle_anim()
                else:
                    progress = idle_elapsed / JUMP_DURATION_MS
                    # Jump up then down (parabola)
                    jump_offset = JUMP_HEIGHT * (1.0 - abs(2.0 * progress - 1.0))
                    labubu_body.position.y = BASE_BODY_Y - jump_offset
                    labubu_head.position.y = BASE_HEAD_Y - jump_offset
                    # Spin (full rotation)
                    labubu_body.rotation = progress * 6.28
                    labubu_head.rotation = progress * 6.28
            elif idle_anim_type == 2:
                # Sleeping animation
                if hunger < MAX_STAT:
                    # Wake up
                    reset_idle_anim()
                else:
                    # Rotate to sleeping position
                    labubu_body.rotation = 1.57  # 90 degrees
                    labubu_head.rotation = 1.57
                    # Animate zzz opacity
                    idle_elapsed = time.ticks_diff(current_time, idle_anim_start)
                    zzz_cycle = (idle_elapsed % 1000) / 1000.0
                    sleep_text.opacity = 0.5 + 0.5 * abs(1.0 - 2.0 * zzz_cycle)
            elif idle_anim_type == 3:
                # Disco dance animation
                idle_elapsed = time.ticks_diff(current_time, idle_anim_start)

                # Disco ball descends over 500ms then stays
                if idle_elapsed < 500:
                    disco_ball.position.y = -60 + (30 * idle_elapsed / 500)
                else:
                    disco_ball.position.y = -30
                disco_ball.opacity = 1.0

                # Rotate rays around disco ball
                ray_angle = (idle_elapsed / 500.0) * 3.14  # Rotate over time
                for i, ray in enumerate(disco_rays):
                    ray.opacity = 1.0
                    ray.rotation = ray_angle + (i * 0.785)  # Offset each ray by 45 degrees

                # Labubu wiggles side to side
                wiggle = 5 * (1.0 - abs(2.0 * ((idle_elapsed % 300) / 300.0) - 1.0)) - 2.5
                labubu_body.position.x = wiggle
                labubu_head.position.x = wiggle
                labubu_body.rotation = wiggle * 0.05
                labubu_head.rotation = wiggle * 0.05
            elif idle_anim_type == 4:
                # Crying animation - tears blink and labubu shakes
                idle_elapsed = time.ticks_diff(current_time, idle_anim_start)

                # Labubu shakes left and right rapidly
                shake_cycle = (idle_elapsed % 150) / 150.0
                shake = 4 * (1.0 - abs(2.0 * shake_cycle - 1.0)) - 2
                labubu_body.position.x = shake
                labubu_head.position.x = shake

                # Tears blink on/off every 200ms and move with the shake
                tear_cycle = (idle_elapsed % 400) / 400.0
                tear_opacity = 1.0 if tear_cycle < 0.5 else 0.0
                for i, tear in enumerate(cry_tears):
                    tear.opacity = tear_opacity
                    tear.position.x = tear_offsets[i][0] + shake

            # Auto-save
            if time.ticks_diff(current_time, last_save_time) >= SAVE_INTERVAL_MS:
                save_game()
                last_save_time = current_time

        elif state == STATE_DEAD:
            # Any button restarts
            if input_cooldown == 0:
                if (engine_io.A.is_just_pressed or engine_io.B.is_just_pressed or
                    engine_io.UP.is_just_pressed or engine_io.DOWN.is_just_pressed or
                    engine_io.LEFT.is_just_pressed or engine_io.RIGHT.is_just_pressed):
                    clear_save()
                    show_package()
                    state = STATE_PACKAGE
                    input_cooldown = 10

        # Exit on MENU
        if engine_io.MENU.is_just_pressed:
            # Save if we have a labubu (not in package state)
            if state != STATE_PACKAGE and state != STATE_DEAD:
                save_game()
            engine.end()
            break
