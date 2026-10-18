# Thumby Color Games

A collection of games for the [Thumby Color](https://tinycircuits.com/products/thumby-color) handheld console, just making small games for my kids to play.

## Games

### Race
A betting game where you pick a racer, place a bet, and watch them race.
- 3 racers with random names
- Fatigue system: recent winners get tired, underdogs get rested
- Speed re-roll at halfway point for excitement
- 3x payout on wins

### Labubu
A Tamagotchi-style virtual pet game.
- 7 Labubu types with different colors and rarities
- Feed and Play to keep your Labubu happy and fed
- Idle animations based on stat levels
- Persistent save state between sessions

### PinBattle
A 2-player pachinko-style battle game.
- Two players select names and drop colored balls
- Balls bounce through pins toward a moving bucket
- First ball to land in the bucket wins
- Use LB/RB bumper buttons to nudge balls

### Watermelon
A rolling watermelon balance game.
- Roll a watermelon across procedurally generated terrain
- Tilt gravity with LB/RB to control movement
- Jump with A to hop over gaps (1 second cooldown)
- Don't fall too far or you'll splat!
- High score saved between sessions

### TicTac9
Ultimate Tic Tac Toe - a strategic twist on the classic game.
- 9 tic-tac-toe boards arranged in a 3x3 grid
- Where you play determines which board your opponent must play next
- Win 3 boards in a row to win the game
- 2-player local gameplay (X vs O)

### Sand
A falling sand simulation game (modified from the original Thumby Color game).
- Particle types: sand, water, wall, fuse, bomb, fire (LB/RB to switch, A to draw, B to erase)
- Fuse burns along its length when lit with fire; water puts it out
- Bombs explode when fire or a burning fuse touches them (chain reactions, screen shake, boom sound from `boom.wav`)
- Added ant creatures that crawl around and interact with particles
- Added fish creatures that swim through water

### TimesTables
A multiplication times tables learning game for kids.
- Practice 1x through 12x tables
- Three-phase learning: read aloud, sequential quiz, shuffled quiz
- Multiple choice questions with plausible wrong answers
- Tracks best scores for each table (saves between sessions)
- Shows correct answer when wrong, helping reinforce learning

### Scorched Thumb
A Scorched Earth style artillery game for 2-4 players.
- Turn-based tank battles on a 256px wide battlefield that scrolls (minimap in the HUD)
- Destructible terrain: craters with scorched rims, loose dirt and tanks fall, fall damage
- Weapons: Baby Missile, Missile, Big Bomb, MIRV, Funky Bomb, Roller, Dirt Bomb, Tracer, Napalm (burning fire that flows downhill)
- Items: parachutes (no fall damage), shields (soak up damage), fuel for driving
- Shop before each round: earn money for damage, kills and wins, then spend it
- Wind, six landscape themes, and three landscape styles
- Hotseat play; any seat can be a CPU (Easy / Medium / Hard) that zeroes in on its target
- Aim Help option shows the start of each shot's path for younger players
- Sudden death breaks stalemates
- Target Practice: 12 single-player levels of balloons and ground targets, up to 3 stars each
- Hall of Fame: games and rounds won by each player's name, saved on the device
- Controls: Left/Right angle, Up/Down power, A fire, B tap weapon, hold B + Left/Right look around, LB/RB drive, MENU pause

### Pinball
Five pinball tables that scroll with the ball. Pick one on the title screen with Left/Right; each keeps its own high score.
- **Space** (easy): planet bumpers, rollover lanes and alien drop targets
- **Dino Park** (easy): volcano bumpers, a spinner, dino eggs, and a T-rex that eats the ball (three bites = 2-ball multiball)
- **Pirate Ship** (medium): a ramp up the mast, skull targets, a treasure chest hole (2-ball multiball) and a cannon kickback
- **Castle** (hard): smash the castle gate and shoot the ball inside for 3-ball multiball, plus a catapult ramp, an orbit spinner and pop-up trolls
- **Robot Factory** (hard): two ramps with spinners (combos!), gear bumpers, and bolt targets that light the lock for 3-ball multiball
- The harder tables have outlanes that can drain the ball, with a kickback to save it
- Light all the top lanes to raise the score multiplier (up to 5X); the flippers slide the lit lanes
- 3 balls, ball save after each launch, double scoring during multiball
- The camera stays on the flippers and only rises when the ball is high on the table
- Controls: LB or LEFT left flipper, RB or A right flipper, hold DOWN to launch, UP to nudge, MENU pause

## Installation

1. Connect your Thumby Color via USB
2. Use [Thonny IDE](https://thonny.org/) to upload game folders to the device's `Games/` directory
3. Each game folder contains `main.py`, `manifest.ini`, and optionally `icon.bmp`

## Development

- Screen resolution: 128x128 pixels
- Engine: [Tiny Game Engine](https://github.com/TinyCircuits/TinyCircuits-Tiny-Game-Engine) (MicroPython)
- Documentation: https://color.thumby.us/doc/landing.html
- Desktop testing: `tools/thumbysim.py` stands in for the engine so a game's `main.py` runs on regular Python and saves screenshots. See `tools/scorched_tests.py` for an example.
