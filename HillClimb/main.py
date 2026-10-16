import engine_main
import engine
import engine_draw
import engine_io
import engine_save
from engine_nodes import Rectangle2DNode, Text2DNode, CameraNode, Circle2DNode
from engine_math import Vector2
import urandom
import math

# === Game States ===
STATE_TITLE = 0
STATE_PLAYING = 1
STATE_DEAD = 2

# === Screen Constants ===
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128

# === Physics Constants ===
GRAVITY_X = 0
GRAVITY_Y = 0.15  # Downward gravity (positive Y is down)

# Car physics
CAR_WIDTH = 22
CAR_HEIGHT = 10
WHEEL_RADIUS = 5
MOTOR_POWER = 0.08
BRAKE_POWER = 0.12
MAX_VELOCITY = 3.0
ROTATION_SMOOTHING = 0.15

# Terrain generation
SEGMENT_STEP = 16        # Ground is drawn as straight pieces this wide
TERRAIN_POOL_SIZE = 28   # Enough pieces to cover the screen plus a stretch behind
TERRAIN_BASE_Y = 30      # Height of the flat start
FLAT_UNTIL = 120         # Flat starting area length
HILL_FADE_IN = 200       # Hills grow smoothly from flat over this distance
HILL_AMP_START = 10      # Hill size near the start
HILL_AMP_MAX = 26        # Biggest hills (reached at HILL_GROWTH_DIST)
HILL_GROWTH_DIST = 3000  # ~300 m
GROUND_BAND = 16         # Thickness of the sloped grass+dirt strip
SLOPE_PULL = 1.0         # How strongly hills slow you down / speed you up
AIR_GRACE = 3            # Frames off the ground that still count as driving (tiny bumps)
LANDING_MAX_ANGLE = 1.3  # Landing more tilted than this (radians) wrecks the car

# Fuel system
MAX_FUEL = 100
FUEL_CONSUMPTION = 0.15  # Per frame when accelerating
FUEL_SPACING_START = 400   # Distance between fuel cans at the start
FUEL_SPACING_GROWTH = 0.12 # Cans get further apart the further you go
FUEL_SPACING_MAX = 1200

# === Save System ===
engine_save._init_saves_dir("Saves/Games/HillClimb")
engine_save.set_location("save")
high_score = engine_save.load("high_score", 0)

# === Engine Setup ===
engine.fps_limit(60)

# === Camera ===
camera = CameraNode()


