# Drought Risk Prevention System

import os
import sys

# Ensure working directory is the artefact folder (where data/ lives)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from src.gui.app import App


def main():
    app = App()
    app.run()


if __name__ == "__main__":
    main()
