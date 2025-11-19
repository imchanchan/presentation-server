#!/usr/bin/env python3
"""Generate narration scripts for each slide by calling the OpenAI API."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI


ROOT_DIR = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError("OPENAI_API_KEY가 설정되지 않았습니다. .env 구성을 확인하세요.")


DEFAULT_MODEL = os.getenv("SLIDE_SCRIPT_MODEL", "gpt-4o-mini")
STYLE_HINTS = {
    "concise": "간결하고 핵심 메시지를 강조하는 말투",
    "persuasive": "투자자에게 설득력 있게 강조하는 말투",
    "friendly": "대화하듯 자연스럽고 부드러운 말투",
}


@dataclass
class SlidePayload:
    number: int
    path: Path
    data: Dict[str, object]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="슬라이드 JSON을 기반으로 발표 대본을 생성합니다."
    )
    parser.add_argument(
        "--slides-dir",
        type=Path,
        default=ROOT_DIR / "slides",
        help="슬라이드 JSON이 저장된 디렉터리 경로",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT_DIR / "slide_scripts",
        help="생성된 대본 JSON을 저장할 디렉터리",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help="사용할 OpenAI 모델 이름",
    )
    parser.add_argument(
        "--style",
        choices=STYLE_HINTS.keys(),
        default="concise",
        help="대본 말투 스타일",
    )
    parser.add_argument(
        "--language",
        choices=("ko", "en"),
        default="ko",
        help="대본을 작성할 언어",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.6,
        help="OpenAI 호출 시 사용할 temperature",
    )
    parser.add_argument(
        "--max-slides",
        type=int,
        help="처리할 최대 슬라이드 수(테스트용)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="한 번의 OpenAI 호출로 처리할 슬라이드 수",
    )
    return parser.parse_args()


def extract_slide_number(path: Path) -> Optional[int]:
    match = re.search(r"slide(\d+)_", path.name)
    return int(match.group(1)) if match else None


def load_latest_slides(slides_dir: Path) -> List[SlidePayload]:
    if not slides_dir.exists():
        raise FileNotFoundError(f"슬라이드 폴더를 찾을 수 없습니다: {slides_dir}")

    latest: Dict[int, SlidePayload] = {}
    for file_path in slides_dir.glob("slide*.json"):
        slide_number = extract_slide_number(file_path)
        if slide_number is None:
            continue

        try:
            raw = file_path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"⚠️ JSON 파싱 실패 - {file_path}: {exc}")
            continue

        payload = SlidePayload(slide_number, file_path, data)
        existing = latest.get(slide_number)
        if not existing or file_path.stat().st_mtime > existing.path.stat().st_mtime:
            latest[slide_number] = payload

    slides = sorted(latest.values(), key=lambda item: item.number)
    if not slides:
        raise RuntimeError(f"{slides_dir}에서 슬라이드 JSON을 찾을 수 없습니다.")
    return slides


def build_prompt(slide: SlidePayload, style: str, language: str) -> str:
    slide_json = json.dumps(slide.data, ensure_ascii=False, indent=2)
    tone = STYLE_HINTS[style]
    language_hint = "한국어" if language == "ko" else "영어"

    return f"""
너는 스타트업 IR 발표에서 사용할 슬라이드별 대본을 작성하는 전문 카피라이터다.
아래 JSON은 {slide.number}번 슬라이드의 구성 요소다.

[슬라이드 데이터]
{slide_json}

[작성 지침]
- 말투는 {tone}로 유지하고, {language_hint}로 작성한다.
- narration은 2~3문장(약 170~260자)으로 구성하고 자연스러운 흐름을 만든다.
- 각 문장은 해당 슬라이드의 메시지를 명확히 전달해야 한다.
- talkPoints 배열에는 발표자가 강조할 핵심 포인트 3개를 25~40자 이내로 요약한다.
- JSON 외의 설명이나 코드 블록을 출력하지 말고, 아래 형식을 정확히 따른다.

[출력 형식]
{{
  "slideNumber": {slide.number},
  "title": "",
  "narration": "",
  "talkPoints": ["", "", ""]
}}

