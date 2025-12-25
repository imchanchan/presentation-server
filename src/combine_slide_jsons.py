#!/usr/bin/env python3
"""Combine slide JSON outputs into one text file for easy token counting."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Combine JSON slide outputs into a single text file."
    )
    parser.add_argument(
        "slides_dir",
        nargs="?",
        default=Path(__file__).resolve().parent.parent / "slides",
        type=Path,
        help="Directory that holds slide JSON files (default: ../slides).",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=Path(__file__).resolve().parent.parent / "slides" / "slides_combined.txt",
        type=Path,
        help="Output text file path (default: ../slides/slides_combined.txt).",
    )
    return parser.parse_args()


def json_to_text(data: object) -> str:
    """Render JSON content in a readable text representation."""
    if isinstance(data, dict):
        lines = []
        for key, value in data.items():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
    return json.dumps(data, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    slides_dir = args.slides_dir
    if not slides_dir.exists():
        raise SystemExit(f"Slides directory not found: {slides_dir}")

    json_files = sorted(slides_dir.glob("*.json"))
    if not json_files:
        raise SystemExit(f"No JSON files found in {slides_dir}")

    sections = []
    for path in json_files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Failed to parse {path}: {exc}") from exc
        body = json_to_text(data)
        sections.append(f"### {path.name}\n{body}\n")

    args.output.write_text("\n".join(sections), encoding="utf-8")
    print(f"Combined {len(json_files)} files into {args.output}")


if __name__ == "__main__":
    main()
