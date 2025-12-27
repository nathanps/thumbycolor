import engine_main
import engine
from engine_nodes import Rectangle2DNode, Text2DNode, CameraNode
from engine_math import Vector2
import engine_io
import engine_draw
import engine_save
import urandom

# Constants
NUM_RACERS = 3
STARTING_MONEY = 100
PAYOUT_MULTIPLIER = 3
START_X = -55
FINISH_X = 50
LANE_SPACING = 20

# Colors for racers
RACER_COLORS = [engine_draw.red, engine_draw.green, engine_draw.blue]

# Randomly pick 3 names from the pool
ALL_NAMES = ["Nathan", "Helen", "Kaylee", "Luke", "Mochi"]
name_pool = ALL_NAMES.copy()
RACER_NAMES = []
for _ in range(3):
    idx = urandom.getrandbits(8) % len(name_pool)
    RACER_NAMES.append(name_pool.pop(idx))

# Initialize save system
engine_save._init_saves_dir("Saves/Games/Race")
engine_save.set_location("save")

# Game state
state = 0  # 0=betting, 1=bet_amount, 2=racing, 3=result
money = engine_save.load("money", STARTING_MONEY)
selected_racer = 0
bet_amount = 10
winner = -1
halfway_rerolled = False
input_cooldown = 0

# Racer data
racer_speeds = [0.0, 0.0, 0.0]
race_history = []  # Track last 3 winners for fatigue system

def get_speed_modifier(racer_index):
    """Returns speed modifier based on recent wins"""
    wins = race_history.count(racer_index)
    if wins >= 2:
        return 0.8   # 20% slower (tired)
    elif wins == 0 and len(race_history) >= 2:
        return 1.2   # 20% faster (rested)
    else:
        return 1.0   # normal

def get_status(racer_index):
    """Returns status string for display"""
    wins = race_history.count(racer_index)
    if wins >= 2:
        return "TIRED"
    elif wins == 0 and len(race_history) >= 2:
        return "RESTED"
    else:
        return ""

def random_speed(racer_index):
    base = 0.25 + (urandom.getrandbits(8) / 255.0) * 0.75
    return base * get_speed_modifier(racer_index)

def reset_race():
    global halfway_rerolled, winner
    for i in range(NUM_RACERS):
        racers[i].position.x = START_X
        racer_speeds[i] = random_speed(i)
    halfway_rerolled = False
    winner = -1

# Create camera
camera = CameraNode()

# Create racers (colored rectangles)
racers = []
for i in range(NUM_RACERS):
    racer = Rectangle2DNode()
    racer.width = 10
    racer.height = 15
    racer.color = RACER_COLORS[i]
    racer.position = Vector2(START_X, (i - 1) * LANE_SPACING)
    racers.append(racer)

# Create finish line
finish_line = Rectangle2DNode()
finish_line.width = 3
finish_line.height = 70
finish_line.color = engine_draw.white
finish_line.position = Vector2(FINISH_X, 0)

# Create name labels for each racer
name_texts = []
for i in range(NUM_RACERS):
    name_label = Text2DNode()
    name_label.position = Vector2(START_X + 30, (i - 1) * LANE_SPACING)
    name_label.color = RACER_COLORS[i]
    name_label.text = RACER_NAMES[i]
    name_texts.append(name_label)

# Create status text for each racer (TIRED/RESTED)
status_texts = []
for i in range(NUM_RACERS):
    status = Text2DNode()
    status.position = Vector2(45, (i - 1) * LANE_SPACING)
    status.color = engine_draw.white
    status.text = ""
    status_texts.append(status)

# Create selection indicator
selector = Rectangle2DNode()
selector.width = 4
selector.height = 18
selector.color = engine_draw.yellow
selector.position = Vector2(START_X - 10, 0)

# Create UI text
ui_text = Text2DNode()
ui_text.position = Vector2(-30, 50)
ui_text.color = engine_draw.white
ui_text.text = "SELECT: RED\nA to confirm"

