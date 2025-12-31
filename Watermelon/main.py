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

# === Physics Constants ===
WATERMELON_RADIUS = 8
GROUND_SEGMENT_WIDTH = 40
GROUND_HEIGHT = 10
SCREEN_WIDTH = 128
SCREEN_HEIGHT = 128
GROUND_Y_BASE = 40

# Gravity settings (negative Y = downward, 10x lighter)
GRAVITY_NEUTRAL_X = 0
GRAVITY_NEUTRAL_Y = -0.1
GRAVITY_TILT_X = 0.19  # Max tilt
GRAVITY_TILT_Y = -0.08
TILT_SPEED = 0.02  # How fast tilt changes

# Death threshold - vertical velocity that causes splat (lower for lighter gravity)
DEATH_VELOCITY_THRESHOLD = 1.5

# Jump force
JUMP_FORCE = 2

# Max horizontal velocity
MAX_VELOCITY_X = 2.0

# Gap settings - base values that scale with distance
GAP_WIDTH_MIN_BASE = 20
GAP_WIDTH_MAX_BASE = 28
GAP_WIDTH_GROWTH = 0.015  # Gap grows by this much per unit of distance

# Ramp settings for smooth gap transitions
RAMP_LENGTH = 15
RAMP_ANGLE = 0.25  # Radians - steeper for clearer visual

# Bump settings
BUMP_HEIGHT = 8

# === Save System ===
engine_save._init_saves_dir("Saves/Games/Watermelon")
engine_save.set_location("save")
high_score = engine_save.load("high_score", 0)

# === Engine Setup ===
engine.fps_limit(60)
engine_physics.set_gravity(GRAVITY_NEUTRAL_X, GRAVITY_NEUTRAL_Y)

# === Camera ===
camera = CameraNode()

# === Watermelon Class ===
class Watermelon:
    def __init__(self):
        self.physics = PhysicsCircle2DNode()
        self.physics.radius = WATERMELON_RADIUS
        self.physics.dynamic = True
        self.physics.bounciness = 0.7
        self.physics.density = 0.8
        self.physics.position = Vector2(0, -20)
        self.physics.layer = 3  # In front of ground and mountains

        # Visual: Green circle body
        self.body = Circle2DNode()
        self.body.radius = WATERMELON_RADIUS
        self.body.color = engine_draw.green
        self.body.layer = 6  # In front of ground
        self.physics.add_child(self.body)

        # Dark green stripes
        self.stripe1 = Rectangle2DNode()
        self.stripe1.width = 2
        self.stripe1.height = WATERMELON_RADIUS * 2 - 4
        self.stripe1.color = engine_draw.darkgreen
        self.stripe1.position = Vector2(-3, 0)
        self.stripe1.layer = 6
        self.physics.add_child(self.stripe1)

        self.stripe2 = Rectangle2DNode()
        self.stripe2.width = 2
        self.stripe2.height = WATERMELON_RADIUS * 2 - 4
        self.stripe2.color = engine_draw.darkgreen
        self.stripe2.position = Vector2(3, 0)
        self.stripe2.layer = 6
        self.physics.add_child(self.stripe2)

        self.prev_velocity_y = 0
        self.alive = True
        self.rotation_angle = 0  # Track visual rotation
        self.jump_cooldown = 0  # Frames until can jump again

    def update(self):
        """Check for death condition and update visual rotation"""
        if not self.alive:
            return False

        current_vel_y = self.physics.velocity.y

        # Detect hard impact: was falling fast (negative Y), now stopped
        if self.prev_velocity_y < -DEATH_VELOCITY_THRESHOLD and abs(current_vel_y) < 0.5:
            self.alive = False
            return False

        # Decrement jump cooldown
        if self.jump_cooldown > 0:
            self.jump_cooldown -= 1

        self.prev_velocity_y = current_vel_y

        # Cap horizontal velocity
        vel_x = self.physics.velocity.x
        if abs(vel_x) > MAX_VELOCITY_X:
            capped_vel_x = MAX_VELOCITY_X if vel_x > 0 else -MAX_VELOCITY_X
            self.physics.velocity = Vector2(capped_vel_x, self.physics.velocity.y)
            vel_x = capped_vel_x

        # Update rolling rotation based on horizontal velocity
        # rotation = distance / radius, distance = velocity per frame
        self.rotation_angle -= vel_x / WATERMELON_RADIUS * 0.5

        # Apply rotation to stripes (body is a circle so doesn't need rotation)
        self.stripe1.rotation = self.rotation_angle
        self.stripe2.rotation = self.rotation_angle

        # Update stripe positions to rotate around center
        stripe_dist = 3
        self.stripe1.position = Vector2(
            -stripe_dist * math.cos(self.rotation_angle),
            -stripe_dist * math.sin(self.rotation_angle)
        )
        self.stripe2.position = Vector2(
            stripe_dist * math.cos(self.rotation_angle),
            stripe_dist * math.sin(self.rotation_angle)
        )

        return True

    def jump(self):
        """Apply upward jump force (negative Y = up) - 1 second cooldown"""
        if self.jump_cooldown > 0:
            return
        self.jump_cooldown = 60  # 1 second at 60 FPS
        current_vel_x = self.physics.velocity.x
        self.physics.velocity = Vector2(current_vel_x, -JUMP_FORCE)

    def reset(self, x_pos=0):
        self.physics.position = Vector2(x_pos, -20)
        self.physics.velocity = Vector2(0, 0)
        self.prev_velocity_y = 0
        self.alive = True
        self.rotation_angle = 0
        self.jump_cooldown = 0
        self.show()

    def show(self):
        self.body.opacity = 1.0
        self.stripe1.opacity = 1.0
        self.stripe2.opacity = 1.0

    def hide(self):
        self.body.opacity = 0
        self.stripe1.opacity = 0
        self.stripe2.opacity = 0
        self.physics.position = Vector2(0, -200)
        self.physics.velocity = Vector2(0, 0)