- title에는 슬라이드를 대표하는 12~18자 내외의 제목을 넣는다.
- narration과 talkPoints에는 줄바꿈을 사용하지 않는다.
""".strip()


def extract_json_payload(content: str) -> Optional[dict]:
    stripped = content.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped)
    candidates: List[str] = []
    if match:
        candidates.append(match.group(1).strip())
    candidates.append(stripped)

    for candidate in candidates:
        if not candidate:
            continue
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue
    return None


def request_script(client: OpenAI, prompt: str, model: str, temperature: float) -> dict:
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "너는 슬라이드 데이터를 기반으로 발표 대본을 JSON으로 작성하는 전문가야.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    content = response.choices[0].message.content or ""
    payload = extract_json_payload(content)
    if payload is None:
        raise ValueError("모델 응답을 JSON으로 파싱할 수 없습니다.")
    return payload


def build_batch_prompt(
    slides: List[SlidePayload], style: str, language: str
) -> str:
    """여러 슬라이드를 한 번에 요청할 프롬프트를 구성한다."""

    instructions = [
        "너는 스타트업 IR 발표 슬라이드 대본을 JSON으로 작성하는 전문가다.",
        f"이번에는 총 {len(slides)}개의 슬라이드를 처리해야 한다.",
        "각 슬라이드에 대해 JSON 객체를 출력하고, 슬라이드 사이에는 '---' 구분선을 넣는다.",
        "응답에는 설명을 추가하지 말고 JSON과 구분선만 포함한다.",
        "출력 JSON 구조는 아래 형식을 따른다:",
        '{"slideNumber": <번호>, "title": "", "narration": "", "talkPoints": ["", "", ""]}',
        "title은 12~18자, narration은 2~3문장(170~260자), talkPoints는 3개의 핵심 요약(25~40자)으로 작성한다.",
        "말투와 언어 지침은 각 슬라이드 섹션에서 제공한다.",
    ]

    sections: List[str] = []
    for slide in slides:
        slide_prompt = build_prompt(slide, style, language)
        sections.append(f"[슬라이드 {slide.number} 지침]\n{slide_prompt}")

    return "\n\n".join(instructions + sections)


def request_script_batch(
    client: OpenAI,
    slides: List[SlidePayload],
    style: str,
    language: str,
    model: str,
    temperature: float,
) -> List[dict]:
    prompt = build_batch_prompt(slides, style, language)
    response = client.chat.completions.create(
        model=model,
        temperature=temperature,
        messages=[
            {
                "role": "system",
                "content": "너는 슬라이드 데이터를 기반으로 발표 대본을 JSON으로 작성하는 전문가야.",
            },
            {"role": "user", "content": prompt},
        ],
    )

    print(prompt)

    content = response.choices[0].message.content or ""
    parts = re.split(r"\n?---+\n?", content.strip())
    payloads: List[dict] = []
    for part in parts:
        snippet = part.strip()
        if not snippet:
            continue
        payload = extract_json_payload(snippet)
        if payload is None:
            raise ValueError("배치 응답에서 JSON을 파싱할 수 없습니다.")
        payloads.append(payload)

    if len(payloads) != len(slides):
        raise ValueError(
            f"배치 응답 개수 불일치: 기대 {len(slides)}개, 실제 {len(payloads)}개"
        )
    return payloads


def main() -> None:
    args = parse_args()
    slides = load_latest_slides(args.slides_dir)
    if args.max_slides:
        slides = slides[: args.max_slides]

    batch_size = max(1, args.batch_size)
    client = OpenAI()

    results: List[dict] = []
    for start in range(0, len(slides), batch_size):

        batch = slides[start : start + batch_size]
        label = ", ".join(str(slide.number) for slide in batch)
        print(f"➡️ 슬라이드 {label} 배치 처리 중...", flush=True)
        try:
            if len(batch) == 1:
                payloads = [
                    request_script(
                        client,
                        build_prompt(batch[0], args.style, args.language),
                        args.model,
                        args.temperature,
                    )
                ]
            else:
                payloads = request_script_batch(
                    client,
                    batch,
                    args.style,
                    args.language,
                    args.model,
                    args.temperature,
                )
        except Exception as exc:  # noqa: BLE001
            print(f"⚠️ 슬라이드 {label} 배치 생성 실패: {exc}", file=sys.stderr)
            continue

        for slide, payload in zip(batch, payloads):
            payload.setdefault("slideNumber", slide.number)
            results.append(payload)
            print(f"✅ 슬라이드 {slide.number} 대본 생성 완료")

    if not results:
        raise RuntimeError("대본 생성 결과가 없습니다.")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    output_path = output_dir / f"slide_scripts_{timestamp}.json"
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(results, handle, ensure_ascii=False, indent=2)

    print(f"\n🎉 총 {len(results)}개의 대본을 저장했습니다: {output_path}")


if __name__ == "__main__":
    main()
