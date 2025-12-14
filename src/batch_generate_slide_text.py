import asyncio
import json
import os
import random
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple
from time import perf_counter

import aiohttp
from dotenv import load_dotenv

from prompt import build_prompt

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

# 동시 실행 설정 및 재시도 전략
CONCURRENCY = 3
MAX_ATTEMPTS_PER_BATCH = 3
BASE_BACKOFF_SECONDS = 2.0

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


def build_instruction_for_batch(start: int, end: int) -> str:
    """배치 범위에 맞춘 instruction 문자열 생성."""
    prompt_body = ""
    for idx in range(start, end + 1):
        prompt_body += (
            "=" * 10
            + "\n"
            + f"해당슬라이드번호는 {idx} 슬라이드입니다. 추출 프롬프트는 다음과 같습니다.\n >>"
            + build_prompt(idx)
            + "\n"
            + "=" * 10
            + "\n"
        )

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
                "content": "주어진 HTML정보로 IR Deck 슬라이드를 만들어야해. 너는 HTML 정보를 사용해 슬라이드별 필요한 텍스트를 JSON으로 구조화하는 전문가야.",
            },
            {"role": "user", "content": f"다음은 HTML 전체 내용이다:\n{html}"},
            {"role": "user", "content": instruction},
        ],
    }

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

        instruction = build_instruction_for_batch(start, end)
        result_text, call_logs = await call_gpt_with_context(
            session=session,
            html=html,
            instruction=instruction,
            batch_label=label,
        )
        messages.extend()
        if not result_text:
            elapsed = perf_counter() - started_at
            summary = (
                f"⚠️ 배치 {label} 실패 (시도 {batch.attempt}/{MAX_ATTEMPTS_PER_BATCH}) "
                f"(소요 {elapsed:.2f}s)"
            )
            return BatchResult(batch=batch, success=False, summary=summary, messages=messages)

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
    sem = asyncio.Semaphore(CONCURRENCY)
    failed_next: List[Batch] = []
    results: List[Optional[BatchResult]] = [None] * len(batches)

    async def runner(idx: int, batch: Batch) -> BatchResult:
        async with sem:
            outcome = await run_one_batch(session, html, batch)
            results[idx] = outcome
            if not outcome.success and outcome.batch.attempt < MAX_ATTEMPTS_PER_BATCH:
                failed_next.append(
                    Batch(
                        outcome.batch.start,
                        outcome.batch.end,
                        outcome.batch.desc,
                        outcome.batch.attempt + 1,
                    )
                )
            return outcome  # ✅ 추가

    tasks = [asyncio.create_task(runner(idx, b)) for idx, b in enumerate(batches)]

    # ✅ 먼저 끝난 순서대로 실시간 로그 출력
    for finished in asyncio.as_completed(tasks):
        outcome = await finished
        print(outcome.summary)

    logs: List[str] = []
    for outcome in results:
        if outcome is None:
            continue
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
        print(f"\n>> 라운드 {round_idx} 시작 — {len(queue)}개 배치 동시 실행")
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
    
    initial_batches = [
        Batch(1, 3, "표지 + 외내부동기 + 아이템필요성"),
        Batch(4, 5, "TAM·SAM·SOM + 시장분석"),
        Batch(6, 8, "해결방안 + 핵심가치 + 개발방안"),
        Batch(9, 10, "고객검증 + 경쟁사분석 및 경쟁력"),
        Batch(11, 14, "비즈니스모델 + 수익모델 + 시장전략 + 성과"),
        Batch(15, 16, "로드맵 + 자금조달 및 소요계획"),
        Batch(17, 18, "팀소개 + 비전 및 결론"),
    ]

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        print(f"🚀 {len(initial_batches)}개 배치를 동시에 실행합니다.")
        await run_all_batches_until_stable(session, html, initial_batches)

    print("\n🎉 모든 배치 처리 파이프라인 종료")


if __name__ == "__main__":
    asyncio.run(main())