# === Ground Manager (Pooled) ===
GROUND_POOL_SIZE = 15  # Fixed pool of ground segments

class GroundManager:
    def __init__(self):
        self.pool = []  # Physics nodes
        self.pool_visuals = []  # Visual nodes
        self.pool_data = []  # Track x position and active state
        self.next_segment_x = -SCREEN_WIDTH // 2
        self.furthest_x = 0
        self.last_was_gap = False
        self.need_exit_ramp = False
        self.current_y = GROUND_Y_BASE
        self._create_pool()

    def _create_pool(self):
        """Pre-create all ground segment objects"""
        for _ in range(GROUND_POOL_SIZE):
            physics = PhysicsRectangle2DNode()
            physics.width = GROUND_SEGMENT_WIDTH
            physics.height = GROUND_HEIGHT
            physics.dynamic = False
            physics.bounciness = 0.2
            physics.friction = 0
            physics.position = Vector2(-9999, -9999)  # Off-screen initially
            visual = Rectangle2DNode()
            visual.width = GROUND_SEGMENT_WIDTH
            visual.height = GROUND_HEIGHT
            visual.color = engine_draw.darkgrey
            visual.layer = 5  # In front of mountains
            physics.add_child(visual)

            self.pool.append(physics)
            self.pool_visuals.append(visual)
            self.pool_data.append({'x': -9999, 'active': False})

    def _get_available_segment(self, camera_x):
        """Find a segment that's off-screen left and available for reuse"""
        cleanup_x = camera_x - SCREEN_WIDTH - 50
        for i, data in enumerate(self.pool_data):
            if not data['active'] or data['x'] < cleanup_x:
                return i
        return -1

    def _configure_segment(self, index, x, y, width, height, rotation, color):
        """Configure a pooled segment with new properties"""
        physics = self.pool[index]
        visual = self.pool_visuals[index]

        physics.position = Vector2(x, y)
        physics.width = width
        physics.height = height
        physics.rotation = rotation

        visual.width = width
        visual.height = height
        visual.color = color

        self.pool_data[index] = {'x': x, 'active': True}

    def get_gap_width(self):
        """Calculate gap width based on distance - gaps get larger as you progress"""
        distance_factor = max(0, self.furthest_x) * GAP_WIDTH_GROWTH
        gap_min = GAP_WIDTH_MIN_BASE + distance_factor
        gap_max = GAP_WIDTH_MAX_BASE + distance_factor
        gap_min = min(gap_min, 50)
        gap_max = min(gap_max, 65)
        gap_range = max(1, int(gap_max - gap_min))
        return int(gap_min) + (urandom.getrandbits(4) % gap_range)

    def generate_segment(self, camera_x):
        """Generate next ground segment using pooled objects"""
        x = self.next_segment_x
        y = self.current_y

        idx = self._get_available_segment(camera_x)
        if idx == -1:
            return  # No available segments

        # If we just came out of a gap, create an upward exit ramp
        if self.need_exit_ramp:
            self.need_exit_ramp = False
            ramp_y = y + 8
            self._configure_segment(idx, x, ramp_y, RAMP_LENGTH, GROUND_HEIGHT,
                                   -RAMP_ANGLE, engine_draw.lightgrey)
            self.next_segment_x = x + RAMP_LENGTH - 2
            return

        # Random height variation
        y_offset = (urandom.getrandbits(3) - 4)
        y = GROUND_Y_BASE + y_offset
        self.current_y = y

        # Don't allow consecutive gaps
        if self.last_was_gap:
            segment_type = urandom.getrandbits(4) % 9
        else:
            segment_type = urandom.getrandbits(4)

        self.last_was_gap = False

        if segment_type < 5:  # Flat ground
            self._configure_segment(idx, x, y, GROUND_SEGMENT_WIDTH, GROUND_HEIGHT,
                                   0, engine_draw.darkgrey)
            self.next_segment_x = x + GROUND_SEGMENT_WIDTH - 2

        elif segment_type < 6:  # Upward ramp
            self._configure_segment(idx, x, y - 3, GROUND_SEGMENT_WIDTH, GROUND_HEIGHT,
                                   -0.15, engine_draw.lightgrey)
            self.next_segment_x = x + GROUND_SEGMENT_WIDTH - 2

        elif segment_type < 7:  # Downward ramp
            self._configure_segment(idx, x, y + 3, GROUND_SEGMENT_WIDTH, GROUND_HEIGHT,
                                   0.15, engine_draw.lightgrey)
            self.next_segment_x = x + GROUND_SEGMENT_WIDTH - 2

        elif segment_type < 8:  # Elevated platform
            w = int(GROUND_SEGMENT_WIDTH * 0.7)
            self._configure_segment(idx, x, y - 15, w, GROUND_HEIGHT,
                                   0, engine_draw.white)
            self.next_segment_x = x + w - 2

        elif segment_type < 9:  # Dip/valley
            w = int(GROUND_SEGMENT_WIDTH * 0.5)
            self._configure_segment(idx, x, y + BUMP_HEIGHT, w, GROUND_HEIGHT,
                                   0, engine_draw.lightgrey)
            self.next_segment_x = x + w - 2

        else:  # Gap - create downward ramp first
            ramp_y = y + 4
            self._configure_segment(idx, x, ramp_y, RAMP_LENGTH, GROUND_HEIGHT,
                                   RAMP_ANGLE, engine_draw.lightgrey)
            gap_width = self.get_gap_width()
            self.next_segment_x = x + RAMP_LENGTH + gap_width
            self.last_was_gap = True
            self.need_exit_ramp = True

    def update(self, camera_x):
        """Generate new segments ahead"""
        while self.next_segment_x < camera_x + SCREEN_WIDTH * 1.5:
            self.generate_segment(camera_x)

        if camera_x > self.furthest_x:
            self.furthest_x = camera_x

    def reset(self):
        # Reset all pool segments to off-screen
        for i in range(GROUND_POOL_SIZE):
            self.pool[i].position = Vector2(-9999, -9999)
            self.pool_data[i] = {'x': -9999, 'active': False}

        self.next_segment_x = -SCREEN_WIDTH // 2
        self.furthest_x = 0
        self.last_was_gap = False
        self.need_exit_ramp = False
        self.current_y = GROUND_Y_BASE

        # Generate initial ground
        for _ in range(8):
            self.generate_segment(0)

    def get_distance_score(self):
        return max(0, int(self.furthest_x / 10))