money_text = Text2DNode()
money_text.position = Vector2(-20, -55)
money_text.color = engine_draw.gold
money_text.scale = Vector2(2, 2)
money_text.text = "$100"

# Main game loop
while True:
    if engine.tick():
        # Input cooldown
        if input_cooldown > 0:
            input_cooldown -= 1
            continue

        if state == 0:  # Betting - select racer
            selector.opacity = 1.0
            # Update status display for each racer
            for i in range(NUM_RACERS):
                s = get_status(i)
                status_texts[i].text = s
                if s == "TIRED":
                    status_texts[i].color = engine_draw.red
                elif s == "RESTED":
                    status_texts[i].color = engine_draw.green
                else:
                    status_texts[i].color = engine_draw.white

            if engine_io.UP.is_just_pressed:
                selected_racer = (selected_racer - 1) % NUM_RACERS
                input_cooldown = 5
            elif engine_io.DOWN.is_just_pressed:
                selected_racer = (selected_racer + 1) % NUM_RACERS
                input_cooldown = 5
            elif engine_io.A.is_just_pressed:
                state = 1
                bet_amount = min(10, money)
                input_cooldown = 10

            selector.position.y = (selected_racer - 1) * LANE_SPACING
            ui_text.text = "SELECT: " + RACER_NAMES[selected_racer] + "\nA to confirm"

        elif state == 1:  # Bet amount
            if engine_io.UP.is_just_pressed:
                bet_amount = min(bet_amount + 10, money)
                input_cooldown = 5
            elif engine_io.DOWN.is_just_pressed:
                bet_amount = max(bet_amount - 10, 10)
                input_cooldown = 5
            elif engine_io.A.is_just_pressed:
                reset_race()
                state = 2
                input_cooldown = 10
            elif engine_io.B.is_just_pressed:
                state = 0
                input_cooldown = 10

            ui_text.text = "BET: $" + str(bet_amount) + "\nA:Race B:Back"

        elif state == 2:  # Racing
            selector.opacity = 0
            # Hide status texts during race
            for i in range(NUM_RACERS):
                status_texts[i].text = ""

            # Move racers
            for i in range(NUM_RACERS):
                racers[i].position.x += racer_speeds[i]

            # Check halfway reroll
            if not halfway_rerolled:
                for i in range(NUM_RACERS):
                    if racers[i].position.x >= (START_X + FINISH_X) / 2:
                        for j in range(NUM_RACERS):
                            racer_speeds[j] = random_speed(j)
                        halfway_rerolled = True
                        break

            # Check winner
            for i in range(NUM_RACERS):
                if racers[i].position.x >= FINISH_X:
                    winner = i
                    # Track win history
                    race_history.append(winner)
                    if len(race_history) > 3:
                        race_history.pop(0)
                    # Update money
                    if winner == selected_racer:
                        money += bet_amount * (PAYOUT_MULTIPLIER - 1)
                    else:
                        money -= bet_amount
                    state = 3
                    break

            if halfway_rerolled:
                ui_text.text = "SPEED BOOST!"
            else:
                ui_text.text = "RACING..."

        elif state == 3:  # Result
            if engine_io.A.is_just_pressed:
                if money <= 0:
                    money = STARTING_MONEY
                # Reset racers to start
                for i in range(NUM_RACERS):
                    racers[i].position.x = START_X
                state = 0
                input_cooldown = 10

            if winner == selected_racer:
                win_amt = bet_amount * (PAYOUT_MULTIPLIER - 1)
                ui_text.text = "WIN! +$" + str(win_amt) + "\n" + RACER_NAMES[winner] + " wins!\nA:Continue"
                ui_text.color = engine_draw.green
            else:
                ui_text.text = "LOSE! -$" + str(bet_amount) + "\n" + RACER_NAMES[winner] + " wins!\nA:Continue"
                ui_text.color = engine_draw.red

        # Update money display
        money_text.text = "$" + str(money)

        # Reset text color for non-result states
        if state != 3:
            ui_text.color = engine_draw.white

        # Save and exit on MENU
        if engine_io.MENU.is_just_pressed:
            engine_save.save("money", money)
            engine.end()
            break