# === Terrain Manager ===
class TerrainManager:
    """Generates procedural hilly terrain similar to Hill Climb Racing"""

    def __init__(self):
        self.strips = []    # Sloped grass+dirt strip for each piece
        self.columns = []   # Upright dirt column under each piece
        self.piece_end = [] # Right edge x of each piece (-9999 = unused)
        self.next_x = -SCREEN_WIDTH
        self.furthest_x = 0
        self._new_hill_shape()
        self._create_pool()

    def _create_pool(self):
        """Pre-create terrain piece objects"""
        for _ in range(TERRAIN_POOL_SIZE):
            # Dirt strip that follows the slope, with grass on top
            strip = Rectangle2DNode()
            strip.height = GROUND_BAND
            strip.color = engine_draw.brown
            strip.layer = 4
            strip.position = Vector2(-9999, -9999)

            grass = Rectangle2DNode()
            grass.height = 3
            grass.color = engine_draw.green
            grass.position = Vector2(0, -GROUND_BAND / 2 + 1.5)
            grass.layer = 5
            strip.add_child(grass)

            # Deep dirt below so no sky shows under the hills
            column = Rectangle2DNode()
            column.height = 100
            column.color = engine_draw.brown
            column.layer = 3
            column.position = Vector2(-9999, -9999)

            self.strips.append((strip, grass))
            self.columns.append(column)
            self.piece_end.append(-9999)

    def _new_hill_shape(self):
        """Pick random wave phases and lengths so every run has different hills"""
        def r():
            return urandom.getrandbits(16) / 65536
        self.p1 = r() * 6.28
        self.p2 = r() * 6.28
        self.p3 = r() * 6.28
        self.p4 = r() * 6.28
        self.f1 = 0.018 * (0.85 + r() * 0.3)   # Big rolling hills
        self.f2 = 0.041 * (0.85 + r() * 0.3)   # Medium hills
        self.f3 = 0.09 * (0.85 + r() * 0.3)    # Small bumps

    def _get_terrain_height(self, x):
        """Ground y at x: layered sine waves that fade in and grow with distance"""
        if x <= FLAT_UNTIL:
            return TERRAIN_BASE_Y
        d = x - FLAT_UNTIL

        # Hills get bigger the further you go
        amp = HILL_AMP_START + (HILL_AMP_MAX - HILL_AMP_START) * min(1.0, d / HILL_GROWTH_DIST)
        # Ease in from the flat start (smoothstep, so no bump or cliff)
        if d < HILL_FADE_IN:
            t = d / HILL_FADE_IN
            amp *= t * t * (3 - 2 * t)
        # Alternate calmer and wilder stretches
        amp *= 0.75 + 0.25 * math.sin(d * 0.004 + self.p4)

        h = (0.6 * math.sin(d * self.f1 + self.p1)
             + 0.3 * math.sin(d * self.f2 + self.p2)
             + 0.1 * math.sin(d * self.f3 + self.p3))
        return TERRAIN_BASE_Y - amp * h

    def _get_available_piece(self):
        """Find a piece far enough behind to reuse"""
        cleanup_x = self.furthest_x - SCREEN_WIDTH - 120
        for i in range(TERRAIN_POOL_SIZE):
            if self.piece_end[i] < cleanup_x:
                return i
        return -1

    def generate_segment(self):
        """Place the next straight piece of ground. Returns False if none are free."""
        idx = self._get_available_piece()
        if idx == -1:
            return False

        # Each piece runs exactly between two points on the curve, so pieces always meet
        x0 = self.next_x
        x1 = x0 + SEGMENT_STEP
        y0 = self._get_terrain_height(x0)
        y1 = self._get_terrain_height(x1)
        dx = x1 - x0
        dy = y1 - y0
        angle = -math.atan2(dy, dx)  # Negated for the engine's rotation direction

        strip, grass = self.strips[idx]
        strip.width = math.sqrt(dx * dx + dy * dy) + 2
        grass.width = strip.width
        strip.rotation = angle
        # Centre the strip half its thickness below the curve, perpendicular to the slope
        half = GROUND_BAND / 2
        strip.position = Vector2((x0 + x1) / 2 + half * math.sin(angle),
                                 (y0 + y1) / 2 + half * math.cos(angle))

        column = self.columns[idx]
        column.width = dx + 2
        column.position = Vector2((x0 + x1) / 2, max(y0, y1) + column.height / 2)

        self.piece_end[idx] = x1
        self.next_x = x1
        return True

    def update(self, camera_x):
        """Generate new ground ahead of camera"""
        if camera_x > self.furthest_x:
            self.furthest_x = camera_x
        while self.next_x < camera_x + SCREEN_WIDTH:
            if not self.generate_segment():
                break  # No free piece, try again next frame

    def get_ground_y_at(self, x):
        """Get ground Y position at x coordinate"""
        return self._get_terrain_height(x)

    def get_slope_at(self, x):
        """Ground steepness at x (dy/dx, positive = downhill)"""
        return (self._get_terrain_height(x + 1) - self._get_terrain_height(x - 1)) / 2

    def reset(self):
        """Reset terrain for new game"""
        self._new_hill_shape()
        self.next_x = -SCREEN_WIDTH
        self.furthest_x = 0

        for i in range(TERRAIN_POOL_SIZE):
            self.strips[i][0].position = Vector2(-9999, -9999)
            self.columns[i].position = Vector2(-9999, -9999)
            self.piece_end[i] = -9999

        # Generate initial terrain
        self.update(0)