# === Water (Visual only, below ground) ===
water = Rectangle2DNode()
water.width = SCREEN_WIDTH + 50  # Slightly wider than screen
water.height = 100  # Tall enough to fill bottom
water.color = engine_draw.blue
water.layer = 3  # In front of mountains (0), behind ground (5)
water.position = Vector2(0, 90)  # Below ground level

# === Left Wall ===
class LeftWall:
    def __init__(self):
        self.physics = PhysicsRectangle2DNode()
        self.physics.position = Vector2(-SCREEN_WIDTH, 0)
        self.physics.width = 10
        self.physics.height = SCREEN_HEIGHT * 3
        self.physics.dynamic = False
        self.physics.bounciness = 0.1

        self.visual = Rectangle2DNode()
        self.visual.width = 10
        self.visual.height = SCREEN_HEIGHT * 3
        self.visual.color = engine_draw.darkgrey
        self.physics.add_child(self.visual)

    def update(self, camera_x):
        """Keep wall just behind the camera"""
        self.physics.position.x = camera_x - SCREEN_WIDTH - 5

# === Breaking Animation ===
class BreakingAnimation:
    def __init__(self):
        self.pieces = []
        self.active = False
        self.timer = 0
        self.piece_data = []

    def start(self, x, y):
        """Create breaking pieces at watermelon position"""
        self.active = True
        self.timer = 0

        # Clear old pieces
        for p in self.pieces:
            p.opacity = 0
        self.pieces.clear()
        self.piece_data.clear()

        # Create 6 small pieces flying outward
        for i in range(6):
            piece = Circle2DNode()
            piece.radius = 3
            if i % 3 == 0:
                piece.color = engine_draw.green
            elif i % 3 == 1:
                piece.color = engine_draw.red
            else:
                piece.color = engine_draw.pink
            piece.position = Vector2(x, y)

            # Random velocity outward
            angle = (i / 6.0) * 6.28
            speed = 1.5 + (urandom.getrandbits(4) / 10.0)

            self.pieces.append(piece)
            self.piece_data.append({
                'vx': speed * math.cos(angle),
                'vy': -2.0 + speed * math.sin(angle),
                'x': x,
                'y': y
            })

    def update(self):
        if not self.active:
            return False

        self.timer += 1

        for i, p in enumerate(self.pieces):
            data = self.piece_data[i]
            # Apply gravity (screen coords: positive Y = down)
            data['vy'] += 0.15
            data['x'] += data['vx']
            data['y'] += data['vy']
            p.position = Vector2(data['x'], data['y'])

            # Fade out
            if self.timer > 30:
                p.opacity = max(0, 1.0 - (self.timer - 30) / 30.0)

        # End after 60 frames
        if self.timer >= 60:
            self.active = False
            for p in self.pieces:
                p.opacity = 0
            return True

        return False

    def reset(self):
        for p in self.pieces:
            p.opacity = 0
        self.pieces.clear()
        self.piece_data.clear()
        self.active = False
        self.timer = 0

