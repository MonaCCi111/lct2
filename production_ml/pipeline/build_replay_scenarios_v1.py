"""Воспроизвести фиксированные исторические сценарии без выбора параметров кодом."""

import json
import subprocess
import sys
from pathlib import Path


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    here = Path(__file__).resolve().parent
    scenarios = json.loads((here / "replay_scenarios_v1.json").read_text(encoding="utf-8"))
    output_root = here.parent / "data" / "replay_v1"
    for scenario in scenarios:
        command = [sys.executable,str(here / "build_replay_v1.py"),
                   "--object-id",str(scenario["object_id"]),
                   "--start",scenario["start"],"--end",scenario["end"],
                   "--output",str(output_root / scenario["id"])]
        subprocess.run(command,check=True)


if __name__ == "__main__":
    main()
