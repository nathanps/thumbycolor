import engine_main
import engine
import engine_draw
import engine_io
import engine_physics
import engine_save
from engine_nodes import (Rectangle2DNode, Text2DNode, CameraNode,
                          Circle2DNode, PhysicsRectangle2DNode,
                          PhysicsCircle2DNode)
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
GRAVITY_Y = 0.15  # Downward gravity

# Car physics
CAR_WIDTH = 22
CAR_HEIGHT = 10
WHEEL_RADIUS = 5
MOTOR_POWER = 0.08
BRAKE_POWER = 0.12
MAX_VELOCITY = 3.0
ROTATION_SMOOTHING = 0.15

# Terrain generation
SEGMENT_WIDTH = 20
TERRAIN_AMPLITUDE = 25  # Max hill height variation
TERRAIN_FREQUENCY = 0.08  # How often hills occur
TERRAIN_POOL_SIZE = 20

# Fuel system
MAX_FUEL = 100
FUEL_CONSUMPTION = 0.15  # Per frame when accelerating
FUEL_BONUS_DISTANCE = 200  # Get fuel bonus every this many units

# === Save System ===
engine_save._init_saves_dir("Saves/Games/HillClimb")
engine_save.set_location("save")
high_score = engine_save.load("high_score", 0)

# === Engine Setup ===
engine.fps_limit(60)
engine_physics.set_gravity(GRAVITY_X, GRAVITY_Y)

# === Camera ===
camera = CameraNode()


# === Terrain Manager ===
class TerrainManager:
    """Generates procedural hilly terrain similar to Hill Climb Racing"""

    def __init__(self):
        self.segments = []  # Physics bodies
        self.visuals = []   # Visual rectangles
        self.segment_data = []  # Position and height data
        self.next_x = -SCREEN_WIDTH
        self.seed = 0
        self.difficulty = 1.0  # Increases over distance
        self._create_pool()

    def _create_pool(self):
        """Pre-create terrain segment objects"""
        for _ in range(TERRAIN_POOL_SIZE):
            physics = PhysicsRectangle2DNode()
            physics.width = SEGMENT_WIDTH + 4  # Overlap slightly
            physics.height = 15
            physics.dynamic = False
            physics.bounciness = 0.1
            physics.friction = 0.9
            physics.position = Vector2(-9999, -9999)

            # Green grass top
            grass = Rectangle2DNode()
            grass.width = SEGMENT_WIDTH + 4
            grass.height = 5
            grass.color = engine_draw.green
            grass.position = Vector2(0, -5)
            grass.layer = 5
            physics.add_child(grass)

            # Brown dirt
            dirt = Rectangle2DNode()
            dirt.width = SEGMENT_WIDTH + 4
            dirt.height = 10
            dirt.color = engine_draw.brown
            dirt.position = Vector2(0, 2)
            dirt.layer = 4
            physics.add_child(dirt)

            self.segments.append(physics)
            self.visuals.append((grass, dirt))
            self.segment_data.append({'x': -9999, 'y': 0, 'active': False})

    def _get_terrain_height(self, x):
        """Generate terrain height using layered sine waves (pseudo-Perlin)"""
        # Flat starting area
        if x < 100:
            return 30

        # Mix of sine waves at different frequencies for natural-looking terrain
        adjusted_x = x - 100

        # Primary hill shape
        h1 = math.sin(adjusted_x * TERRAIN_FREQUENCY * 0.5) * TERRAIN_AMPLITUDE
        # Secondary variation
        h2 = math.sin(adjusted_x * TERRAIN_FREQUENCY * 1.3 + 1.5) * TERRAIN_AMPLITUDE * 0.5
        # Small bumps
        h3 = math.sin(adjusted_x * TERRAIN_FREQUENCY * 3.7 + 0.7) * TERRAIN_AMPLITUDE * 0.2

        # Random variation based on position (deterministic)
        seed_val = int(adjusted_x / SEGMENT_WIDTH) + self.seed
        urandom.seed(seed_val)
        random_offset = (urandom.getrandbits(4) - 8) * self.difficulty * 0.3

        # Increase difficulty (steeper hills) over distance
        self.difficulty = 1.0 + (adjusted_x / 1000.0) * 0.5

        base_height = 30
        return base_height + (h1 + h2 + h3 + random_offset) * min(self.difficulty, 2.0)

    def _get_terrain_angle(self, x):
        """Calculate terrain angle at position x"""
        h1 = self._get_terrain_height(x - 5)
        h2 = self._get_terrain_height(x + 5)
        return math.atan2(h2 - h1, 10)

    def _get_available_segment(self, camera_x):
        """Find a segment off-screen left for reuse"""
        cleanup_x = camera_x - SCREEN_WIDTH - 50
        for i, data in enumerate(self.segment_data):
            if not data['active'] or data['x'] < cleanup_x:
                return i
        return -1

    def generate_segment(self, camera_x):
        """Generate next terrain segment"""
        x = self.next_x
        y = self._get_terrain_height(x)
        angle = self._get_terrain_angle(x)

        idx = self._get_available_segment(camera_x)
        if idx == -1:
            return

        physics = self.segments[idx]
        physics.position = Vector2(x, y)
        physics.rotation = angle

        # Update visuals
        grass, dirt = self.visuals[idx]

        self.segment_data[idx] = {'x': x, 'y': y, 'active': True}
        self.next_x = x + SEGMENT_WIDTH - 2

    def update(self, camera_x):
        """Generate new segments ahead of camera"""
        while self.next_x < camera_x + SCREEN_WIDTH * 2:
            self.generate_segment(camera_x)

    def get_ground_y_at(self, x):
        """Get ground Y position at x coordinate"""
        return self._get_terrain_height(x)

    def get_angle_at(self, x):
        """Get ground angle at x coordinate"""
        return self._get_terrain_angle(x)

    def reset(self):
        """Reset terrain for new game"""
        self.seed = urandom.getrandbits(16)
        self.next_x = -SCREEN_WIDTH
        self.difficulty = 1.0

        for i in range(TERRAIN_POOL_SIZE):
            self.segments[i].position = Vector2(-9999, -9999)
            self.segment_data[i] = {'x': -9999, 'y': 0, 'active': False}

        # Generate initial terrain
        for _ in range(12):
            self.generate_segment(0)