# === Star Field (Background) ===
class StarField:
    def __init__(self, num_stars=25):
        self.stars = []
        self.star_data = []

        for _ in range(num_stars):
            star = Circle2DNode()
            # Random size - most small, some larger
            size_roll = urandom.getrandbits(4)
            if size_roll < 12:
                star.radius = 1
            elif size_roll < 15:
                star.radius = 2
            else:
                star.radius = 3

            # Star colors - mostly white/yellow
            color_roll = urandom.getrandbits(3)
            if color_roll < 5:
                star.color = engine_draw.white
            elif color_roll < 7:
                star.color = engine_draw.yellow
            else:
                star.color = engine_draw.lightgrey

            self.stars.append(star)
            self.star_data.append({
                'base_x': urandom.getrandbits(8) - 64,  # -64 to 191 spread
                'y': -65 + (urandom.getrandbits(5)),    # Upper sky area
                'twinkle_phase': urandom.getrandbits(6) / 10.0,
                'twinkle_speed': 0.05 + (urandom.getrandbits(4) / 100.0)
            })

    def update(self, camera_x, frame_count):
        """Update star positions with very slow parallax and twinkle effect"""
        for i, star in enumerate(self.stars):
            data = self.star_data[i]

            # Very slow parallax (stars move at 5% of camera speed)
            parallax_x = data['base_x'] + (camera_x * 0.05)

            # Wrap stars horizontally to always have coverage
            screen_x = ((parallax_x - camera_x + 128) % 256) + camera_x - 128

            star.position = Vector2(screen_x, data['y'])

            # Twinkle effect
            twinkle = math.sin(frame_count * data['twinkle_speed'] + data['twinkle_phase'])
            star.opacity = 0.4 + 0.6 * ((twinkle + 1) / 2)  # Range 0.4 to 1.0

