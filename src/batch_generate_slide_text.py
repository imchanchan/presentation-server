import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from time import perf_counter

import aiohttp
from dotenv import load_dotenv

from prompt_ba import message_prompt

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

# ---------------------------
# 모델 설정
# ---------------------------
MODEL = "o4-mini-2025-04-16"
API_URL = "https://api.openai.com/v1/chat/completions"
REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=120)

# 재시도 전략
MAX_ATTEMPTS_PER_BATCH = 3
BASE_BACKOFF_SECONDS = 2.0


# -----------------------------
# * 기본 배치 구성을 사용 : no
# -----------------------------
# 기본 배치 구간 정의 (start, end, description)
DEFAULT_BATCH_DEFINITIONS: Tuple[Tuple[int, int, str], ...] = (
    (1, 3, "표지 + 외내부동기 + 아이템필요성"),
    (4, 5, "TAM·SAM·SOM + 시장분석"),
    (6, 8, "해결방안 + 핵심가치 + 개발방안"),
    (9, 10, "고객검증 + 경쟁사분석 및 경쟁력"),
    (11, 14, "비즈니스모델 + 수익모델 + 시장전략 + 성과"),
    (15, 16, "로드맵 + 자금조달 및 소요계획"),
    (17, 18, "팀소개 + 비전 및 결론"),
)

# 디버그 시 실패한 배치 raw 응답 저장
DEBUG_DUMP_FAILED_OUTPUT = os.getenv("DEBUG_DUMP_FAILED_OUTPUT", "0") == "1"


@dataclass
class Batch:
    start: int
    end: int
    desc: str
    attempt: int = 1


@dataclass
class BatchResult:
    batch: Batch
    success: bool
    summary: str
    messages: List[str]


def _default_batches() -> List[Batch]:
    return [Batch(start, end, desc) for start, end, desc in DEFAULT_BATCH_DEFINITIONS]

def _parse_batch_string(entry: str) -> Batch:
    """start-end[:desc] 형태 문자열을 Batch로 변환 (단일 번호도 허용)."""
    match = re.match(r"^(\d+)(?:-(\d+))?(?::(.+))?$", entry.strip())
    if not match:
        raise ValueError(
            f"배치 입력 '{entry}' 형식을 인식할 수 없습니다. 예) 1-3:표지"
        )

    start, end, desc = match.groups()
    start_i = int(start)
    end_i = int(end) if end else start_i
    if end_i < start_i:
        raise ValueError(f"배치 입력 '{entry}'에서 끝({end_i})이 시작({start_i})보다 작습니다.")

    description = desc.strip() if desc else f"슬라이드 {start_i}~{end_i}"
    return Batch(start_i, end_i, description)


def _prompt_use_default_batches() -> bool:
    while True:
        choice = input("기본 배치 구성을 사용할까요? (Y/n): ").strip().lower()
        if choice in ("", "y", "yes"):
            return True
        if choice in ("n", "no"):
            return False
        print("Y 또는 N으로 입력해주세요.")


def _prompt_manual_batches() -> List[Batch]:
    while True:
        raw = input(
            "사용할 배치 범위를 입력하세요 (예: 1-4, 5-7, 8-10 또는 1-4:표지): "
        ).strip()
        if not raw:
            print("빈 입력입니다. 다시 입력해주세요.")
            continue

        entries = [part.strip() for part in re.split(r"[,\s]+", raw) if part.strip()]
        if not entries:
            print("배치 정보를 인식하지 못했습니다. 다시 입력해주세요.")
            continue

        try:
            return [_parse_batch_string(entry) for entry in entries]
        except ValueError as exc:
            print(f"입력 오류: {exc}")


def prompt_batches_interactively() -> List[Batch]:
    if _prompt_use_default_batches():
        return _default_batches()
    return _prompt_manual_batches()


