"""
MicroPython script for BBC micro:bit V2.
Flash this onto the micro:bit using https://python.microbit.org/

Reads the built-in temperature sensor and light level sensor,
then sends comma-separated values over USB serial.
Receives commands from the desktop app:
  ``RISK:<level>``  – visual/audio feedback on the 5×5 LED matrix.
  ``RATE:<ms>``     – dynamic sampling rate (adjusts read interval).

Data is also logged locally on the micro:bit's flash storage using
the built-in ``log`` module.  When the micro:bit is connected as a
USB drive the file ``MY_DATA.HTM`` contains the logged readings.
Use the desktop app's **History → Import from micro:bit** button to
import this data.

Format sent:     temperature,light\\n     e.g. 23,147\\n
Format received: RISK:LOW\\n  /  RISK:MODERATE\\n  /  RISK:HIGH\\n  /  RISK:CRITICAL\\n
                 RATE:500\\n  /  RATE:2000\\n   (sampling interval in ms)
"""
import uart
from microbit import *
import music
import log

# ------------------------------------------------------------------
# LED patterns for each risk level  (5×5 images, digits 0-9 = brightness)
# ------------------------------------------------------------------
RISK_IMAGES = {
    "LOW": Image(
        "00000:"
        "00000:"
        "00300:"
        "00000:"
        "00000"),
    "MODERATE": Image(
        "00000:"
        "05550:"
        "05050:"
        "05550:"
        "00000"),
    "HIGH": Image(
        "00600:"
        "06060:"
        "60006:"
        "06060:"
        "00600"),
    "CRITICAL": Image(
        "90009:"
        "09090:"
        "00900:"
        "09090:"
        "90009"),
}

# Short melodies / tones for each risk transition
# Using pitch(frequency_hz, duration_ms) tuples played with music.pitch
# or built-in melodies.  Only triggered when the level *changes*.
def play_risk_sound(level):
    """Play a short sound matching the risk level (non-blocking where possible)."""
    if level == "LOW":
        # Single gentle low beep
        music.pitch(262, 150)
    elif level == "MODERATE":
        # Two short mid-pitch beeps
        music.pitch(440, 150)
        sleep(80)
        music.pitch(440, 150)
    elif level == "HIGH":
        # Rising two-tone alert
        music.pitch(600, 200)
        sleep(60)
        music.pitch(800, 200)
    elif level == "CRITICAL":
        # Urgent rapid alarm
        music.play(music.BADDY, wait=False)


# ------------------------------------------------------------------
# Setup
# ------------------------------------------------------------------
uart.init(baudrate=115200)
speaker.on()          # Enable the built-in V2 speaker

# Local data logging – stored on the micro:bit flash as MY_DATA.HTM
log.set_labels("temperature", "light", "risk", timestamp=log.SECONDS)
log.set_mirroring(True)  # Mirror log entries to serial as well

current_risk = "LOW"  # Default until the desktop app tells us otherwise
previous_risk = None   # Track transitions so audio only fires on change
uart_buffer = ""       # Accumulate incoming bytes between loop iterations
sample_interval = 2000 # Default read interval (ms), updated by RATE: commands

# ------------------------------------------------------------------
# Main loop
# ------------------------------------------------------------------
while True:
    # 1. Read built-in sensors  (read light BEFORE showing an image)
    temp = temperature()                    # °C (integer)
    light = display.read_light_level()      # 0-255

    # 2. Send sensor data to the desktop app
    uart.write("{},{}\n".format(temp, light))

    # 3. Log data locally on the micro:bit flash (MY_DATA.HTM)
    try:
        log.add(temperature=temp, light=light, risk=current_risk)
    except OSError:
        pass  # Flash full – silently skip logging

    # 4. Check for incoming commands from the desktop app
    if uart.any():
        incoming = uart.read()
        if incoming:
            uart_buffer += str(incoming, "utf-8")

    # Process complete lines in the buffer
    while "\n" in uart_buffer:
        line, uart_buffer = uart_buffer.split("\n", 1)
        line = line.strip()
        if line.startswith("RISK:"):
            level = line[5:]
            if level in RISK_IMAGES:
                current_risk = level
        elif line.startswith("RATE:"):
            # Dynamic Sampling Rate: desktop app controls read frequency
            try:
                new_rate = int(line[5:])
                if 100 <= new_rate <= 600000:
                    sample_interval = new_rate
            except ValueError:
                pass  # Ignore malformed RATE values

    # 5. LED feedback – show the icon for the current risk level
    display.show(RISK_IMAGES.get(current_risk, RISK_IMAGES["LOW"]))

    # 6. Audio feedback – only on risk-level *transitions*
    if current_risk != previous_risk:
        play_risk_sound(current_risk)
        previous_risk = current_risk

    sleep(sample_interval)  # Dynamic: adjusted by desktop app via RATE: command