# === Mountain Manager (Parallax Background) ===
class MountainManager:
    def __init__(self):
        self.mountains = []
        self.mountain_data = []
        self.parallax_factor = 0.15  # Mountains move at 15% of camera speed (slower than foreground)
        self.num_mountains = 8  # Fixed pool of mountains to recycle

    def create_mountain(self, base_x):
        """Create a mountain as a rotated square (diamond shape)"""
        # Random mountain size - doubled
        size = 40 + urandom.getrandbits(6)  # 40-103 pixels

        # Mountain Y position - moved down so only top half shows
        y = 45 + (urandom.getrandbits(3) - 4)  # Lower on screen

        # Create diamond shape (rotated rectangle)
        mountain = Rectangle2DNode()
        mountain.width = size
        mountain.height = size
        mountain.rotation = 0.785  # 45 degrees in radians (pi/4)
        mountain.layer = 0  # Background layer

        # Mountain colors - different shades of brown
        color_roll = urandom.getrandbits(3)
        if color_roll < 3:
            mountain.color = engine_draw.brown
        elif color_roll < 5:
            mountain.color = engine_draw.orange
        else:
            mountain.color = engine_draw.darkgrey  # Dark brown-ish

        mountain.opacity = 0.5  # More transparent for depth

        self.mountains.append(mountain)
        self.mountain_data.append({
            'base_x': base_x,
            'y': y,
            'size': size
        })

    def recycle_mountain(self, index, camera_x):
        """Move a mountain that went off-screen left to a new position on the right"""
        data = self.mountain_data[index]
        mountain = self.mountains[index]

        # Find the rightmost mountain position
        max_base_x = camera_x / self.parallax_factor + SCREEN_WIDTH
        for d in self.mountain_data:
            if d['base_x'] > max_base_x:
                max_base_x = d['base_x']

        # Place this mountain to the right with random spacing
        new_size = 40 + urandom.getrandbits(6)  # Doubled size
        new_base_x = max_base_x + new_size + 400 + urandom.getrandbits(7)  # 5x wider spacing
        new_y = 45 + (urandom.getrandbits(3) - 4)  # Lower on screen

        # Update mountain properties
        mountain.width = new_size
        mountain.height = new_size

        # Randomize color - different shades of brown
        color_roll = urandom.getrandbits(3)
        if color_roll < 3:
            mountain.color = engine_draw.brown
        elif color_roll < 5:
            mountain.color = engine_draw.orange
        else:
            mountain.color = engine_draw.darkgrey  # Dark brown-ish

        # Update data
        data['base_x'] = new_base_x
        data['y'] = new_y
        data['size'] = new_size

    def update(self, camera_x):
        """Update mountain positions with parallax, recycle off-screen mountains"""
        for i, mountain in enumerate(self.mountains):
            data = self.mountain_data[i]

            # Parallax position - mountains move slower than camera
            actual_x = data['base_x'] * self.parallax_factor - camera_x * (self.parallax_factor - 1)

            mountain.position = Vector2(actual_x, data['y'])

            # If mountain went off screen to the left, recycle it to the right
            if actual_x < camera_x - SCREEN_WIDTH - data['size']:
                self.recycle_mountain(i, camera_x)

    def reset(self):
        # Clear existing mountains
        for m in self.mountains:
            m.opacity = 0
        self.mountains.clear()
        self.mountain_data.clear()

        # Create fixed pool of mountains spread across the screen
        spacing = 600  # 5x wider spacing
        for i in range(self.num_mountains):
            base_x = -150 + (i * spacing) + urandom.getrandbits(6)
            self.create_mountain(base_x)

