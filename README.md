# Floppy v1.44

A mischievous retro desktop companion for Windows: a 3.5" floppy disk with a `VIRUS_DO_NOT_RUN.bat` label.
Full spec: `floppy_design_doc.md` on the desktop.

## Running

Double-click **`Floppy.exe`** in the project folder (it has Floppy's face as its icon). It is built by
`python tools/build.py` (see below) and uses the `assets/` folder next to it.

From source:

```
pip install -r requirements.txt
python main.py      # with a console (Ctrl+C quits)
```

Only one Floppy runs at a time; a second launch quietly exits. He idles at about 2% of one CPU core:
frames are repainted only when something visible changes, and the tick drops from 60 to 20 fps while he rests.
Unhandled errors are written to `%LOCALAPPDATA%\Floppy\Floppy\floppy_error.log` instead of closing the app.
He steps aside while a fullscreen app (game, video, presentation) is in front and pulls no pranks.

## Building the .exe

```
pip install -r requirements-dev.txt
python tools/build.py
```

The results are `Floppy.exe` in the project folder (a single file, the double-click launcher) and
`dist/Floppy/Floppy.exe` plus `dist/Floppy-v<version>.zip` for sharing (a self-contained folder that starts faster). Sounds live next to the exe in
`dist/Floppy/assets/sounds`, so they can be swapped without rebuilding; the YouTube link list is
`dist/Floppy/assets/videos.txt`. `Floppy.exe --self-check` writes
`floppy_check.txt` next to the exe, reporting whether every sound was found and decoded.

## Controls

- **Drag with the mouse**: he gets picked up and dangles his legs. Let go with a swing and he flies with physics,
  bouncing off the screen edges and the floor. Let go high up without a swing and he opens his parachute.
- **Reactions to your hands**: he comments on being grabbed, held for too long, flung fast, and on every landing,
  in yellow Win95 tooltip bubbles (the text types itself out while his shutter mouth moves). Shaking him or spinning
  him mid-air makes him dizzy: spiral eyes, circling stars, wobbling. 4 throws in a minute and he gets offended
  and may take revenge with an error window.
- **Drag an error window by its title bar**: Floppy jumps over, pushes back and won't let you move it (tug of war).
- **Left click**: makes him angry. 10 quick clicks in a row trigger a joke BSOD (exit with Space, Esc, a click or after 6 seconds).
- **Click him while asleep**: he wakes up startled.
- **Leave the mouse still for 15 seconds**: he tiptoes over and lurks under the cursor. Move the mouse and he
  panics: eyes pop (O_O), he shrieks, sheds pixels, spins his wheels and runs for the far corner.
- **Right click**: menu with the chaos level slider, skin, sound (on/off and volume), "Pranks" (which pranks he may
  pull on his own, "Real YouTube videos", "Edit video list..."), "Sleep for 15 minutes" / "Wake up",
  "Put on a show" ("Surprise me!" or any prank by name, including the blue screen) and "Eject floppy" to quit.

## Pranks (`floppy/pranks.py`, texts in `floppy/messages.py`)

- Win95 error windows: 305 messages, 20 titles, 25 sets of absurd buttons, many buttons with follow-ups.
  Texts come from a no-repeat shuffle bag: nothing repeats until everything has been shown, even across restarts.
- Runaway button: swaps places with "Panic" when the cursor gets close.
- Hydra: close a window with the X and there's a 30% chance two mini windows pop out.
- Fake progress bar: reaches 99%, hangs, then turns out to be a joke (25 variants).
- Tug of war: drag an error window and Floppy pushes against its side, huffing and sweating, and gives up after 6 seconds.
- **Video from behind the screen**: he walks to the screen edge, reaches behind it up to the elbows, rummages, and
  drags in a real YouTube video: he opens a **new** window of the default browser (Chrome, Edge, Firefox, Brave,
  Opera, Vivaldi, Yandex) with a link from `assets/videos.txt` and hauls it onto the screen. Only that new window
  is ever moved. Grab the window while he pulls and he lets go. If no browser window turns up (or
  "Pranks → Real YouTube videos" is unchecked), he brings his own Win95 Media Player with pixel cartoons instead
  (`floppy_dance.avi` with a chiptune, `hamster_wheel.mpg`, `cat_on_keyboard.avi`, the eternal `buffering.avi`).
- **Defragmenter**: "Defragmenting Drive A:" where a tiny Floppy runs across the cluster map carrying blocks by hand,
  gets faster as he goes, reaches 100%... and sneezes, scattering everything again ("Again!" restarts).
- **Minesweeper**: he plays it himself with his own mouse pointer, flags the obvious, guesses wildly and eventually
  clicks a mine out of overconfidence. The blast throws him across the screen, spinning, and he lands dizzy.
  Click the board to take over; the smiley starts a new game.
- **Graffiti**: he shakes a spray can and walks along the wall painting pixel lettering in neon ("FLOPPY WAS HERE",
  "SECTOR 0 GANG", 18 tags), drips and over-spray included. Scrub it off with the mouse, or it fades in ~3 minutes.
- **Clone (Ctrl+V)**: "Ctrl+C... Ctrl+V!" and a copy in another skin pops up, complete with a shortcut arrow. They
  argue, shove each other, the Recycle Bin slides in, and the copy gets kicked in head first, boots sticking out.
  Click the copy to delete it yourself.

## Behavior (state machine, `floppy/brain.py`)

| State | When | What he does |
| :--- | :--- | :--- |
| IDLE | default | breathes, blinks, follows the cursor, glances around and wiggles his eyebrows |
| WALK | random timer (frequency depends on chaos level) | walks along the taskbar or a window's top edge, shutter rattling |
| RAGE | clicks on his body | turns red, shakes, throws sparks, grinds his shutter; cools down without clicks |
| BSOD | 10 clicks / menu / rarely on his own at 100% | blue screen on every monitor |
| JUMP → AIR | random timer, if the active window is within reach | crouches and jumps onto the window's title bar (or jumps down from it) |
| AIR | jump, throw, window narrowed out from under him | ballistics: gravity, bounces off the floor and walls, spinning when thrown |
| FALL | his window was minimized, closed or covered | airmail-gore parachute, gentle descent |
| DRAG | the user is dragging him | hangs like a pendulum, kicks his legs |
| MISCHIEF | chaos timer, menu, revenge for throws | two hops, a shutter clack, then a window prank (error, progress bar, defragmenter, Minesweeper) |
| STUNT | chaos timer, menu | pranks in person (`floppy/stunts.py`): hauling a video in, graffiti, the clone show |
| DIZZY | shaking or spinning mid-air | spiral eyes, stars, wobbles for 2.6 s |
| PUSH | the user is dragging an error window | pushes against the window's side, feet spinning, sweating |
| SNEAK | the cursor hasn't moved for 15 s | crouches and tiptoes towards it, glancing around, then lurks underneath |
| SCARED | the frozen cursor suddenly moves nearby | startled jump, O_O eyes, shriek, sheds pixels, spins his wheels, runs to safety |
| SLEEP | nap timer, more often at night, after 5 min without mouse/keyboard, from the menu | walks to a corner, sits down, snores, floats "Z"s |

Chaos levels: **Sleepy** (sleeps almost all the time), **25%**, **50%**, **100% Apocalypse** (walks constantly and occasionally throws a BSOD on his own).
Timings and physics live in `floppy/config.py`.

## Sounds (`assets/sounds/`, `floppy/sound.py`)

All sounds are synthesized from scratch by `tools/make_sounds.py` (no samples), played asynchronously
through QtMultimedia. Replace any file with your own 16-bit PCM WAV and it is used on the next launch;
`python tools/make_sounds.py --force` restores the defaults.

| File | When |
| :--- | :--- |
| `floppy_seek.wav` | stepper motor grinding when he pulls a prank |
| `floppy_read.wav` | sector-reading buzz for progress bars; a quiet motor purr while he sleeps |
| `win95_error.wav` | an error window pops up (an original dissonant chord, not the real Windows sound) |
| `bsod_beep.wav` | long PC-speaker beep with the blue screen |
| `floppy_eject.wav` | latch click and clunk on "Eject floppy" |
| `ding.wav` | a progress bar finishes its joke |
| `scared_beep.wav` | panicked chirps when the cursor startles him |
| `shutter_clack.wav` | his shutter snapping when you click him |
| `mine_boom.wav` | a Minesweeper mine goes off |
| `spray_hiss.wav` | the spray can while he paints graffiti |
| `clone_pop.wav` | Ctrl+V: a copy pops into existence (or gets deleted) |
| `recycle_bin.wav` | the copy lands in the Recycle Bin |
| `chiptune_loop.wav` | an original 8-second chiptune loop under `floppy_dance.avi` and friends |

## Visual language

"A Windows 95 icon that came to life". See `docs/design_sheet.png`.

- Black outline, flat fills, hard bevels and VGA checkerboard dithering instead of gradients.
- Win95 palette: silver `#C0C0C0`, bevels `#FFFFFF` / `#808080`, navy `#000080` ink, red `#C00000`.
- The shutter mouth is a raised Win95 button with a sunken window; opened, it shows pixel teeth and the magnetic disk.
- The face is the star: pixel eyelids and eyebrows, expressions in `floppy/expressions.py`
  (`smug` by default, `angry`, `scared`, `panic`, `sneaky`, `happy`, `dizzy`, `sleepy`, `neutral`).
- Frame-by-frame motion: breathing in 1 px steps, expressions blend in about 0.1 s.

## Structure

- `floppy/render.py`: procedural rendering of the character (body, label, face, shutter mouth, legs, shadow, parachute).
- `floppy/expressions.py`: expressions (eyelids, eyebrows, pupil size).
- `floppy/skins.py`: plastic palettes.
- `floppy/brain.py`: state machine and physics, independent of Qt windows.
- `floppy/stunts.py`: pranks in person (hauling, graffiti, the clone and the Recycle Bin), also Qt-window-free.
- `floppy/face.py`: facial animation (blinking, expression blending, gaze, fidgets).
- `floppy/effects.py`: pixel particles (sparks, dust, sweat, shed pixels, "Z z z").
- `floppy/bsod.py`: blue screen on every monitor.
- `floppy/menu.py`, `floppy/theme.py`: retro menu and Windows 95 styles.
- `floppy/dialogs.py`: Windows 95 windows (error with a runaway button, progress bar).
- `floppy/pranks.py`: prank manager (spawning windows, hydra, follow-ups, tug of war, hauling, graffiti, the clone).
- `floppy/defrag.py`, `floppy/minesweeper.py`, `floppy/mediaplayer.py`: the defragmenter, Minesweeper and Media Player.
- `floppy/graffiti.py`: spray-paint overlay. `floppy/actors.py`: windows for the clone and the Recycle Bin.
- `floppy/browser.py`: the real-YouTube mode (default browser lookup, finding and moving its new window).
- `floppy/sprites.py`: tiny pixel art (mini Floppy) and a 5x7 pixel font.
- `floppy/messages.py`: all prank texts.
- `floppy/speech.py`: Floppy's lines and the speech bubble.
- `floppy/character.py`: the transparent always-on-top window that ties everything together.
- `floppy/sound.py`: sound bank (preloaded effect pools, volume, on/off).
- `floppy/config.py`: chaos levels, timings and physics.
- `tools/make_sounds.py`: synthesizes the default WAVs. `tools/build.py`: icon, PyInstaller builds (folder + one-file launcher), zip.
- `floppy/win32.py`: Win32 API (active window, visible DWM frame, occlusion checks, fullscreen detection,
  physical-to-logical pixel conversion per monitor scale, user idle time).

## Progress

- [x] Stage 1: skeleton. Transparent window, Floppy stands on the taskbar, breathes, blinks, follows the mouse
- [x] Stage 2: state machine. WALK / SLEEP / RAGE / BSOD and the context menu (sound comes in stage 5)
- [x] Stage 3: window platforming, FALL with a parachute, dragging and throwing with physics
- [x] Stage 4: pranks. Win95 error windows (305 texts), hydra, progress bar, tug of war; reactions to the user's hands
- [x] Stage 5: SNEAK / SCARED, synthesized sounds with volume control, fullscreen pause, single instance, .exe build
- [x] Extra: arms; video from behind the screen (own player or real YouTube), defragmenter, Minesweeper, graffiti,
  the clone show; prank menu