def _format_prompt_messages(messages: Union[str, List[Dict[str, Any]]]) -> str:
    """prompt_batch의 messages 리스트를 텍스트 블록으로 직렬화."""
    if isinstance(messages, str):
        return messages.strip()

    formatted_blocks: List[str] = []
    for idx, message in enumerate(messages, start=1):
        role = message.get("role", "user")
        content = (message.get("content") or "").strip()
        formatted_blocks.append(f"[{role} #{idx}]\n{content}")
    return "\n\n".join(formatted_blocks)


def build_instruction_for_batch(html: str, start: int, end: int) -> str:
    """배치 범위에 맞춘 instruction 문자열 생성."""
    prompt_body = ""
    for idx in range(start, end + 1):
        messages = message_prompt(idx, html)
        prompt_body += (
            "=" * 10
            + "\n"
            + f"해당슬라이드번호는 {idx} 슬라이드입니다. 추출 프롬프트는 다음과 같습니다.\n"
            + _format_prompt_messages(messages)
            + "\n"
            + "=" * 10
            + "\n"
        )
        # if idx == start :
            # print(messages)

    instruction = f"""
아래 HTML 문서를 기반으로, 슬라이드 {start}~{end}에 해당하는 내용을 각각 독립된 JSON 객체로 생성하세요.
각 슬라이드는 --- 로 구분하세요.
JSON 구조는 슬라이드별 정의를 엄격히 따라야 하며, 불필요한 설명문이나 코드 블록은 포함하지 마세요.

[가장 중요]
** 슬라이드별 추출 형식을 명심하세요! **
** 추출형식에서 제시된 json 키값을 수정하면 절대 안됩니다. 그대로 사용합니다. 새로운 키를 추가하거나 이름을 바꾸지 마세요. **
**JSON 구조(중괄호·대괄호·쉼표·따옴표)와 필드 순서는 예시와 동일하게 유지하세요.**
** 최종 추출되는 json 객체는 {end-start+1}개입니다.**
    """

    return instruction + prompt_body


def save_fallback_text(identifier: str, raw_text: str) -> Path:
    """JSON 파싱 실패 시 원본 텍스트를 보관하기 위한 fallback 파일 저장."""
    fallback_dir = OUTPUT_DIR / "fallback"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fallback_path = fallback_dir / f"{identifier}_{timestamp}.txt"
    fallback_path.write_text(raw_text, encoding="utf-8")
    return fallback_path


def save_split_json_results(
    content: str,
    start: int,
    end: int,
    output_dir: Path,
    prefix: str = "slide",
) -> Tuple[List[Path], List[str]]:
    """
    GPT 결과 텍스트(content)를 받아서
    '---' 기준으로 JSON 블록을 분리 후 각각 파일로 저장하는 함수.
    """

    # 없으면, 폴더 만들기
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 구분 기준으로 분리
    parts = re.split(r"\n?---+\n?", content)
    parts = [p.strip() for p in parts if p.strip()]

    saved_files = []
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    messages: List[str] = []

    # 각 블록 JSON 파싱 + 저장
    for idx, block in enumerate(parts, start=start):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            fallback_path = save_fallback_text(f"{prefix}{idx}_block", block)
            messages.append(f">> JSON 파싱 실패 (#{idx}) → fallback 저장: {fallback_path}")
            data = {"raw_text": block}

        # 파일 저장
        out_path = output_dir / f"{prefix}{idx}_{timestamp}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        saved_files.append(out_path)
        messages.append(f"✅ {prefix}{idx} 저장 완료 → {out_path}")

    messages.append(f"총 {len(saved_files)}개 JSON 저장 완료")
    return saved_files, messages