# === Car Class ===
class Car:
    """Hill climb car with two wheels"""

    def __init__(self):
        # Track position manually (no parent-child relationship)
        self.x = 0
        self.y = -30
        self.rotation = 0

        # Car visual body (red car)
        self.visual = Rectangle2DNode()
        self.visual.width = CAR_WIDTH
        self.visual.height = CAR_HEIGHT
        self.visual.color = engine_draw.red
        self.visual.layer = 7

        # Windshield
        self.windshield = Rectangle2DNode()
        self.windshield.width = 6
        self.windshield.height = 5
        self.windshield.color = engine_draw.cyan
        self.windshield.layer = 8

        # Front wheel
        self.front_wheel = Circle2DNode()
        self.front_wheel.radius = WHEEL_RADIUS
        self.front_wheel.color = engine_draw.darkgrey
        self.front_wheel.layer = 6

        # Front wheel hub
        self.front_hub = Circle2DNode()
        self.front_hub.radius = 2
        self.front_hub.color = engine_draw.lightgrey
        self.front_hub.layer = 7

        # Rear wheel
        self.rear_wheel = Circle2DNode()
        self.rear_wheel.radius = WHEEL_RADIUS
        self.rear_wheel.color = engine_draw.darkgrey
        self.rear_wheel.layer = 6

        # Rear wheel hub
        self.rear_hub = Circle2DNode()
        self.rear_hub.radius = 2
        self.rear_hub.color = engine_draw.lightgrey
        self.rear_hub.layer = 7

        self.wheel_rotation = 0
        self.target_rotation = 0
        self.grounded = False
        self.air_frames = 0
        self.fuel = MAX_FUEL
        self.distance = 0
        self.max_distance = 0
        self.alive = True
        # Manual velocity tracking
        self.vel_x = 0
        self.vel_y = 0

    def sync_visuals(self):
        """Move all visual elements to match car position"""
        x = self.x
        y = self.y

        # Main body
        self.visual.position.x = x
        self.visual.position.y = y
        self.visual.rotation = self.rotation

        # Offsets are rotated the same way the engine rotates the body
        # (positive rotation = counter-clockwise on screen, so the nose lifts uphill)
        c = math.cos(self.rotation)
        s = math.sin(self.rotation)

        # Windshield at (4, -4) relative to body
        self.windshield.position.x = x + 4 * c + (-4) * s
        self.windshield.position.y = y - 4 * s + (-4) * c
        self.windshield.rotation = self.rotation

        # Front wheel at (7, 6) relative to body
        self.front_wheel.position.x = x + 7 * c + 6 * s
        self.front_wheel.position.y = y - 7 * s + 6 * c

        # Rear wheel at (-7, 6) relative to body
        self.rear_wheel.position.x = x + (-7) * c + 6 * s
        self.rear_wheel.position.y = y - (-7) * s + 6 * c

        # Wheel hubs (same position as wheels with slight animation)
        hub_offset_x = 2 * math.cos(self.wheel_rotation) * 0.3
        hub_offset_y = 2 * math.sin(self.wheel_rotation) * 0.3
        self.front_hub.position.x = self.front_wheel.position.x + hub_offset_x
        self.front_hub.position.y = self.front_wheel.position.y + hub_offset_y
        self.rear_hub.position.x = self.rear_wheel.position.x + hub_offset_x
        self.rear_hub.position.y = self.rear_wheel.position.y + hub_offset_y

    def update(self, terrain):
        """Update car physics and state"""
        if not self.alive:
            return False


        # Move, with gravity always pulling down
        self.vel_y += GRAVITY_Y
        self.x += self.vel_x
        self.y += self.vel_y

        ground_y = terrain.get_ground_y_at(self.x)
        target_y = ground_y - CAR_HEIGHT / 2 - WHEEL_RADIUS

        if self.y >= target_y:
            slope = terrain.get_slope_at(self.x)
            terrain_angle = -math.atan(slope)

            # Landing upside down or nose-first after a jump wrecks the car
            if self.air_frames > AIR_GRACE and abs(self.rotation - terrain_angle) > LANDING_MAX_ANGLE:
                self.alive = False
                return False

            self.grounded = True
            self.air_frames = 0
            self.y = target_y
            # Move along the ground; going over a crest fast launches the car
            self.vel_y = slope * self.vel_x
            self.target_rotation = terrain_angle
            # Uphill slows the car, downhill speeds it up
            self.vel_x += GRAVITY_Y * SLOPE_PULL * slope / math.sqrt(1 + slope * slope)
            # Rolling friction
            self.vel_x *= 0.99
            self.vel_x = max(-MAX_VELOCITY * 1.3, min(MAX_VELOCITY * 1.3, self.vel_x))
        else:
            self.air_frames += 1
            # Tiny hops over bumps still count as on the ground
            self.grounded = self.air_frames <= AIR_GRACE

        # Smooth rotation
        rot_diff = self.target_rotation - self.rotation
        self.rotation = self.rotation + rot_diff * ROTATION_SMOOTHING

        # Update wheel rotation based on velocity
        self.wheel_rotation += self.vel_x / WHEEL_RADIUS * 0.3

        # Sync all visual elements to new position
        self.sync_visuals()

        # Update distance
        if self.x > self.max_distance:
            self.max_distance = self.x
        self.distance = max(0, int(self.x / 10))

        # Check for death (flipped over or fell)
        if abs(self.rotation) > 2.5:  # ~143 degrees
            self.alive = False
            return False

        # Check for out of fuel
        if self.fuel <= 0:
            self.alive = False
            return False

        return True

    def accelerate(self, forward=True):
        """Apply motor force"""
        if not self.grounded or self.fuel <= 0:
            return

        # Consume fuel
        self.fuel -= FUEL_CONSUMPTION

        # Push along the ground (the ground sets vertical speed)
        force = MOTOR_POWER if forward else -MOTOR_POWER
        self.vel_x += force * math.cos(self.rotation)

        # Motor can't push past top speed (hills can still speed you up a bit)
        if abs(self.vel_x) > MAX_VELOCITY and (self.vel_x > 0) == forward:
            self.vel_x -= force * math.cos(self.rotation)

    def brake(self):
        """Apply braking force"""
        # Reduce velocity
        self.vel_x *= (1.0 - BRAKE_POWER)

    def add_fuel(self, amount):
        """Add fuel pickup"""
        self.fuel = min(MAX_FUEL, self.fuel + amount)

    def reset(self):
        """Reset car for new game"""
        # Calculate starting Y position on the ground
        ground_y = 30  # Flat terrain height at x=0
        start_y = ground_y - CAR_HEIGHT / 2 - WHEEL_RADIUS
        self.x = 0
        self.y = start_y
        self.rotation = 0
        self.target_rotation = 0
        self.wheel_rotation = 0
        self.grounded = True  # Start grounded since we're on the terrain
        self.air_frames = 0
        self.fuel = MAX_FUEL
        self.distance = 0
        self.max_distance = 0
        self.alive = True
        # Reset manual velocity
        self.vel_x = 0
        self.vel_y = 0
        self.show()
        self.sync_visuals()

    def show(self):
        self.visual.opacity = 1.0
        self.windshield.opacity = 1.0
        self.front_wheel.opacity = 1.0
        self.rear_wheel.opacity = 1.0
        self.front_hub.opacity = 1.0
        self.rear_hub.opacity = 1.0

    def hide(self):
        self.visual.opacity = 0
        self.windshield.opacity = 0
        self.front_wheel.opacity = 0
        self.rear_wheel.opacity = 0
        self.front_hub.opacity = 0
        self.rear_hub.opacity = 0
        self.x = 0
        self.y = -200
        self.sync_visuals()