# === UI Elements ===
UI_LAYER = 10  # Higher layer renders on top of background elements

# Title screen
title_text = Text2DNode()
title_text.text = "WATERMELON"
title_text.position = Vector2(5, -40)
title_text.color = engine_draw.green
title_text.layer = UI_LAYER

subtitle_text = Text2DNode()
subtitle_text.text = "Balance Game"
subtitle_text.position = Vector2(12, -25)
subtitle_text.color = engine_draw.white
subtitle_text.layer = UI_LAYER

high_score_text = Text2DNode()
high_score_text.text = "Best: " + str(high_score) + "m"
high_score_text.position = Vector2(10, 0)
high_score_text.color = engine_draw.gold
high_score_text.layer = UI_LAYER

controls_text = Text2DNode()
controls_text.text = "LB/RB to tilt"
controls_text.position = Vector2(5, 15)
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
distance_text.position = Vector2(-20, -55)
distance_text.color = engine_draw.white
distance_text.opacity = 0
distance_text.layer = UI_LAYER
distance_text.scale = Vector2(2, 2)

# Tilt indicator
tilt_bar = Rectangle2DNode()
tilt_bar.width = 30
tilt_bar.height = 4
tilt_bar.color = engine_draw.darkgrey
tilt_bar.position = Vector2(40, -55)
tilt_bar.opacity = 0
tilt_bar.layer = UI_LAYER

tilt_marker = Circle2DNode()
tilt_marker.radius = 4
tilt_marker.color = engine_draw.yellow
tilt_marker.position = Vector2(40, -55)
tilt_marker.opacity = 0
tilt_marker.layer = UI_LAYER

# Jump cooldown indicator
jump_bar_bg = Rectangle2DNode()
jump_bar_bg.width = 30
jump_bar_bg.height = 4
jump_bar_bg.color = engine_draw.darkgrey
jump_bar_bg.position = Vector2(40, -47)
jump_bar_bg.opacity = 0
jump_bar_bg.layer = UI_LAYER

jump_bar_fill = Rectangle2DNode()
jump_bar_fill.width = 30
jump_bar_fill.height = 4
jump_bar_fill.color = engine_draw.green
jump_bar_fill.position = Vector2(40, -47)
jump_bar_fill.opacity = 0
jump_bar_fill.layer = UI_LAYER

# Death screen
death_text = Text2DNode()
death_text.text = "SPLAT!"
death_text.position = Vector2(-5, -20)
death_text.color = engine_draw.red
death_text.opacity = 0
death_text.layer = UI_LAYER

final_score_text = Text2DNode()
final_score_text.text = "Distance: 0m"
final_score_text.position = Vector2(10, 5)
final_score_text.color = engine_draw.white
final_score_text.opacity = 0
final_score_text.layer = UI_LAYER