async def call_gpt_with_context(
    session: aiohttp.ClientSession,
    html: str,
    instruction: str,
    batch_label: str,
) -> Tuple[str, List[str]]:
    """하나의 HTML과 instruction(배치 단위 프롬프트)을 입력받아 여러 JSON 결과를 반환."""
    logs: List[str] = []
    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "system",
                "content": "주어진 HTML정보로 IR Deck 슬라이드를 만들어야해. 너는 HTML 정보를 사용해 슬라이드별 필요한 텍스트를 JSON으로 구조화하는 전문가야."
                " role: assistant에서 content는 참고만해야하는 예제야. 절대로 그대로 출력해서는 안돼.",
            },
            {"role": "user", "content": f"이번에는 이 사업 내용으로 작성해줘.:\n{html}"},
            {"role": "user", "content": instruction},
        ],
    }

    # payload = {
    #     "model" : MODEL, 
    #     "messages": [
    #         { "role": "developer", "content": "여기에 모델 행동 규칙/역할 지정" },
    #         { "role": "user", "content":  },
    #         { "role": "assistant", "content":  },
    #         { "role": "user", "content": instruct + html }
    #     ],
    # }

    headers = {
        "Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
        "Content-Type": "application/json",
    }

    async with session.post(API_URL, headers=headers, json=payload) as resp:
        raw_text = await resp.text()

        if resp.status >= 400:
            fallback_path = save_fallback_text(f"batch_{batch_label}_error", raw_text)
            logs.append(f"⚠️ API 호출 실패 (status={resp.status}) → fallback 저장: {fallback_path}")
            return "", logs

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError:
            fallback_path = save_fallback_text(f"batch_{batch_label}_response", raw_text)
            logs.append(f"⚠️ API 응답 JSON 파싱 실패 → fallback 저장: {fallback_path}")
            return "", logs

    result = data["choices"][0]["message"]["content"].strip()
    logs.append(f"😎 GPT 결과 (배치 {batch_label}):\n{result}")
    return result, logs


async def run_one_batch(session: aiohttp.ClientSession, html: str, batch: Batch) -> BatchResult:
    """배치 1건 실행."""
    start, end = batch.start, batch.end
    label = f"{start}-{end}"
    expected_count = end - start + 1
    started_at = perf_counter()
    messages: List[str] = []

    try:
        await asyncio.sleep(0.8)  # 가벼운 rate-limit 완화 딜레이

        instruction = build_instruction_for_batch(html, start, end)

        instruction_path = OUTPUT_DIR / f"instruction_{label}.txt"
        instruction_path.parent.mkdir(parents=True, exist_ok=True)
        instruction_path.write_text(instruction, encoding="utf-8")
        
        result_text, call_logs = await call_gpt_with_context(
            session=session,
            html=html,
            instruction=instruction,
            batch_label=label,
        )

        print("**html", len(html))
        print('**GPT:', result_text )
        messages.extend(call_logs)
        if not result_text:
            elapsed = perf_counter() - started_at
            summary = (
                f"⚠️ 배치 {label} 실패 (시도 {batch.attempt}/{MAX_ATTEMPTS_PER_BATCH}) "
                f"(소요 {elapsed:.2f}s)"
            )
            return BatchResult(batch=batch, success=False, summary=summary, messages=messages)

        # GPT 원본 응답을 txt로 보관
        result_dump_dir = OUTPUT_DIR / "raw_results"
        result_dump_dir.mkdir(parents=True, exist_ok=True)
        dump_path = result_dump_dir / f"result_{label}_{datetime.now().strftime('%Y%m%d-%H%M%S')}.txt"
        dump_path.write_text(result_text, encoding="utf-8")
        messages.append(f"📝 GPT 원본 응답 저장 → {dump_path}")

        saved_files, save_logs = save_split_json_results(
            content=result_text,
            start=start,
            end=end,
            output_dir=OUTPUT_DIR,
            prefix="slide",
        )
        messages.extend(save_logs)

        if len(saved_files) != expected_count:
            elapsed = perf_counter() - started_at
            msg = (
                f"⚠️ 배치 {label} 저장 개수 불일치 "
                f"(기대 {expected_count}개, 실제 {len(saved_files)}개) "
                f"(시도 {batch.attempt}/{MAX_ATTEMPTS_PER_BATCH}) "
                f"(소요 {elapsed:.2f}s)"
            )
            if DEBUG_DUMP_FAILED_OUTPUT:
                fallback_path = save_fallback_text(f"batch_{label}_mismatch", result_text)
                msg += f" → raw 저장: {fallback_path}"
                messages.append(f"RAW 저장 완료: {fallback_path}")
            return BatchResult(batch=batch, success=False, summary=msg, messages=messages)

        elapsed = perf_counter() - started_at
        summary = (
            f"✅ 배치 {label} 완료 ({len(saved_files)}개 슬라이드 저장) "
            f"(시도 {batch.attempt}/{MAX_ATTEMPTS_PER_BATCH}) "
            f"(소요 {elapsed:.2f}s)"
        )
        return BatchResult(batch=batch, success=True, summary=summary, messages=messages)

    except Exception as exc:  # 예상치 못한 예외는 로그 후 재시도
        elapsed = perf_counter() - started_at
        summary = (
            f"❌ 배치 {label} 예외 발생: {exc} "
            f"(시도 {batch.attempt}/{MAX_ATTEMPTS_PER_BATCH}) "
            f"(소요 {elapsed:.2f}s)"
        )
        if DEBUG_DUMP_FAILED_OUTPUT:
            fallback_path = save_fallback_text(f"batch_{label}_exception", str(exc))
            summary += f" → raw 저장: {fallback_path}"
            messages.append(f"RAW 저장 완료: {fallback_path}")
        return BatchResult(batch=batch, success=False, summary=summary, messages=messages)


