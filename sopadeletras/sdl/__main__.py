"""Punto de entrada: permite ejecutar `python -m sdl ...`."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
