"""CLI действующих моделей. Без --model сохраняет прежний маршрут фазы."""

import argparse
import importlib
import sys

from .active import ACTIVE_MODELS, MODEL_VERSION


def main():
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--model", choices=tuple(ACTIVE_MODELS), default=MODEL_VERSION)
    known, remaining = parser.parse_known_args()
    module = importlib.import_module(ACTIVE_MODELS[known.model]["scorer"])
    sys.argv = [sys.argv[0], *remaining]
    module.main()


if __name__ == "__main__":
    main()
