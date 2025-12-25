from __future__ import annotations
from email import message
import json
from pathlib import Path
from datetime import datetime
import re
import os
from openai import OpenAI

# ---------------------------
# 경로 설정
# ---------------------------
from pathlib import Path
from dotenv import load_dotenv

# 현재 파일 기준 경로 설정
ROOT_DIR = Path(__file__).resolve().parents[1]  # 프로젝트 루트
SCRIPT_DIR = Path(__file__).resolve().parent  # 현재 scripts 폴더
load_dotenv(SCRIPT_DIR / ".env", override=True)  # .env가 scripts 폴더에 있을 경우

if not os.getenv("OPENAI_API_KEY"):
    raise RuntimeError(
        "OPENAI_API_KEY를 불러오지 못했습니다. .env 위치와 키 값을 다시 확인하세요."
    )

DATA_PATH = ROOT_DIR / ".data" / "retort_1213.json"
OUTPUT_DIR = ROOT_DIR / "slides"

IMMUTABLE_META_KEYS = {"leftNumber", "leftTitle", "leftSubtitle", "rightTitle", "rightNumber"}

client = OpenAI()


# ---------------------------
# 1️⃣ EX2.json 로드
# ---------------------------
def load_html() -> str:
    """EX2.json에서 content.html 필드를 읽어 HTML 문자열 반환."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"EX2.json 파일이 존재하지 않습니다: {DATA_PATH}")
    with DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    html = data.get("content", {}).get("html", "")
    if not html:
        raise ValueError("EX2.json 내부에 'content.html' 필드가 없습니다.")
    print(html)
    return html


# ---------------------------
# 2️⃣ GPT 호출
# ---------------------------
def _extract_json_text(content: str) -> str | None:
    """마크다운 코드 블록 등을 제거한 JSON 텍스트 추출."""
    stripped = content.strip()

    # ```json ... ``` 패턴을 우선 제거
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", stripped, re.IGNORECASE)
    if match:
        candidate = match.group(1).strip()
        if candidate:
            return candidate

    # 전체 문자열에서 중괄호 영역 추출
    if "{" in stripped and "}" in stripped:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start != -1 and end != -1 and end > start:
            candidate = stripped[start : end + 1].strip()
            if candidate:
                return candidate

    return None


# def call_gpt(prompt: str) -> dict:
#     """GPT에 프롬프트를 보내고 JSON 결과를 반환."""
#     response = client.chat.completions.create(
#         model = "o4-mini-2025-04-16",
#         messages=[
#             {"role": "system", "content": "너는 HTML 문서를 분석해 슬라이드 데이터를 JSON으로 생성하는 전문가야."},
#             {"role": "user", "content": prompt},
#         ],
#         temperature=1.0        
#     )

#     content = response.choices[0].message.content.strip()

#     candidates: list[str] = []
#     extracted = _extract_json_text(content)
#     if extracted:
#         candidates.append(extracted)

#     candidates.append(content)

#     for candidate in candidates:
#         try:
#             return json.loads(candidate)
#         except json.JSONDecodeError:
#             continue

#     print("⚠️ JSON 디코딩 실패. 원문을 raw_output으로 저장합니다.")
#     return {"raw_output": content}

# ======

def call_gpt(response: str) -> dict:
    """GPT에 프롬프트를 보내고 JSON 결과를 반환."""

    content = response.choices[0].message.content.strip()

    candidates: list[str] = []
    extracted = _extract_json_text(content)
    if extracted:
        candidates.append(extracted)

    candidates.append(content)

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            continue

    print("⚠️ JSON 디코딩 실패. 원문을 raw_output으로 저장합니다.")
    return {"raw_output": content}

# ====

def remove_immutable_meta(data: dict) -> dict:
    for key in IMMUTABLE_META_KEYS:
        data.pop(key, None)
    return data


# ---------------------------
# 3️⃣ 슬라이드별 프롬프트 생성
# ---------------------------
# from prompt import build_prompt
from prompt_ba import message_prompt

# ---------------------------
# 4️⃣ JSON 저장
# ---------------------------
def save_slide_json(slide_num: int, slide_json: dict) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUTPUT_DIR / f"slide{slide_num}_{timestamp}.json"

    with out_path.open("w", encoding="utf-8") as f:
        json.dump(slide_json, f, ensure_ascii=False, indent=2)

    print(f"✅ slide{slide_num} 저장 완료 → {out_path}")


# ---------------------------
# 5️⃣ 메인 실행
# ---------------------------
def main() -> None:
    html = load_html()

    for i in range(100,101):  # 1~18까지

        print(f">> GPT 슬라이드 {i} 생성 중...")

        # prompt = base + build_prompt(i) + end
        messages = message_prompt(i, html)
        print(len(messages))

        # print(messages)
        response = client.chat.completions.create(
            # model="o4-mini-2025-04-16",
            model="o4-mini-2025-04-16",
            messages= messages,
            # response_format={"type": "json_object"}
        )

        # slide_data = remove_immutable_meta(call_gpt(prompt))
        slide_data = remove_immutable_meta(call_gpt(response))
      
        save_slide_json(i, slide_data)

    print("\n🎉 모든 슬라이드 JSON 생성이 완료되었습니다!")


if __name__ == "__main__":
    main()
