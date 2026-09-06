# Forest Risk Prevention System

A Leaving Certificate Computer Science project that uses a BBC micro:bit and a
Python desktop application to monitor environmental conditions, estimate
wildfire risk, display warnings, and record sensor sessions.

## Published report

The project report is published with GitHub Pages:

**[View the report website](https://1042025104687-cmyk.github.io/CS_LC_PROJECT/)**

The website is deployed automatically from the `report/` directory whenever a
report file is pushed to the `main` branch. The Python application is not a web
application; its complete source remains available in this repository.

The deployment workflow publishes the site to the `gh-pages` branch. In
repository **Settings → Pages**, set the source to **Deploy from a branch** and
select `gh-pages` (root) once.

## Repository structure

```text
.
├── artefact/                 Python desktop application and micro:bit code
│   ├── config/               Saved application settings
│   ├── data/                 Example sensor and session data
│   ├── docs/                 Detailed startup guide
│   ├── microbit/             MicroPython source and flashable HEX file
│   ├── src/                  Application source code
│   ├── tests/                Automated pytest test suite
│   ├── main.py               Desktop application entry point
│   └── requirements.txt      Python dependencies
├── report/                   GitHub Pages website
│   ├── report-site/          Report pages and stylesheet
│   ├── resources/            Diagrams, screenshots, and videos
│   └── index.html            Website entry point
└── .github/workflows/        Automatic GitHub Pages deployment
```

## Run the artefact

### Requirements

- Python 3.10 or newer
- Tkinter (normally included with Python on Windows)
- A BBC micro:bit V2 is optional because the application includes simulated
  sensor scenarios

From the repository root, create a virtual environment and install the Python
packages:

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
python -m pip install -r artefact/requirements.txt
python artefact/main.py
```

On Linux or macOS:

```bash
source .venv/bin/activate
python -m pip install -r artefact/requirements.txt
python artefact/main.py
```

To use the built-in simulation, open **Settings**, enable simulation, choose a
scenario, and select **Connect**.

## Use a BBC micro:bit

1. Open the [micro:bit Python editor](https://python.microbit.org/).
2. Copy `artefact/microbit/microbit_sensor.py` into the editor and flash it to
   a micro:bit V2.
3. Connect the micro:bit over USB.
4. In the desktop application, disable simulation, select the serial port, and
   select **Connect**.

The micro:bit sends temperature and light readings to the application. It also
uses its LED display and speaker to communicate the current risk level.

## Run the tests

With the virtual environment active:

```bash
cd artefact
python -m pytest tests/ -v
```

More detailed setup and troubleshooting information is available in
[`artefact/docs/STARTUP_GUIDE.md`](artefact/docs/STARTUP_GUIDE.md).