new_record_text = Text2DNode()
new_record_text.text = "NEW RECORD!"
new_record_text.position = Vector2(10, -35)
new_record_text.color = engine_draw.gold
new_record_text.opacity = 0
new_record_text.layer = UI_LAYER

restart_text = Text2DNode()
restart_text.text = "Press A to Retry"
restart_text.position = Vector2(-5, 40)
restart_text.color = engine_draw.white
restart_text.opacity = 0
restart_text.layer = UI_LAYER

# === Create Game Objects ===
watermelon = Watermelon()
ground_manager = GroundManager()
left_wall = LeftWall()
breaking_anim = BreakingAnimation()
star_field = StarField(25)
mountain_manager = MountainManager()

# === Game State ===
state = STATE_TITLE
input_cooldown = 0
current_gravity_x = GRAVITY_NEUTRAL_X
frame_count = 0  # For star twinkling animation

# === Helper Functions ===
def show_title():
    title_text.opacity = 1.0
    subtitle_text.opacity = 1.0
    high_score_text.opacity = 1.0
    high_score_text.text = "Best: " + str(high_score) + "m"
    controls_text.opacity = 1.0
    start_text.opacity = 1.0

    distance_text.opacity = 0
    tilt_bar.opacity = 0
    tilt_marker.opacity = 0
    jump_bar_bg.opacity = 0
    jump_bar_fill.opacity = 0
    death_text.opacity = 0
    final_score_text.opacity = 0
    new_record_text.opacity = 0
    restart_text.opacity = 0

    watermelon.hide()
    left_wall.visual.opacity = 0

def show_playing():
    title_text.opacity = 0
    subtitle_text.opacity = 0
    high_score_text.opacity = 0
    controls_text.opacity = 0
    start_text.opacity = 0

    distance_text.opacity = 1.0
    tilt_bar.opacity = 1.0
    tilt_marker.opacity = 1.0
    jump_bar_bg.opacity = 1.0
    jump_bar_fill.opacity = 1.0

    death_text.opacity = 0
    final_score_text.opacity = 0
    new_record_text.opacity = 0
    restart_text.opacity = 0

    left_wall.visual.opacity = 1.0

def show_death(is_new_record):
    death_text.opacity = 1.0
    final_score_text.opacity = 1.0
    restart_text.opacity = 1.0
    tilt_bar.opacity = 0
    tilt_marker.opacity = 0
    jump_bar_bg.opacity = 0
    jump_bar_fill.opacity = 0

    if is_new_record:
        new_record_text.opacity = 1.0
    else:
        new_record_text.opacity = 0

def start_game():
    global state, frame_count
    watermelon.reset(0)
    ground_manager.reset()
    mountain_manager.reset()
    camera.position = Vector2(0, 0)
    left_wall.update(0)
    breaking_anim.reset()
    frame_count = 0
    engine_physics.set_gravity(GRAVITY_NEUTRAL_X, GRAVITY_NEUTRAL_Y)
    state = STATE_PLAYING
    show_playing()

def update_tilt():
    """Update gravity based on shoulder button input - gradual change"""
    global current_gravity_x

    lb_pressed = engine_io.LB.is_pressed
    rb_pressed = engine_io.RB.is_pressed

    # Determine target tilt (LB = right, RB = left)
    if lb_pressed and not rb_pressed:
        target_x = GRAVITY_TILT_X
    elif rb_pressed and not lb_pressed:
        target_x = -GRAVITY_TILT_X
    else:
        target_x = GRAVITY_NEUTRAL_X

    # Gradually move toward target
    if current_gravity_x < target_x:
        current_gravity_x = min(current_gravity_x + TILT_SPEED, target_x)
    elif current_gravity_x > target_x:
        current_gravity_x = max(current_gravity_x - TILT_SPEED, target_x)

    # Apply gravity (always keep full downward gravity)
    engine_physics.set_gravity(current_gravity_x, GRAVITY_NEUTRAL_Y)