# === Sky Background ===
class Sky:
    """Gradient sky background"""

    def __init__(self):
        self.layers = []
        colors = [
            engine_draw.blue,
            engine_draw.cyan,
            engine_draw.lightgrey,
        ]

        for i, color in enumerate(colors):
            layer = Rectangle2DNode()
            layer.width = SCREEN_WIDTH + 50
            layer.height = 50
            layer.color = color
            layer.layer = 0
            layer.position = Vector2(0, -64 + i * 40)
            layer.opacity = 0.6
            self.layers.append(layer)

    def update(self, camera_x, camera_y):
        for i, layer in enumerate(self.layers):
            layer.position.x = camera_x
            layer.position.y = camera_y - 64 + i * 40


# === Fuel Canister ===
class FuelCanister:
    """Collectible fuel pickup"""

    def __init__(self):
        self.body = Rectangle2DNode()
        self.body.width = 8
        self.body.height = 12
        self.body.color = engine_draw.yellow
        self.body.layer = 5

        self.cap = Rectangle2DNode()
        self.cap.width = 4
        self.cap.height = 3
        self.cap.color = engine_draw.red
        self.cap.position = Vector2(0, -7)
        self.cap.layer = 6
        self.body.add_child(self.cap)

        self.active = False
        self.x = 0

    def spawn(self, x, y):
        self.x = x
        self.body.position = Vector2(x, y - 8)
        self.active = True
        self.body.opacity = 1.0
        self.cap.opacity = 1.0

    def check_collect(self, car_x, car_y):
        if not self.active:
            return False

        dx = abs(car_x - self.x)
        dy = abs(car_y - self.body.position.y)

        if dx < 15 and dy < 15:
            self.active = False
            self.body.opacity = 0
            self.cap.opacity = 0
            return True
        return False

    def hide(self):
        self.active = False
        self.body.opacity = 0
        self.cap.opacity = 0
        self.body.position = Vector2(-9999, -9999)