# === Car Class ===
class Car:
    """Hill climb car with two wheels"""

    def __init__(self):
        # Car body (physics)
        self.body = PhysicsRectangle2DNode()
        self.body.width = CAR_WIDTH
        self.body.height = CAR_HEIGHT
        self.body.dynamic = True
        self.body.bounciness = 0.2
        self.body.density = 1.5
        self.body.friction = 0.3
        self.body.position = Vector2(0, -30)
        self.body.layer = 6

        # Car visual body (red car)
        self.visual = Rectangle2DNode()
        self.visual.width = CAR_WIDTH
        self.visual.height = CAR_HEIGHT
        self.visual.color = engine_draw.red
        self.visual.layer = 7
        self.body.add_child(self.visual)

        # Windshield
        self.windshield = Rectangle2DNode()
        self.windshield.width = 6
        self.windshield.height = 5
        self.windshield.color = engine_draw.cyan
        self.windshield.position = Vector2(4, -4)
        self.windshield.layer = 8
        self.body.add_child(self.windshield)

        # Front wheel (visual only - positioned relative to body)
        self.front_wheel = Circle2DNode()
        self.front_wheel.radius = WHEEL_RADIUS
        self.front_wheel.color = engine_draw.darkgrey
        self.front_wheel.position = Vector2(7, 6)
        self.front_wheel.layer = 6
        self.body.add_child(self.front_wheel)

        # Front wheel hub
        self.front_hub = Circle2DNode()
        self.front_hub.radius = 2
        self.front_hub.color = engine_draw.lightgrey
        self.front_hub.position = Vector2(7, 6)
        self.front_hub.layer = 7
        self.body.add_child(self.front_hub)

        # Rear wheel (visual only)
        self.rear_wheel = Circle2DNode()
        self.rear_wheel.radius = WHEEL_RADIUS
        self.rear_wheel.color = engine_draw.darkgrey
        self.rear_wheel.position = Vector2(-7, 6)
        self.rear_wheel.layer = 6
        self.body.add_child(self.rear_wheel)

        # Rear wheel hub
        self.rear_hub = Circle2DNode()
        self.rear_hub.radius = 2
        self.rear_hub.color = engine_draw.lightgrey
        self.rear_hub.position = Vector2(-7, 6)
        self.rear_hub.layer = 7
        self.body.add_child(self.rear_hub)

        self.wheel_rotation = 0
        self.target_rotation = 0
        self.grounded = False
        self.fuel = MAX_FUEL
        self.distance = 0
        self.max_distance = 0
        self.alive = True

    def update(self, terrain):
        """Update car physics and state"""
        if not self.alive:
            return False

        # Get current position
        x = self.body.position.x
        y = self.body.position.y

        # Check if on ground
        ground_y = terrain.get_ground_y_at(x)
        car_bottom = y + CAR_HEIGHT / 2 + WHEEL_RADIUS

        self.grounded = car_bottom >= ground_y - 5

        # Align car rotation to terrain when grounded
        if self.grounded:
            terrain_angle = terrain.get_angle_at(x)
            self.target_rotation = terrain_angle

            # Keep car on ground
            target_y = ground_y - CAR_HEIGHT / 2 - WHEEL_RADIUS
            self.body.position = Vector2(x, min(y, target_y + 2))

        # Smooth rotation
        current_rot = self.body.rotation
        rot_diff = self.target_rotation - current_rot
        self.body.rotation = current_rot + rot_diff * ROTATION_SMOOTHING

        # Update wheel rotation based on velocity
        vel_x = self.body.velocity.x
        self.wheel_rotation += vel_x / WHEEL_RADIUS * 0.3

        # Visual wheel rotation (rotate the hubs to show movement)
        hub_offset_x = 2 * math.cos(self.wheel_rotation)
        hub_offset_y = 2 * math.sin(self.wheel_rotation)
        self.front_hub.position = Vector2(7 + hub_offset_x * 0.3, 6 + hub_offset_y * 0.3)
        self.rear_hub.position = Vector2(-7 + hub_offset_x * 0.3, 6 + hub_offset_y * 0.3)

        # Update distance
        if x > self.max_distance:
            self.max_distance = x
        self.distance = max(0, int(x / 10))

        # Check for death (flipped over or fell)
        if abs(self.body.rotation) > 2.5:  # ~143 degrees
            self.alive = False
            return False

        if y > 100:  # Fell off screen
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

        # Calculate force direction based on car rotation
        angle = self.body.rotation
        force = MOTOR_POWER if forward else -MOTOR_POWER

        # Apply force in direction car is facing
        fx = force * math.cos(angle)
        fy = force * math.sin(angle)

        vel = self.body.velocity
        new_vx = vel.x + fx
        new_vy = vel.y + fy

        # Cap velocity
        speed = math.sqrt(new_vx * new_vx + new_vy * new_vy)
        if speed > MAX_VELOCITY:
            scale = MAX_VELOCITY / speed
            new_vx *= scale
            new_vy *= scale

        self.body.velocity = Vector2(new_vx, new_vy)

    def brake(self):
        """Apply braking force"""
        vel = self.body.velocity
        # Reduce velocity
        new_vx = vel.x * (1.0 - BRAKE_POWER)
        self.body.velocity = Vector2(new_vx, vel.y)

    def add_fuel(self, amount):
        """Add fuel pickup"""
        self.fuel = min(MAX_FUEL, self.fuel + amount)

    def reset(self):
        """Reset car for new game"""
        self.body.position = Vector2(0, -30)
        self.body.velocity = Vector2(0, 0)
        self.body.rotation = 0
        self.target_rotation = 0
        self.wheel_rotation = 0
        self.grounded = False
        self.fuel = MAX_FUEL
        self.distance = 0
        self.max_distance = 0
        self.alive = True
        self.show()

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
        self.body.position = Vector2(0, -200)


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

    def update(self, camera_x):
        for layer in self.layers:
            layer.position.x = camera_x


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
        self.body.position = Vector2(x, y - 15)
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
    camera.position = Vector2(0, 0)
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
        sky.update(camera.position.x)

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
                car.body.rotation -= 0.05
                car.target_rotation = car.body.rotation
            elif engine_io.RIGHT.is_pressed and not car.grounded:
                car.body.rotation += 0.05
                car.target_rotation = car.body.rotation

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
            target_x = car.body.position.x + 20
            target_y = car.body.position.y - 10
            camera.position.x += (target_x - camera.position.x) * 0.1
            camera.position.y += (target_y - camera.position.y) * 0.05

            # Clamp camera Y
            camera.position.y = max(-30, min(20, camera.position.y))

            # Update terrain
            terrain.update(camera.position.x)

            # Check fuel canister collection
            for fc in fuel_canisters:
                if fc.check_collect(car.body.position.x, car.body.position.y):
                    car.add_fuel(25)

            # Spawn new fuel canisters periodically
            current_dist = int(car.body.position.x)
            if current_dist - last_fuel_distance > FUEL_BONUS_DISTANCE:
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
            speed = abs(car.body.velocity.x)
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