# === Initialize ===
show_title()
ground_manager.reset()
mountain_manager.reset()

# === Main Game Loop ===
while True:
    if engine.tick():
        frame_count += 1

        if input_cooldown > 0:
            input_cooldown -= 1

        # Update background on all screens (stars twinkle, mountains visible)
        star_field.update(camera.position.x, frame_count)
        mountain_manager.update(camera.position.x)

        if state == STATE_TITLE:
            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                start_game()
                input_cooldown = 15

        elif state == STATE_PLAYING:
            # Handle tilt input
            update_tilt()

            # Handle jump input
            if engine_io.A.is_just_pressed:
                watermelon.jump()

            # Update watermelon and check for death
            fell_off_screen = watermelon.physics.position.y > 80

            if not watermelon.update() or fell_off_screen:
                # Death!
                state = STATE_DEAD
                score = ground_manager.get_distance_score()
                final_score_text.text = "Distance: " + str(score) + "m"

                # Check for new high score
                is_new_record = False
                if score > high_score:
                    high_score = score
                    engine_save.save("high_score", high_score)
                    is_new_record = True

                # Start breaking animation
                breaking_anim.start(watermelon.physics.position.x,
                                   watermelon.physics.position.y)
                watermelon.hide()
                show_death(is_new_record)
                input_cooldown = 30

            # Camera follow with look-ahead
            target_x = watermelon.physics.position.x + 20
            camera.position.x += (target_x - camera.position.x) * 0.1

            # Update ground generation
            ground_manager.update(camera.position.x)

            # Update left wall
            left_wall.update(camera.position.x)

            # Update water position (follows camera)
            water.position.x = camera.position.x

            # Update distance display (follows camera)
            distance_text.text = str(ground_manager.get_distance_score()) + "m"
            distance_text.position.x = camera.position.x - 20
            distance_text.position.y = camera.position.y - 55

            # Update tilt indicator (follows camera, marker moves with tilt)
            tilt_bar.position.x = camera.position.x + 40
            tilt_bar.position.y = camera.position.y - 55
            # Marker moves left/right based on tilt (-15 to +15 range)
            tilt_offset = (current_gravity_x / GRAVITY_TILT_X) * 12 if GRAVITY_TILT_X != 0 else 0
            tilt_marker.position.x = camera.position.x + 40 + tilt_offset
            tilt_marker.position.y = camera.position.y - 55

            # Update jump cooldown indicator
            jump_bar_bg.position.x = camera.position.x + 40
            jump_bar_bg.position.y = camera.position.y - 47
            # Fill bar shrinks as cooldown counts down (full = ready to jump)
            cooldown_ratio = 1.0 - (watermelon.jump_cooldown / 60.0)
            jump_bar_fill.width = max(1, int(30 * cooldown_ratio))
            jump_bar_fill.position.x = camera.position.x + 40 - (30 - jump_bar_fill.width) / 2
            jump_bar_fill.position.y = camera.position.y - 47
            # Change color based on ready state
            if watermelon.jump_cooldown == 0:
                jump_bar_fill.color = engine_draw.green
            else:
                jump_bar_fill.color = engine_draw.red

        elif state == STATE_DEAD:
            # Update breaking animation
            breaking_anim.update()

            # Keep HUD centered on camera
            death_text.position.x = camera.position.x - 5
            death_text.position.y = camera.position.y - 20
            final_score_text.position.x = camera.position.x + 10
            final_score_text.position.y = camera.position.y + 5
            new_record_text.position.x = camera.position.x + 10
            new_record_text.position.y = camera.position.y - 35
            restart_text.position.x = camera.position.x - 5
            restart_text.position.y = camera.position.y + 40

            if input_cooldown == 0 and engine_io.A.is_just_pressed:
                start_game()
                input_cooldown = 15

        # Exit on MENU
        if engine_io.MENU.is_just_pressed:
            engine_save.save("high_score", high_score)
            engine.end()
            break
