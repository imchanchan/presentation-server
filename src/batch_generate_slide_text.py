from prompt import build_prompt


import os
import json
import re
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from openai import OpenAI

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

DATA_PATH = ROOT_DIR / ".data" / "EX2.json"
OUTPUT_DIR = ROOT_DIR / "slides"

IMMUTABLE_META_KEYS = {"leftNumber", "leftTitle", "leftSubtitle", "rightTitle", "rightNumber"}

client = OpenAI()

# ---------------------------
# 모델 설정
# ---------------------------
MODEL = "o4-mini-2025-04-16"
client = OpenAI()


# ---------------------------
# JSON 블록 추출 (--- 또는 {…})
# ---------------------------

def save_split_json_results(content: str, start:int, end:int, output_dir: Path, prefix: str = "slide") -> list[Path]:
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

    # 각 블록 JSON 파싱 + 저장
    for idx, block in enumerate(parts, start=start):
        try:
            data = json.loads(block)
        except json.JSONDecodeError:
            print(f">> JSON 파싱 실패 (#{idx}) → 텍스트로 저장")
            data = {"raw_text": block}

        # 파일 저장
        out_path = output_dir / f"{prefix}{idx}_{timestamp}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        saved_files.append(out_path)
        print(f"✅ {prefix}{idx} 저장 완료 → {out_path}")

    print(f"\n 총 {len(saved_files)}개 JSON 저장 완료")
    return saved_files

# ---------------------------
# GPT 호출 (배치 처리)
# ---------------------------

import json
import re
from datetime import datetime
from pathlib import Path



def call_gpt_with_context(html: str, instruction: str) -> list[dict]:
    """하나의 HTML과 instruction(배치 단위 프롬프트)을 입력받아 여러 JSON 결과를 반환"""
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": "주어진 HTML정보로 IR Deck 슬라이드를 만들어야해. 너는 HTML 정보를 사용해 슬라이드별 필요한 텍스트를 JSON으로 구조화하는 전문가야."},
            {"role": "user", "content": f"다음은 HTML 전체 내용이다:\n{html}"},
            {"role": "user", "content": instruction},
        ]
    )

    result = resp.choices[0].message.content.strip()

    print("😎 GPT 결과: \n", result)
    return result

# ---------------------------
# 슬라이드 저장 함수
# ---------------------------
def save_slide_json(slide_num: int, slide_json: dict):
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_path = OUTPUT_DIR / f"slide{slide_num}_{timestamp}.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(slide_json, f, ensure_ascii=False, indent=2)
    print(f"✅ slide{slide_num} 저장 완료 → {out_path}")


# ---------------------------
# 메인 배치 처리
# ---------------------------
def main():
    # 1) HTML 로드 (수정 필요 시 이 부분만 교체)
    with open(DATA_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    # 2) 배치 그룹 정의
    batches = [
        (1, 3, "표지 + 외내부동기 + 아이템필요성"),
        (4, 5, "TAM·SAM·SOM + 시장분석"),
        (6, 8, "해결방안 + 핵심가치 + 개발방안"),
        (9, 10, "고객검증 + 경쟁사분석 및 경쟁력"),
        (11, 14, "비즈니스모델 + 수익모델 + 시장전략 + 성과"),
        (15, 16, "로드맵 + 자금조달 및 소요계획"),
        (17, 18, "팀소개 + 비전 및 결론"),
    ]

    # 3) 각 배치 실행
    for (start, end, desc) in batches:
        print(f"\n🚀 [배치 {start}-{end}] {desc} 생성 중...")

        prompt = ""
        for i in range(start, end+1):
            prompt += "="*10 + "\n" + f"해당슬라이드번호는 {i} 슬라이드입니다. 추출 프롬프트는 다음과 같습니다.\n >>" + build_prompt(i) + "\n" + "="*10 + "\n"


        instruction = f"""
아래 HTML 문서를 기반으로, 슬라이드 {start}~{end}에 해당하는 내용을 각각 독립된 JSON 객체로 생성하세요.
각 슬라이드는 --- 로 구분하세요.
JSON 구조는 슬라이드별 정의를 엄격히 따라야 하며, 불필요한 설명문이나 코드 블록은 포함하지 마세요.

[가장 중요]
** 슬라이드별 추출 형식을 명심하세요! **
** 추출형식에서 제시된 json 키값을 수정하면 절대 안됩니다. 그대로 사용합니다. 새로운 키를 추가하거나 이름을 바꾸지 마세요. **
**JSON 구조(중괄호·대괄호·쉼표·따옴표)와 필드 순서는 예시와 동일하게 유지하세요.**
** 최종 추출되는 json 객체는 {end-start+1}개입니다.**
        """ + prompt

        print('프롬프트: ', instruction)

        results = call_gpt_with_context(html, instruction)
        
        output_dir = Path("/Users/chanchan/Downloads/MVP IR DECK (3)/slides")
        save_split_json_results(results, start, end , output_dir)

        # for i, slide_json in enumerate(results, start=start):
        #     save_slide_json(i, slide_json)

        print(f"✅ 배치 {start}-{end} 완료 ({end-start+1}개 슬라이드)\n")

    print("\n 모든 배치(8덩어리) 생성 완료!")


if __name__ == "__main__":
    main()