async def process_batches_round(session: aiohttp.ClientSession, html: str, batches: List[Batch]) -> Tuple[List[Batch], List[str]]:
    failed_next: List[Batch] = []
    logs: List[str] = []

    for batch in batches:
        outcome = await run_one_batch(session, html, batch)
        print(outcome.summary)

        if not outcome.success and outcome.batch.attempt < MAX_ATTEMPTS_PER_BATCH:
            failed_next.append(
                Batch(
                    outcome.batch.start,
                    outcome.batch.end,
                    outcome.batch.desc,
                    outcome.batch.attempt + 1,
                )
            )

        logs.extend(outcome.messages)
        logs.append(outcome.summary)

    return failed_next, logs


async def run_all_batches_until_stable(session: aiohttp.ClientSession, html: str, initial_batches: List[Batch]) -> None:
    """
    실패한 배치를 재시도하면서 안정 상태까지 반복 실행.
    """
    round_idx = 1
    queue = list(initial_batches)

    while queue:
        print(f"\n>> 라운드 {round_idx} 시작 — {len(queue)}개 배치 순차 실행")
        failed_next, logs = await process_batches_round(session, html, queue)

        for line in logs:
            print(line)

        if not failed_next:
            print(f"\n✅ 라운드 {round_idx}에서 모두 성공 — 종료")
            return

        still_retryable = [b for b in failed_next if b.attempt <= MAX_ATTEMPTS_PER_BATCH]
        if not still_retryable:
            print("\n⚠️ 재시도 가능한 배치 없음 — 종료")
            return

        backoff = BASE_BACKOFF_SECONDS * (2 ** (round_idx - 1)) + random.uniform(0, 0.5)
        print(f"\n⏳ 다음 라운드 전 대기: {backoff:.2f}s (백오프)")
        await asyncio.sleep(backoff)

        queue = still_retryable
        round_idx += 1

def load_html() -> str:
    """EX2.json에서 content.html 필드를 읽어 HTML 문자열 반환."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"EX2.json 파일이 존재하지 않습니다: {DATA_PATH}")
    with DATA_PATH.open(encoding="utf-8") as f:
        data = json.load(f)

    html = data.get("content", {}).get("html", "")
    if not html:
        raise ValueError("'content.html' 필드가 없습니다.")
    
    return html



async def main() -> None:
    html = load_html()

    initial_batches = prompt_batches_interactively()

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        print(f"🚀 {len(initial_batches)}개 배치를 순차적으로 실행합니다.")
        await run_all_batches_until_stable(session, html, initial_batches)

    print("\n🎉 모든 배치 처리 파이프라인 종료")


if __name__ == "__main__":
    asyncio.run(main())
