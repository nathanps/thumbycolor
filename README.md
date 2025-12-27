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

### Sand
A falling sand simulation game (modified from the original Thumby Color game).
- Particle types: sand, water, stone
- Added ant creatures that crawl around and interact with particles
- Added fish creatures that swim through water

## Installation

1. Connect your Thumby Color via USB
2. Use [Thonny IDE](https://thonny.org/) to upload game folders to the device's `Games/` directory
3. Each game folder contains `main.py`, `manifest.ini`, and optionally `icon.bmp`

## Development

- Screen resolution: 128x128 pixels
- Engine: [Tiny Game Engine](https://github.com/TinyCircuits/TinyCircuits-Tiny-Game-Engine) (MicroPython)
- Documentation: https://color.thumby.us/doc/landing.html
