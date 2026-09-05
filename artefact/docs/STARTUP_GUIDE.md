Startup Guide — Drought Risk Prevention System


Getting Started

You'll need Python 3.10 or newer with pip installed. Once that's sorted, just open a terminal in the project folder and run:

    pip install pyserial pandas matplotlib
    python main.py

That should open the application window straight away.


Starting the Simulation

Head over to the Settings tab, tick Enable simulation, choose whichever scenario you want, and hit Connect. Data should start coming through on the dashboard within a few seconds.


Using a BBC micro:bit (Optional)

You don't actually need any hardware — simulation mode covers everything. But if you do have a micro:bit V2 and want to try it with real sensor data:

  1. Go to python.microbit.org in your browser.
  2. Copy the code from microbit/microbit_sensor.py into the editor and flash it onto the micro:bit.
  3. Plug the micro:bit into your computer with a USB cable.
  4. Back in the app, go to Settings, untick Enable simulation, pick the right serial port from the dropdown, and click Connect.

Once it's connected, the micro:bit will send live temperature and light readings over serial. It also shows the current risk level on its LED display and plays a little alert tone whenever the risk level changes, which is a nice touch.


Running the Tests

If you want to run the test suite:

    python -m pytest tests/ -v


Troubleshooting

  ModuleNotFoundError
    Run "pip install pyserial pandas matplotlib" again — a package probably didn't install properly.

  No data showing on the dashboard
    Make sure Enable simulation is ticked and you've clicked Connect.

  The window won't open
    Make sure you're running the program from inside the artefact/ folder.


LCCS Leaving Cert Computer Science — March 2026