# === UI Elements ===
UI_LAYER = 10

# Title screen
title_text = Text2DNode()
title_text.text = "HILL CLIMB"
title_text.position = Vector2(8, -40)
title_text.color = engine_draw.red
title_text.layer = UI_LAYER

subtitle_text = Text2DNode()
subtitle_text.text = "Racing"
subtitle_text.position = Vector2(30, -25)
subtitle_text.color = engine_draw.white
subtitle_text.layer = UI_LAYER

high_score_text = Text2DNode()
high_score_text.text = "Best: " + str(high_score) + "m"
high_score_text.position = Vector2(20, 0)
high_score_text.color = engine_draw.gold
high_score_text.layer = UI_LAYER

controls_text = Text2DNode()
controls_text.text = "A=Gas B=Brake"
controls_text.position = Vector2(10, 15)
controls_text.color = engine_draw.lightgrey
controls_text.layer = UI_LAYER

start_text = Text2DNode()
start_text.text = "Press A to Start"
start_text.position = Vector2(-5, 40)
start_text.color = engine_draw.white
start_text.layer = UI_LAYER

# In-game HUD
distance_text = Text2DNode()
distance_text.text = "0m"
distance_text.position = Vector2(-55, -55)
distance_text.color = engine_draw.white
distance_text.opacity = 0
distance_text.layer = UI_LAYER

# Fuel bar background
fuel_bar_bg = Rectangle2DNode()
fuel_bar_bg.width = 40
fuel_bar_bg.height = 6
fuel_bar_bg.color = engine_draw.darkgrey
fuel_bar_bg.position = Vector2(35, -55)
fuel_bar_bg.opacity = 0
fuel_bar_bg.layer = UI_LAYER

# Fuel bar fill
fuel_bar = Rectangle2DNode()
fuel_bar.width = 40
fuel_bar.height = 6
fuel_bar.color = engine_draw.yellow
fuel_bar.position = Vector2(35, -55)
fuel_bar.opacity = 0
fuel_bar.layer = UI_LAYER

# Fuel icon
fuel_icon = Text2DNode()
fuel_icon.text = "F"
fuel_icon.position = Vector2(10, -55)
fuel_icon.color = engine_draw.yellow
fuel_icon.opacity = 0
fuel_icon.layer = UI_LAYER

# Speed indicator
speed_text = Text2DNode()
speed_text.text = "0"
speed_text.position = Vector2(-55, -45)
speed_text.color = engine_draw.cyan
speed_text.opacity = 0
speed_text.layer = UI_LAYER

# Death screen
death_text = Text2DNode()
death_text.text = "WRECKED!"
death_text.position = Vector2(5, -25)
death_text.color = engine_draw.red
death_text.opacity = 0
death_text.layer = UI_LAYER

