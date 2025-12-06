from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect narration fields from a slide scripts JSON and write them to a text file."
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Path to the slide scripts JSON file",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional path for the output text file. Defaults to <input>_narrations.txt",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path: Path = args.input
    output_path: Path = args.output or input_path.with_name(f"{input_path.stem}_narrations.txt")

    data = json.loads(input_path.read_text())
    narrations = [item.get("narration", "") for item in data]
    output_path.write_text("\n".join(narrations), encoding="utf-8")
    print(f"Wrote {len(narrations)} narrations to {output_path}")


if __name__ == "__main__":
    main()