final_score_text = Text2DNode()
final_score_text.text = "Distance: 0m"
final_score_text.position = Vector2(5, 0)
final_score_text.color = engine_draw.white
final_score_text.opacity = 0
final_score_text.layer = UI_LAYER

new_record_text = Text2DNode()
new_record_text.text = "NEW RECORD!"
new_record_text.position = Vector2(5, -40)
new_record_text.color = engine_draw.gold
new_record_text.opacity = 0
new_record_text.layer = UI_LAYER

restart_text = Text2DNode()
restart_text.text = "Press A to Retry"
restart_text.position = Vector2(-5, 35)
restart_text.color = engine_draw.white
restart_text.opacity = 0
restart_text.layer = UI_LAYER

out_of_fuel_text = Text2DNode()
out_of_fuel_text.text = "OUT OF FUEL!"
out_of_fuel_text.position = Vector2(5, 15)
out_of_fuel_text.color = engine_draw.orange
out_of_fuel_text.opacity = 0
out_of_fuel_text.layer = UI_LAYER


# === Create Game Objects ===
terrain = TerrainManager()
car = Car()
sky = Sky()
fuel_canisters = [FuelCanister() for _ in range(3)]

# === Game State ===
state = STATE_TITLE
input_cooldown = 0
last_fuel_distance = 0


# === Helper Functions ===
def show_title():
    title_text.opacity = 1.0
    subtitle_text.opacity = 1.0
    high_score_text.opacity = 1.0
    high_score_text.text = "Best: " + str(high_score) + "m"
    controls_text.opacity = 1.0
    start_text.opacity = 1.0

    distance_text.opacity = 0
    fuel_bar_bg.opacity = 0
    fuel_bar.opacity = 0
    fuel_icon.opacity = 0
    speed_text.opacity = 0
    death_text.opacity = 0
    final_score_text.opacity = 0
    new_record_text.opacity = 0
    restart_text.opacity = 0
    out_of_fuel_text.opacity = 0

    car.hide()
    for fc in fuel_canisters:
        fc.hide()


def show_playing():
    title_text.opacity = 0
    subtitle_text.opacity = 0
    high_score_text.opacity = 0
    controls_text.opacity = 0
    start_text.opacity = 0

    distance_text.opacity = 1.0
    fuel_bar_bg.opacity = 1.0
    fuel_bar.opacity = 1.0
    fuel_icon.opacity = 1.0
    speed_text.opacity = 1.0

    death_text.opacity = 0
    final_score_text.opacity = 0
    new_record_text.opacity = 0
    restart_text.opacity = 0
    out_of_fuel_text.opacity = 0


def show_death(out_of_fuel=False):
    if out_of_fuel:
        death_text.text = "OUT OF GAS!"
        out_of_fuel_text.opacity = 0
    else:
        death_text.text = "WRECKED!"

    death_text.opacity = 1.0
    final_score_text.opacity = 1.0
    restart_text.opacity = 1.0

    fuel_bar_bg.opacity = 0
    fuel_bar.opacity = 0
    fuel_icon.opacity = 0
    speed_text.opacity = 0


def spawn_fuel_canister(x):
    """Spawn a fuel canister at given x position"""
    for fc in fuel_canisters:
        if not fc.active:
            y = terrain.get_ground_y_at(x)
            fc.spawn(x, y)
            return


def start_game():
    global state, last_fuel_distance

    terrain.reset()
    car.reset()
    camera.position.x = 0
    camera.position.y = 0
    last_fuel_distance = 0

    # Hide all fuel canisters
    for fc in fuel_canisters:
        fc.hide()

    # Spawn initial fuel canisters
    spawn_fuel_canister(150)
    spawn_fuel_canister(350)

    state = STATE_PLAYING
    show_playing()


# === Initialize ===
show_title()
terrain.reset()


# === Main Game Loop ===
while True:
    if engine.tick():
        if input_cooldown > 0:
            input_cooldown -= 1

        # Update sky background
        sky.update(camera.position.x, camera.position.y)

        if state == STATE_TITLE:
            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                start_game()
                input_cooldown = 15

        elif state == STATE_PLAYING:
            # Handle input
            if engine_io.A.is_pressed:
                car.accelerate(forward=True)
            elif engine_io.B.is_pressed:
                car.brake()

            # Tilt controls for rotation in air
            if engine_io.LEFT.is_pressed and not car.grounded:
                car.rotation -= 0.05
                car.target_rotation = car.rotation
            elif engine_io.RIGHT.is_pressed and not car.grounded:
                car.rotation += 0.05
                car.target_rotation = car.rotation

            # Update car
            out_of_fuel = car.fuel <= 0
            if not car.update(terrain):
                # Death!
                state = STATE_DEAD
                score = car.distance
                final_score_text.text = "Distance: " + str(score) + "m"

                # Check for new high score
                is_new_record = False
                if score > high_score:
                    high_score = score
                    engine_save.save("high_score", high_score)
                    is_new_record = True
                    new_record_text.opacity = 1.0

                show_death(out_of_fuel)
                input_cooldown = 30

            # Camera follow
            target_x = car.x + 20
            target_y = car.y - 10
            camera.position.x += (target_x - camera.position.x) * 0.1
            camera.position.y += (target_y - camera.position.y) * 0.08

            # Update terrain
            terrain.update(camera.position.x)

            # Check fuel canister collection
            for fc in fuel_canisters:
                if fc.check_collect(car.x, car.y):
                    car.add_fuel(25)
                elif fc.active and fc.x < car.x - 150:
                    fc.hide()  # Missed it, free it up for a new one ahead

            # Spawn new fuel canisters periodically
            current_dist = int(car.x)
            fuel_spacing = min(FUEL_SPACING_MAX, FUEL_SPACING_START + current_dist * FUEL_SPACING_GROWTH)
            if current_dist - last_fuel_distance > fuel_spacing:
                spawn_fuel_canister(current_dist + 100 + urandom.getrandbits(6))
                last_fuel_distance = current_dist

            # Update HUD
            distance_text.text = str(car.distance) + "m"
            distance_text.position.x = camera.position.x - 55
            distance_text.position.y = camera.position.y - 55

            # Update fuel bar
            fuel_ratio = car.fuel / MAX_FUEL
            fuel_bar.width = max(1, int(40 * fuel_ratio))
            fuel_bar.position.x = camera.position.x + 35 - (40 - fuel_bar.width) / 2
            fuel_bar.position.y = camera.position.y - 55
            fuel_bar_bg.position.x = camera.position.x + 35
            fuel_bar_bg.position.y = camera.position.y - 55
            fuel_icon.position.x = camera.position.x + 10
            fuel_icon.position.y = camera.position.y - 55

            # Fuel bar color based on amount
            if fuel_ratio > 0.5:
                fuel_bar.color = engine_draw.green
            elif fuel_ratio > 0.25:
                fuel_bar.color = engine_draw.yellow
            else:
                fuel_bar.color = engine_draw.red

            # Speed display
            speed = abs(car.vel_x)
            speed_text.text = str(int(speed * 30)) + "km/h"
            speed_text.position.x = camera.position.x - 55
            speed_text.position.y = camera.position.y - 45

        elif state == STATE_DEAD:
            # Keep HUD centered on camera
            death_text.position.x = camera.position.x + 5
            death_text.position.y = camera.position.y - 25
            final_score_text.position.x = camera.position.x + 5
            final_score_text.position.y = camera.position.y
            new_record_text.position.x = camera.position.x + 5
            new_record_text.position.y = camera.position.y - 40
            restart_text.position.x = camera.position.x - 5
            restart_text.position.y = camera.position.y + 35
            distance_text.position.x = camera.position.x - 55
            distance_text.position.y = camera.position.y - 55

            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                start_game()
                input_cooldown = 15

        # Exit on MENU
        if engine_io.MENU.is_just_pressed:
            engine_save.save("high_score", high_score)
            engine.end()
            break
