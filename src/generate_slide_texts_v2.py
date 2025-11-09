from __future__ import annotations
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

DATA_PATH = ROOT_DIR / ".data" / "EX2.json"
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


def call_gpt(prompt: str) -> dict:
    """GPT에 프롬프트를 보내고 JSON 결과를 반환."""
    response = client.chat.completions.create(
        model="gpt-4-turbo",
        messages=[
            {"role": "system", "content": "너는 HTML 문서를 분석해 슬라이드 데이터를 JSON으로 생성하는 전문가야."},
            {"role": "user", "content": prompt},
        ],
        temperature=1.0,
    )

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


def remove_immutable_meta(data: dict) -> dict:
    for key in IMMUTABLE_META_KEYS:
        data.pop(key, None)
    return data


# ---------------------------
# 3️⃣ 슬라이드별 프롬프트 생성
# ---------------------------
def build_prompt(slide_num: int, html: str) -> str:
    """슬라이드 번호별로 맞춤형 프롬프트 생성."""
    base = (
        "아래 HTML 문서를 분석해 해당 슬라이드에 맞는 내용을 한국어 JSON 형식으로 출력하세요.\n"
        "반드시 하나의 JSON 객체만 순수 텍스트로 출력하고, 코드 블록이나 추가 문장은 절대 포함하지 마세요.\n"
        "JSON 예시에서 제시된 키와 자료형을 그대로 사용하고, 새로운 키를 추가하거나 이름을 바꾸지 마세요.\n"
        "JSON 구조(중괄호·대괄호·쉼표·따옴표)와 필드 순서는 예시와 동일하게 유지하세요.\n"
        "예시에 없는 추가 객체나 필드는 절대 만들지 마세요.\n"
        "값을 찾을 수 없으면 빈 문자열(\"\")로 두고, 배열은 빈 배열([])로 두세요.\n"
        "직관적이고 간결하게 핵심 문장만 추출하세요.\n\n"
    )

    if slide_num == 1:
        return f"""{base}
[슬라이드 1: 표지 (Cover Page)]
HTML:
{html[:]}
JSON 예시:
{{
  "subtitle": "",
  "mainTitle": "",
  "bottomTitle": ""
}}

[글자수 조건]
"subtitle": 최대 30자
"mainTitle": 최소 20자 - 최대 30자
"bottomTitle" : 최대 11자


조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML 내 텍스트 요소를 기준으로 다음 항목을 추출하거나, 내용이 명확히 존재하지 않을 경우 아래 가이드라인을 참고해 알맞게 생성하세요.

---

1️⃣ **subtitle**
- 슬라이드 상단의 부제(보통 작고 얇은 글씨) 텍스트를 추출합니다.
- 예: 연도, 프로그램명, 발표명 등 (ex. “2026년 ○○패키지 사업계획서 발표”)
- 날짜나 기관명이 포함되어 있다면 그대로 포함합니다.
- **없을 경우**: 발표 연도 + 문서 성격을 반영해 “2025년 ○○ 사업계획서 발표” 형태로 생성합니다.

2️⃣ **mainTitle**
- 중앙에 가장 크게 표시된 메인 제목을 추출합니다.
- 예: 핵심 사업명, 서비스명, 프로젝트명 등
- 줄바꿈(`\n`) 없이 하나의 문자열로 병합합니다.
- **없을 경우**: HTML 내 주요 키워드(서비스명, 프로젝트명 등)를 기반으로 핵심 메시지형 문장을 생성합니다.  
  (예: “○○ 프로젝트로 세상을 연결하다”)

3️⃣ **bottomTitle**
- 메인 제목 하단에 위치한 보조 제목이나 서비스 유형명 텍스트를 추출합니다.
- 일반적으로 제품·서비스명, 브랜드명, 또는 핵심 주제 요약이 들어갑니다.
- **없을 경우**: 발표 주제명이나 서비스명을 짧게 요약하여 생성합니다.  
  (예: “AI 기반 반려동물 케어 서비스”)

---

📌 **주의사항**
- 로고, 아이콘, 배경색 등 시각적 요소는 제외하세요.
- 줄바꿈이나 스타일 태그(`<br>`, `<b>`, `<span>`)는 무시하고 순수 텍스트만 추출하세요.
- 텍스트 간 띄어쓰기를 보정해 문장이 자연스럽게 이어지도록 합니다.
- 이 페이지는 **발표의 시작을 알리는 표지 슬라이드**로,  
  **발표 목적과 주제를 명확히 보여주는 내용**이 들어가야 합니다.

"""

    elif slide_num == 2:
        return f"""{base}
[슬라이드 2: 문제 정의 (Problem Definition)]
HTML:
{html[:]}
JSON 예시:
{{
  "title": "",
  "mainHeading": "",
  "description": "",
  "issue1Title": "",
  "issue1Description": "",
  "issue2Title": "",
  "issue2Description": "",
  "issue3Title": "",
  "issue3Description": ""
}}

### 🟪 [글자수 조건]:
- mainHeading: 완전한 한 문장으로, 약 20~35자 내외의 자연스러운 길이로 작성하세요.
- issue1Title: 약 5~10자 이내의 간결한 제목.
- issue1Description: 약 55~70자 내외의 완전한 문장.
- issue2Title: 약 5~10자 이내의 간결한 제목.
- issue2Description: 약 55~70자 내외의 완전한 문장.
- issue3Title: 약 5~10자 이내의 간결한 제목.
- issue3Description: 약 55~70자 내외의 완전한 문장.

### 🟩 조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 구성 요소를 기준으로 아래 항목을 추출하거나, 명확한 내용이 없는 경우 아래 가이드라인을 참고해 알맞게 생성하세요.

---

1️⃣ **mainHeading**
- 슬라이드 중앙에 가장 크게 표시된 핵심 문제 요약 문장을 추출합니다.  
- 현재 시장이나 고객이 직면한 대표적인 이슈를 담은 한 문장으로 정리하세요.  
- 불필요한 줄바꿈 없이 자연스러운 하나의 문장으로 출력합니다.  
- **없을 경우**: 외부·내부 문제를 아우르는 핵심 문장을 생성합니다. (예: “높아진 비용과 느린 서비스로 고객 불만이 확대되고 있다.”)

2️⃣ **description**
- 제목 아래 짧은 부제나 설명 문구가 있다면 추출합니다.  
- 부제 또는 요약 문장이 없다면 빈 문자열("")로 둡니다.  
- **없을 경우**: “이러한 문제는 서비스 이용자와 공급자 모두에게 구조적인 불편을 초래하고 있다.” 와 같이 핵심 요약 문장을 생성합니다.

3️⃣ **issue1Title**
- 첫 번째 박스(왼쪽)의 제목을 추출합니다.  
- 일반적으로 “비효율성”, “시간 낭비”, “복잡한 절차” 등 불편함을 표현한 단어 또는 짧은 문장입니다.  
- **없을 경우**: 시장의 외부 요인(예: 고객 불편, 산업 구조적 제약)을 반영한 핵심 문제를 요약해 생성합니다.

4️⃣ **issue1Description**
- 첫 번째 박스의 본문 설명 문장을 추출합니다.  
- 구체적인 문제 상황보다는 **핵심 개념 중심으로** 요약합니다.  
- 예: “복잡한 절차로 인해 고객의 이용 접근성이 낮다.”  
- **없을 경우**: “기존 프로세스가 복잡해 사용자의 접근성이 떨어진다.” 형태로 생성합니다.

5️⃣ **issue2Title**
- 두 번째 박스(가운데)의 제목을 추출합니다.  
- 일반적으로 “높은 비용”, “기회비용 증가”, “정보 단절” 등 구조적 한계를 나타내는 문구입니다.  
- **없을 경우**: 내부 요인(예: 운영 비효율, 기술적 제약)을 반영한 주제를 생성합니다.

6️⃣ **issue2Description**
- 두 번째 박스의 본문 설명 문장을 추출합니다.  
- 기존 해결책의 한계나 구조적 비효율을 중심으로 요약합니다.  
- **없을 경우**: “기존 시스템은 유지비용이 높고, 개선 여지가 제한적이다.” 형태로 생성합니다.

7️⃣ **issue3Title**
- 세 번째 박스(오른쪽)의 제목을 추출합니다.  
- 일반적으로 “정보 부족”, “의사결정의 어려움”, “시장 인식 부족” 등 정보나 판단 관련 문제입니다.  
- **없을 경우**: 정보의 비대칭성 또는 시장 내 인식 부족을 나타내는 주제를 생성합니다.

8️⃣ **issue3Description**
- 세 번째 박스의 본문 설명 문장을 추출합니다.  
- 고객이 올바른 결정을 내리기 어려운 이유나 정보 부재로 인한 문제를 개념 중심으로 서술합니다.  
- **없을 경우**: “정확한 정보 부족으로 인해 효율적인 의사결정이 어렵다.” 형태로 생성합니다.

---

📌 **주의사항**
- 각 항목은 HTML 내의 박스(또는 카드) 단위로 대응합니다.  
- 아이콘, 장식, 스타일 관련 텍스트는 제외합니다.  
- 모든 문장은 자연스러운 한 문장으로 병합하세요.  
- 값이 비어 있거나 확인되지 않을 경우, 위의 가이드라인을 참고해 논리적으로 자연스러운 텍스트를 생성하세요.  
- 이 페이지는 **문제 정의 단계**로, **외부적 요인과 내부적 요인을 함께 제시하며**  
  **현재 시장이나 서비스 환경에서 나타나는 대표적인 문제를 핵심 개념 중심으로 정리**해야 합니다.  
  구체적 사례보다는 **현상의 본질적인 문제 인식**을 명확히 전달하는 것이 목적입니다.

"""


    elif slide_num == 3:
        return f"""{base}
[슬라이드 3: 아이템 필요성 (Item Necessity)]
HTML:
{html[:]}
JSON 예시:
{{
  "mainTitle": "",
  "rows": [
    {{"division": "", "asIs": "", "toBe": ""}},
    {{"division": "", "asIs": "", "toBe": ""}},
    {{"division": "", "asIs": "", "toBe": ""}}
  ]
}}

### 🟪[글자수 조건]
mainTitle : 최소 20 최대 35
rows.division : 최대 10
rows.asIs : 최소 20 최대 28
rows.toBe : 최소 20 최대 28

### 🟩 조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 표 구조를 기준으로 아래 항목에 맞춰 텍스트를 추출하거나, 내용이 명확히 없을 경우 아래 가이드라인을 참고해 생성하세요.

---

1️⃣ **mainTitle**  
- 슬라이드 중앙 상단의 제목 텍스트를 추출합니다.  
- 일반적으로 “문제 해결의 필요성” 또는 “○○를 위한 새로운 연결 구조” 등 해결 의도를 한 문장으로 요약한 형태입니다.  
- **없을 경우**: 문제 정의(이전 슬라이드)의 핵심 이슈를 기반으로 “○○ 문제를 해결하기 위한 새로운 접근 필요” 형태로 생성합니다.

2️⃣ **rows.division**  
- 표의 첫 번째 열(구분)의 각 행 텍스트를 추출합니다.  
- 각 행은 비교의 관점을 제시하는 카테고리(예: 사용자 경험, 운영 효율, 기술 구조 등)입니다.  
- **없을 경우**: “이용자 측면”, “운영 측면”, “서비스 측면” 순으로 생성합니다.

3️⃣ **rows.asIs**  
- 표의 두 번째 열(AS IS)의 각 행 텍스트를 추출합니다.  
- 현재의 문제 상황, 한계, 비효율 등을 설명하는 영역입니다.  
- 예: “서비스 이용 과정이 복잡하여 고객 이탈이 잦음”, “데이터 관리가 수동으로 이루어짐”  
- **없을 경우**: 각 division 주제에 맞춰 “현재 시스템은 ○○하여 △△ 문제가 발생한다.” 형태로 생성합니다.

4️⃣ **rows.toBe**  
- 표의 세 번째 열(TO BE)의 각 행 텍스트를 추출합니다.  
- 개선 방향이나 목표 상태를 나타내는 영역입니다.  
- 예: “자동화된 관리 시스템을 통해 효율성을 향상시킴”, “사용자 경험을 단순화하여 접근성을 높임”  
- **없을 경우**: 각 asIs 내용과 대응되게 “○○을 개선하여 △△을 달성한다.” 형태로 생성합니다.

---

📌 **주의사항**
- 표의 행 순서를 반드시 유지하세요.  
- **rows는 반드시 3개 행으로 제한**합니다. (필요 시 공백 행을 ""로 채웁니다.)  
- 문장 간 구분은 마침표(`.`)를 기준으로 유지하되, HTML 태그는 모두 제거합니다.  
- 불필요한 아이콘명, 스타일, 장식 텍스트는 제외합니다.  
- 문장은 줄바꿈 없이 자연스럽게 이어지도록 병합합니다.  
- 값이 존재하지 않거나 확인되지 않을 경우, 위 가이드라인에 따라 논리적으로 일관된 텍스트를 생성하세요.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **문제 정의 단계에서 아이템의 필요성을 설명하는 비교형 구조 슬라이드**입니다.  
- **제목**은 해결하고자 하는 주제나 연결의 필요성을 간단히 표현하고,  
  **AS IS**는 현재의 불편·한계·비효율을, **TO BE**는 개선 후의 변화와 기대 효과를 제시해야 합니다.  
- **구분(division)**은 각 비교 항목의 관점을 나누어 주제를 명확히 구분하는 역할을 합니다.  
- 전체적으로 **AS IS → TO BE**를 통해 문제 인식에서 해결 방향으로 이어지는 **논리적 전환 흐름**을 강조해야 합니다.

"""

    elif slide_num == 4:
        return f"""{base}
[슬라이드 4: TAM·SAM·SOM 시장 분석 (Market Analysis)]
HTML:
{html[:]}
JSON 예시:
{{
  "leftTopTitle": "",
  "leftTopDescription": "",
  "tamLabel": "",
  "tamAmount": "",
  "tamMarketName": "",
  "tamDescription": "",
  "samLabel": "",
  "samAmount": "",
  "samMarketName": "",
  "samDescription": "",
  "somLabel": "",
  "somAmount": "",
  "somMarketName": "",
  "somDescription": "",
  "leftBottomTitle": "",
  "leftBottomDescription": ""
}}
이후 내가 문장이나 문구를 요청할 때는 다음 규칙을 따라.


예시: "안녕하세요, 저는 "GPT"입니다."
"" 속예시 문장은 공백포함 19자, 공백제외 17자인 경우야. 이 체계를 통해서 결과 생성해줘. 한 번에 글자수 조건에 맞게 생성해줘. 그리고 출력하기 전에 너가 글자수 계산해보고 안맞으면 맞을때까지 확인한 후에 출력해줘. 명사형 어미로 작성해줘. 문장 끝에 . 은 붙여줘.

### 🟪 [글자수 조건] :
  "leftTopTitle": "최소8 - 최대 10",
  "leftTopDescription": "최소48-최대62",

  "tamLabel": "TAM", ((고정))
  "tamAmount": "최대6",
  "tamMarketName": "최대14",
  "tamDescription": "최소48-최대62", 
  "samLabel": "SAM", ((고정))
  "samAmount": "최대6",
  "samMarketName": "최대14",
  "samDescription": "최소48-최대62",
  "somLabel": "SOM", ((고정))
  "somAmount": "최대6",
  "somMarketName": "최대14",
  "somDescription": "최소48-최대62",

  "leftBottomTitle": "최소8-최대10",
  "leftBottomDescription": "최소48-최대62"


### 🟩 조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 텍스트를 기준으로 아래 항목을 추출하거나, 내용이 명확하지 않을 경우 가이드라인을 참고해 생성하세요.

---

1️⃣ **leftTopTitle, leftTopDescription**
- 좌측 상단 서브섹션의 제목과 설명 문장을 추출합니다.  
- 이 영역은 **시장 성장 배경** 또는 **경쟁 환경 요약**을 설명하는 부분입니다.  
  예: “급성장 중인 반려동물 케어 시장”, “경쟁 심화 속 차별화된 서비스 필요”  
- **없을 경우**:  
  - leftTopTitle → “시장 성장 배경”  
  - leftTopDescription → “○○ 산업은 최근 △△ 트렌드로 인해 빠르게 성장하고 있으며, 경쟁 강도 또한 높아지고 있다.” 형태로 생성합니다.

---

2️⃣ **TAM / SAM / SOM 블록**
- TAM, SAM, SOM 각각은 원형 영역(또는 박스)에 해당합니다.
- 다음 항목을 추출하거나 생성합니다:
  - **tamLabel / samLabel / somLabel**: 원 내부의 레이블 (“TAM”, “SAM”, “SOM”).
  - **tamAmount / samAmount / somAmount**: 시장 규모 수치 (단위 포함).  
    예: “12조 5천억 원”, “4.2조 원”, “8,000억 원”  
    없으면 “-“로 표시하지 말고, “추정치 약 ○○억 원” 형태로 생성합니다.
  - **tamMarketName / samMarketName / somMarketName**: 원 오른쪽의 시장명.  
    예: “전 세계 반려동물 산업 시장”, “국내 온라인 유통 시장”, “타깃 플랫폼 시장”  
    없으면 “전체 시장”, “접근 가능한 시장”, “목표 시장”으로 순서대로 생성합니다.
  - **tamDescription / samDescription / somDescription**: 각 시장의 간단한 설명 문장.  
    예:  
      - TAM: “해당 산업 전반을 포함한 전체 시장 규모”  
      - SAM: “비즈니스가 실질적으로 접근 가능한 세분 시장”  
      - SOM: “현재 제품이 목표로 하는 실질 수익 시장 규모”  
    없을 경우 위 예시 설명으로 대체합니다.

---

3️⃣ **leftBottomTitle, leftBottomDescription**
- 좌측 하단 서브섹션의 제목과 설명을 추출합니다.  
- 이 영역은 **시장 인사이트** 또는 **시사점**을 요약하는 부분입니다.  
  예: “시장 진입 포인트”, “성장 가능성 및 차별화 전략”  
- **없을 경우**:  
  - leftBottomTitle → “시장 인사이트”  
  - leftBottomDescription → “TAM·SAM·SOM 분석을 통해 본 시장의 핵심 기회 영역은 △△이며, 향후 ○○ 분야에서의 확장성이 기대된다.” 형태로 생성합니다.

---

📌 **표기 규칙**
- 줄바꿈, 불릿(`•`), 스타일 태그(`<b>`, `<i>`, `<br>` 등)는 모두 제거하고 순수 텍스트만 사용합니다.  
- 단위(억, 조, 달러 등)는 그대로 유지합니다.  
- 값이 없을 경우 빈 문자열("")로 두지 말고, 위의 가이드라인을 따라 의미가 유지되도록 생성합니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **시장 규모와 구조를 정량적으로 설명하는 단계**입니다.  
- 상단에는 **시장 분석의 목적과 분석 범위(TAM·SAM·SOM)**를 제시하고,  
  본문은 **시장 성장 배경(좌측 상단)** + **TAM·SAM·SOM 비교(중앙)** + **시사점(좌측 하단)**의 3단 구성으로 구성됩니다.  
- TAM·SAM·SOM은 반드시 포함되어야 하며, 각각의 시장 구분과 정의를 명확히 구분하여  
  **시장 규모 → 접근 시장 → 목표 시장**으로 이어지는 논리적 구조를 표현해야 합니다.

"""


    elif slide_num == 5:
        return f"""{base}
[슬라이드 5: 고객 페르소나 (Customer Persona)]
HTML:
{html[:]}
JSON 예시:
{{
  "personName": "",
  "personInfoValues": "",
  "personInfoItems": [
    {{"label": "", "value": ""}},
    {{"label": "", "value": ""}},
    {{"label": "", "value": ""}},
    {{"label": "", "value": ""}},
    {{"label": "", "value": ""}}
  ],
  "lifestyleContent": "",
  "needsContent": "",
  "problemsContent": "",
  "infoSourceContent": "",
  "decisionFactorsContent": "",
  "avoidanceFactorsContent": ""
}}


### 🟪 [글자수 조건]
{{
  "personName": "홍길동" ((고정)), 
  "personInfoValues": "나이// 성별// 직업// 소득",
  "personInfoItems": [
    {{"label": "나이", "value": "최대10자"}},
    {{"label": "성별", "value": "최대10자"}},
    {{"label": "직업", "value": "최대10자"}},
    {{"label": "소득", "value": "최대10자"}},
  ],
  "lifestyleContent": "최소 40자 - 최대 55자",
  "needsContent": "최소 40자 - 최대 55자",
  "problemsContent": "최소 40자 - 최대 55자",
  "infoSourceContent": "최소 40자 - 최대 55자",
  "decisionFactorsContent": "최소 40자 - 최대 55자",
  "avoidanceFactorsContent": "최소 40자 - 최대 55자"
}}



---
### 🟩 조건:
- JSON 구조와 키 이름을 절대 변경하지 마세요.
- HTML의 시각적 구성에 따라 아래 항목 기준으로 텍스트를 추출하세요.
 
### 🟩 고객 정보 영역
1️⃣ **personName**  
- 고객 이름(또는 이름 일부 마스킹 포함 텍스트)을 추출합니다.  
- 이름이 제공되지 않은 경우 빈 문자열("")로 둡니다.

2️⃣ **personInfoValues**  
- 나이, 성별, 직업, 소득을 하나의 문자열로 연결합니다.  
- 각 항목 사이를 줄바꿈(`\n`)으로 구분하세요.

3️⃣ **personInfoItems**  
- 위 항목을 `{{ "label": "…", "value": "…" }}` 형태의 객체 배열로도 제공합니다.  
- 라벨은 “나이”, “성별”, “직업”, “소득”, “추가사항” 순서를 유지하고, 값이 없으면 빈 문자열을 사용하세요.  
- 배열 길이는 항상 4개로 유지합니다.

---

### 🟩 주요 콘텐츠 섹션
4️⃣ **lifestyleContent**  
- “라이프스타일” 섹션의 본문 전체를 추출합니다.  
- 불릿(•)으로 나누어, 2개 문장을 추출합니다.   
- 1문장 기준, 최소 40자 - 최대 55자 입니다. 

5️⃣ **needsContent**  
- “주요 니즈” 섹션의 설명 텍스트를 추출합니다.  
- 불릿(•)으로 나누어, 2개 문장을 추출합니다.   
- 1문장 기준, 최소 40자 - 최대 55자 입니다. 

6️⃣ **problemsContent**  
- “문제점” 섹션의 문장 전체를 추출합니다.  
- 불릿(•)으로 나누어, 2개 문장을 추출합니다.   
- 1문장 기준, 최소 40자 - 최대 55자 입니다. 

7️⃣ **infoSourceContent**  
- “정보 습득 경로” 섹션의 모든 문장을 추출합니다.  
- 불릿(•)으로 나누어, 2개 문장을 추출합니다.   
- 1문장 기준, 최소 40자 - 최대 55자 입니다. 

8️⃣ **decisionFactorsContent**  
- “구매 결정 요인” 섹션의 설명 텍스트를 추출합니다.  
- 불릿(•)으로 나누어, 2개 문장을 추출합니다.   
- 1문장 기준, 최소 40자 - 최대 55자 입니다. 

9️⃣ **avoidanceFactorsContent**  
- “회피 요인” 섹션의 문장 전체를 추출합니다.  
- 불릿(•)으로 나누어, 2개 문장을 추출합니다.   
- 1문장 기준, 최소 40자 - 최대 55자 입니다. 
---

📌 **주의사항**
- 각 항목은 반드시 원문 순서대로 추출하세요.  
- 문장 내 줄바꿈, 중복 공백, 불필요한 HTML 태그는 제거합니다.  
- 값이 없는 경우 빈 문자열("")로 둡니다.
"""



    elif slide_num == 6:
        return f"""{base}
[슬라이드 6: 해결 방안 (Solution)]
HTML:
{html[:]}
JSON 예시:
{{
  "leftNumber": "",
  "leftTitle": "",
  "leftSubtitle": "",
  "rightTitle": "",
  "rightNumber": "",
  "mainTitle": "",
  "cards": [
    {{"step": "", "icon": "", "title": "", "description": ""}},
    {{"step": "", "icon": "", "title": "", "description": ""}},
    {{"step": "", "icon": "", "title": "", "description": ""}},
    {{"step": "", "icon": "", "title": "", "description": ""}}
  ]
}}

### 🟪 [글자수 조건]
{{
  "mainTitle": "최소 20자- 최대 35자",
  "cards": [
    {{"step": "1단계", "icon": "아이콘", "title": "최대 12자", "description": "최소 47자 - 최대 60자"}},
    {{"step": "2단계", "icon": "아이콘", "title": "최대 12자", "description": "최소 47자 - 최대 60자"}},
    {{"step": "3단계", "icon": "아이콘", "title": "최대 12자", "description": "최소 47자 - 최대 60자"}},
    {{"step": "4단계", "icon": "아이콘", "title": "최대 12자", "description": "최소 47자 - 최대 60자"}}
  ]
}}

### 🟩 조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 구성에 따라 아래 기준으로 텍스트를 추출하거나, 내용이 명확하지 않을 경우 가이드라인을 참고해 생성하세요.
- 이 페이지는 해결 방안을 **단계적 프로세스(고객 여정 관점)**으로 제시합니다.

---

### 🟩 본문: 메인 타이틀
1) mainTitle
- 카드 그룹 위 중앙의 핵심 문장을 그대로 추출합니다. (줄바꿈/강조 태그 제거)
- **없을 경우**: “고객 관점의 단계별 해결 프로세스” 형태로 생성합니다.

---

### 🟩 카드 리스트 (cards: 4단계)
2) cards[i] (i=1..4)
- 각 카드(1~4단계)의 요소를 **시각 순서대로** 추출합니다.

| 키 | 설명 |
|----|------|
| step | 카드 상단 단계명 (“1단계”, “2단계”, “3단계”, “4단계”). 숫자만 있는 경우 “N단계”로 정규화. |
| icon | "아이콘"텍스트로 추출. 아이콘이라고 텍스트를 고정한다.  |
| title | 카드의 핵심 제목. **개선 목표** 또는 **핵심 기능**을 1문장으로 요약. |
| description | 카드 하단 설명. **고객이 무엇을 하고(행동)** → **어떤 혜택/성과를 얻는지(결과)**를 간결히 기술. 불필요한 기호/개행 제거. |

- **없을 경우 생성 가이드라인 (고객 여정 기반 기본 템플릿)**
  - 1단계 title 예: “진단 및 문제 인식”  
    - description 예: “고객이 현재 문제를 빠르게 파악하고 핵심 이슈를 확인한다.”
  - 2단계 title 예: “데이터 수집·연계”  
    - description 예: “필요 정보가 자동으로 수집·연동되어 수작업을 줄인다.”
  - 3단계 title 예: “개인화 처리/추천”  
    - description 예: “고객 상황에 맞춘 처리·추천을 제공해 의사결정을 돕는다.”
  - 4단계 title 예: “성과 관리·지속 개선”  
    - description 예: “성과 지표를 모니터링하고 피드백으로 서비스가 고도화된다.”

---

📌 작성/표기 규칙
- 단계(step) 순서는 **반드시 1 → 2 → 3 → 4**. 숫자/서수 표기는 “N단계”로 정규화.
- 문장 내 개행, 중복 공백, 특수문자는 제거. 아이콘/강조/스타일 태그는 제외.
- **고객 관점의 행동(Do) → 결과(Outcome)** 구조로 description을 간결히 작성.
- 값이 비어 있으면 빈 문자열("")로 두되, 핵심 구조가 비면 위 **생성 가이드라인**을 적용해 논리적으로 보완.

"""

    elif slide_num == 7:
        return f"""{base}
[슬라이드 7: 핵심 가치 (Core Values)]
HTML:
{html[:]}
JSON 예시:
{{
  "strength1Title": "",
  "strength1Description": "",
  "strength2Title": "",
  "strength2Description": "",
  "strength3Title": "",
  "strength3Description": "",
  "strength4Title": "",
  "strength4Description": "",
  "centerText": ""
}}

### 🟪 [글자수 조건]
{{
  "strength1Title": "최대 15자",
  "strength1Description": "최소 69자 - 최대 80자",
  "strength2Title": "최대 15자",
  "strength2Description": "최소 69자 - 최대 80자",
  "strength3Title": "최대 15자",
  "strength3Description": "최소 69자 - 최대 80자",
  "strength4Title": "최대 15자",
  "strength4Description": "최소 69자 - 최대 80자",
  "centerText": "제품/서비스 이미지" ((고정))
}}


### 🟩 조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 구조를 기준으로 아래 항목을 추출하거나, 내용이 명확하지 않을 경우 가이드라인을 참고해 생성하세요.

---

### 🟩 **본문: 강점(Strengths) 영역**
1) strength1Title ~ strength4Title  
- 네 개의 핵심 가치 또는 강점의 제목을 추출합니다.  
- 제목은 **가치의 핵심 키워드**를 간결히 표현합니다.  
  예: “수익 구조”, “고객 가치”, “서비스 강화”, “확장 가능성”  
- **없을 경우 생성 규칙**  
  - 순서대로 다음 항목을 기본값으로 사용합니다:  
    1. “수익 구조”  
    2. “서비스 경쟁력”  
    3. “고객 중심 가치”  
    4. “확장 가능성”

2) strength1Description ~ strength4Description  
- 각 강점 제목 아래의 설명 문장을 추출합니다.  
- 문장 내 줄바꿈 없이 하나의 문장으로 병합하고, 불필요한 공백이나 HTML 태그는 제거합니다.  
- 설명은 각 가치가 **사업에 기여하는 효과나 의미**를 중심으로 작성합니다.  
  예:  
  - “안정적인 매출 흐름을 통해 장기적인 성장 기반을 확보한다.”  
  - “서비스 품질을 개선하여 고객 만족도를 향상시킨다.”  
  - “고객 데이터를 기반으로 개인화된 경험을 제공한다.”  
  - “새로운 시장으로의 진출을 통해 비즈니스 확장성을 강화한다.”  
- **없을 경우 생성 규칙**  
  - 각 제목에 맞춰 다음 예시 형태로 생성합니다:  
    - strength1Description → “다양한 수익원을 확보하여 지속 가능한 매출 구조를 형성한다.”  
    - strength2Description → “경쟁사 대비 차별화된 서비스 품질을 제공한다.”  
    - strength3Description → “고객의 만족과 편의성을 중심으로 가치를 창출한다.”  
    - strength4Description → “서비스 확장성과 글로벌 시장 진출 가능성을 강화한다.”

---

⚪ **중앙 원형 영역**
3) centerText  
- "제품/서비스 이미지" 텍스트로 추출한다. 추출하는 텍스트는 "제품/서비스 이미지"으로 고정한다. 

---

📌 **작성 규칙**
- “강점 1~4”는 반드시 순서를 유지합니다.  
- 문장 내부의 줄바꿈, 불필요한 기호, 스타일 태그는 제거합니다.  
- 각 항목은 명확한 가치 중심 키워드(수익성·지속 가능성·차별화)를 중심으로 구성합니다.  
- 값이 비거나 확인되지 않을 경우, 기존 내용을 참고하여 논리적으로 자연스러운 텍스트를 생성합니다.


---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **해결 방안 중 핵심 가치(Core Values)**를 시각적으로 요약하는 단계입니다.  
- 중앙에는 **서비스의 핵심 개념 또는 브랜드 아이덴티티**를 배치하고,  
  주변에는 **수익 구조 / 서비스 강화 / 고객 가치 / 확장 가능성** 등  
  4개의 핵심 가치 항목을 짧고 명확하게 설명합니다.  
- 전체적으로 **수익성, 지속 가능성, 차별성**을 중심으로  
  제품·서비스의 **경쟁력과 사업적 가치**를 한눈에 인식할 수 있도록 구성합니다.

"""

    elif slide_num == 8:
        return f"""{base}
[슬라이드 8: 개발 계획 (Development Plan)]
HTML:
{html[:]}
JSON 예시:
{{
  "leftSectionTitle": "",
  "table": [
    {{"number": "", "content": "", "performance": "", "highlightedMonths": []}},
    {{"number": "", "content": "", "performance": "", "highlightedMonths": []}},
    {{"number": "", "content": "", "performance": "", "highlightedMonths": []}},
    {{"number": "", "content": "", "performance": "", "highlightedMonths": []}},
    {{"number": "", "content": "", "performance": "", "highlightedMonths": []}},
    {{"number": "", "content": "", "performance": "", "highlightedMonths": []}}
  ],
  "rightSectionTitle": "",
  "ipr": {{
    "title": "",
    "items": [
      {{"label": "", "date": ""}},
      {{"label": "", "date": ""}},
      {{"label": "", "date": ""}},
      {{"label": "", "date": ""}}
    ],
    "icon": ""
  }},
  "certification": {{
    "title": "",
    "items": [
      {{"label": "", "date": ""}},
      {{"label": "", "date": ""}},
      {{"label": "", "date": ""}},
      {{"label": "", "date": ""}}
    ],
    "icon": ""
  }}
}}

### 🟪 [글자수 조건]
leftSectionTitle : 최대 20  
table.content : 최소 12 최대 26  
table.performance : "내부" 또는 "외부" 중 선택  
table.highlightedMonths : 1~6 중 해당 월 번호를 쉼표로 구분하여 표기 (예: 1,2,3)  

rightSectionTitle : 최대 20  
ipr.title : 최대 20  
ipr.items.label : 최대 24  
ipr.items.date : yy.mm.  
certification.title : 최대 20  
certification.items.label : 최대 24  
certification.items.date : yy.mm.

조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 두 영역(좌측 표, 우측 인증 및 지재권)을 기준으로 다음을 추출하세요.

---

### 🟩 **좌측: 시제품 개발 계획**
1️⃣ **leftSectionTitle**  
- 표 상단의 제목 텍스트를 추출합니다. (예: “<시제품 개발 계획>”)  

2️⃣ **table**  
- 각 행을 순서대로 추출합니다.  
  - `number`: 순번  
  - `content`: 개발 내용 (12~26자 사이 한 문장)  
  - `performance`: 수행 주체 ("내부" 또는 "외부")  
  - `highlightedMonths`: 기간 영역에서 색으로 표시된 월 번호 (1~6 중 복수 가능)  

---

### 🟩 **우측: 지식재산권 및 인증 현황**
3️⃣ **rightSectionTitle**  
- 우측 섹션 상단의 제목 텍스트를 추출합니다. (예: “<지식재산권 및 인증 현황>”)  

4️⃣ **ipr (지식재산권 현황)**  
- `title`: 소제목 텍스트 (예: “-지식재산권 현황-”)  
- `items`: 각 항목의 `label`(최대 24자)과 `date`(yy.mm.)를 추출  
- `icon`: 아이콘으로 고정한다.

5️⃣ **certification (인증 현황)**  
- `title`: 소제목 텍스트 (예: “-인증 현황-”)  
- `items`: 각 항목의 `label`(최대 24자)과 `date`(yy.mm.)를 추출  
- `icon`: 아이콘으로 고정한다.

---

📌 **주의사항**
- 표의 순서(1~6행)와 리스트의 순서를 반드시 유지하세요.  
- 월, 연도, 날짜는 원문 그대로 유지합니다.  
- 불필요한 장식, 줄바꿈, HTML 태그는 모두 제거합니다.  
- 값이 없으면 "" 또는 []로 둡니다.
"""



    elif slide_num == 9:
        return f"""{base}
[슬라이드 9: 고객 검증 및 시장 반응 (Customer Validation)]
HTML:
{html[:]}
JSON 예시:
{{
  "journeyMapTitle": "",
  "validationStatusTitle": "",
  "journeyMap": [
    {{"step": "", "description": ""}},
    {{"step": "", "description": ""}},
    {{"step": "", "description": ""}},
    {{"step": "", "description": ""}},
    {{"step": "", "description": ""}},
    {{"step": "", "description": ""}}
  ],
  "validationTable": [
    {{"division": "", "content": "", "period": ""}},
    {{"division": "", "content": "", "period": ""}}
  ],
  "metrics": [
    {{"label": "", "number": ""}},
    {{"label": "", "number": ""}},
    {{"label": "", "number": ""}}
  ]
}}

### 🟪 [글자수 조건]
{{
  "journeyMapTitle": "",
  "validationStatusTitle": "",
  "journeyMap": [
    {{"step": "인지", "description": "최소 14자 - 최대 22자"}},
    {{"step": "고려", "description": "최소 14자 - 최대 22자"}},
    {{"step": "구매", "description": "최소 14자 - 최대 22자"}},
    {{"step": "사용", "description": "최소 14자 - 최대 22자"}},
    {{"step": "재사용", "description": "최소 14자 - 최대 22자"}},
    {{"step": "추천", "description": "최소 14자 - 최대 22자"}}
  ],
  "validationTable": [
    {{"division": "최대 7자", "content": "최소 25자 - 최대 42자", "period": "YY.MM."}},
    {{"division": "최대 7자", "content": "최소 25자 - 최대 42자", "period": "YY.MM."}}
  ],
  "metrics": [
    {{"label": "고객", "number": "최대4자 (예시: 30명)"}},
    {{"label": "매출", "number": "최대5자 (예시: 0.8억원)"}},
    {{"label": "평점", "number": "최대6자 (예시: 4.8/5점)"}}
  ]
}}



조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 레이아웃을 기준으로 아래 항목을 추출하거나, 내용이 명확하지 않을 경우 가이드라인을 참고해 생성하세요.

---

### 🟩 **왼쪽 영역: 고객 여정 지도 (Journey Map)**
1) journeyMapTitle  
- 고객 여정지도 상단의 제목을 추출합니다.  
- 예: “고객 여정 지도”, “Customer Journey Map”  
- **없을 경우**: “고객 여정 지도”로 생성합니다.

2) journeyMap (6단계 구조)  
- 인지 → 고려 → 구매 → 사용 → 재사용 → 추천 단계로 구성합니다.  
- 각 객체는 다음 항목을 포함합니다:  
  - step: 단계명 (예: 인지, 고려, 구매 등)  
  - description: 단계별 행동·반응 요약 문장 (줄바꿈 없이 한 문장으로 병합)  
- 불필요한 도형(→, ▼ 등)은 제외하고 순수 텍스트만 추출합니다.  
- **없을 경우 생성 규칙 (기본 템플릿)**  
  1️⃣ 인지 – “고객이 문제를 인식하고 서비스에 대한 관심을 갖기 시작함.”  
  2️⃣ 고려 – “해결 방안을 탐색하며 대안을 비교 검토함.”  
  3️⃣ 구매 – “서비스를 선택하고 실제 구매 또는 체험을 진행함.”  
  4️⃣ 사용 – “서비스를 이용하면서 품질과 편의성을 경험함.”  
  5️⃣ 재사용 – “서비스 만족 후 재구매 또는 반복 사용을 결정함.”  
  6️⃣ 추천 – “타인에게 서비스를 추천하며 긍정적 입소문이 확산됨.”

---

### 🟩 **오른쪽 영역: 시장 검증 현황 (Validation Table)**
3) validationStatusTitle  
- 오른쪽 영역 상단의 제목을 추출합니다.  
- 예: “시장 진출 및 고객 검증 현황”, “Market Validation Summary”  
- **없을 경우**: “시장 검증 현황”으로 생성합니다.

4) validationTable (2행 이상 가능)  
- 오른쪽 표의 각 행에서 다음 데이터를 추출합니다:  
  - division: 구분 항목 (예: 테스트 대상, 검증 방법 등)  
  - content: 내용 요약 (예: 사용자 인터뷰, 베타테스트 등)  
  - period: 진행 기간 (예: 24.03)  
- **없을 경우 생성 규칙 (기본 예시)**  
  | division | content | period |  
  |-----------|----------|---------|  
  | 테스트 대상 | 1차 베타 사용자 50명 대상 인터뷰 및 설문 진행 | 24.03 |  
  | 검증 방법 | 프로토타입 테스트 및 피드백 반영 과정 수행 | 24.04 |

---

### 🟩 **하단 영역: 검증 지표 (Metrics)**
5) metrics  
- 하단 원형 그래픽 내 수치와 항목명을 추출합니다.  
  - label: 원 아래 항목명 (예: “고객 수”, “매출액”, “만족도”)  
  - number: 원 안의 수치 (예: “1,200명”, “0.8억 원”, “4.8/5점”)  
- 순서는 왼쪽 → 오른쪽으로 유지합니다.  
- **없을 경우 생성 규칙 (기본 예시)**  
  | label | number |  
  |--------|---------|  
  | 고객 수 | 1,200명 |  
  | 매출액 | 0.8억 원 |  
  | 만족도 | 4.8/5점 |

---

📌 **작성/표기 규칙**
- 줄바꿈, 불릿(•), 특수기호, 스타일 태그(`<b>`, `<span>`, `<br>` 등)는 모두 제거하고 순수 텍스트만 남깁니다.  
- 모든 문장은 한 문장으로 병합하여 자연스럽게 연결합니다.  
- 표와 여정 순서는 반드시 원래 HTML 순서를 따릅니다.  
- 값이 존재하지 않으면 위 가이드라인을 바탕으로 논리적이고 자연스러운 문장을 생성합니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **해결 방안의 실효성을 검증**하고,  
  **고객 경험 흐름(여정지도)**과 **시장 검증 현황**,  
  **핵심 성과 지표**를 함께 제시하는 슬라이드입니다.  
- 왼쪽에서는 고객의 인지 → 추천까지의 경험 단계를 보여주고,  
  오른쪽에서는 검증 절차·대상·기간을 통해 **객관적 실증 근거**를 강조합니다.  
- 하단 지표는 고객 수, 매출, 만족도 등 **정량적 결과를 시각화**하여  
  해결 방안의 **시장 적합성(Product-Market Fit)**을 명확히 전달해야 합니다.

"""


    elif slide_num == 10:
        return f"""{base}
[슬라이드 10: 경쟁사 분석 및 경쟁력 (Competitor Analysis)]
HTML:
{html[:]}
JSON 예시:
{{
  "mainHeading": "",
  "headerDivision": "",
  "headerCompetitor1": "",
  "headerCompetitor2": "",
  "headerCompetitor3": "",
  "headerOurCompany": "",
  "row1Division": "",
  "row1Competitor1": "",
  "row1Competitor2": "",
  "row1Competitor3": "",
  "row1OurCompany": "",
  "row2Division": "",
  "row2Competitor1": "",
  "row2Competitor2": "",
  "row2Competitor3": "",
  "row2OurCompany": "",
  "row3Division": "",
  "row3Competitor1": "",
  "row3Competitor2": "",
  "row3Competitor3": "",
  "row3OurCompany": "",
  "row4Division": "",
  "row4Competitor1": "",
  "row4Competitor2": "",
  "row4Competitor3": "",
  "row4OurCompany": "",
  "row5Division": "",
  "row5Competitor1": "",
  "row5Competitor2": "",
  "row5Competitor3": "",
  "row5OurCompany": ""
}}

### 🟪 글자수조건:
mainHeading : 최소 30 최대 35  
headerDivision, headerCompetitor1~4 : 최대 10  
row1~5Division : 최대 10  
row1~5Competitor1~3 : 최소 22 최대 34  
row1~5OurCompany : 최소 22 최대 34  

조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 테이블 구조를 기준으로 아래 항목을 추출하거나, 내용이 불명확할 경우 가이드라인을 참고해 생성하세요.

---

### 🟩 **상단 메타 정보**
1) leftNumber, leftTitle, leftSubtitle, rightTitle, rightNumber  
- 슬라이드 상단의 번호, 섹션명, 영어 제목 등을 추출합니다.  
  - leftNumber: 좌측 상단 번호 (예: “04”)  
  - leftTitle: 메인 섹션명 (예: “경쟁사 분석 및 경쟁력”)  
  - leftSubtitle: 부제 (예: “자사 경쟁력 비교”)  
  - rightTitle: 우측 영어 섹션명 (예: “Competitor Analysis”)  
  - rightNumber: 우측 하단 페이지 번호 (예: “10”)  
- **없을 경우 생성 규칙**  
  - leftTitle → “경쟁사 분석 및 경쟁력”  
  - leftSubtitle → “시장 내 차별성과 포지셔닝”  
  - rightTitle → “Competitor Analysis”

---

### 🟩 **메인 제목 (mainHeading)**
2) mainHeading  
- 슬라이드 중앙 상단에 위치한 핵심 문구를 추출합니다.  
- 자사의 **핵심 경쟁 메시지** 또는 **시장 포지션 요약 문장**으로 구성됩니다.  
  예:  
  - “기술력과 사용자 경험으로 시장을 선도하는 ○○”  
  - “경쟁사 대비 높은 서비스 완성도와 고객 만족도 확보”  
- **없을 경우**: “자사 경쟁력 비교를 통한 시장 내 차별성 분석” 형태로 생성합니다.

---

### 🟩 **테이블 헤더 (header)**
3) headerDivision, headerCompetitor1~3, headerOurCompany  
- 표의 첫 번째 행(헤더)에 있는 각 열 제목을 추출합니다.  
  - headerDivision: 구분  
  - headerCompetitor1~3: 경쟁사명 (예: A사, B사, C사)  
  - headerOurCompany: 자사명 (예: 우리 회사명 또는 서비스명)  
- **없을 경우 생성 규칙**  
  - headerDivision → “구분”  
  - headerCompetitor1~3 → “경쟁사1”, “경쟁사2”, “경쟁사3”  
  - headerOurCompany → “자사”

---

### 🟩 **본문 테이블 행 (rows)**
4) row1Division ~ row5Division  
- 각 행의 첫 번째 열(구분 항목)을 추출합니다.  
- 일반적으로 다음과 같은 항목으로 구성됩니다:  
  - row1Division → “제품/서비스”  
  - row2Division → “가격”  
  - row3Division → “강점”  
  - row4Division → “약점”  
  - row5Division → “시장 포지션”  
- **없을 경우 위 기본 구조를 사용해 생성합니다.**

5) rowNCompetitor1~3, rowNOurCompany  
- 각 행에서 경쟁사 및 자사의 특징 설명을 추출합니다.  
- 줄바꿈이나 불릿(•)은 제거하고, 문장은 한 줄로 병합합니다.  
- **작성 방향 가이드라인**  
  - 경쟁사 열: 객관적인 시장 특징 또는 제공 서비스 중심으로 기술  
    (예: “가격은 저렴하지만 기능 제약이 존재함”)  
  - 자사 열: 기술적 우위, 서비스 품질, 브랜드 신뢰도 등 **강점 중심**으로 작성  
    (예: “AI 기반 자동화 기술로 운영 효율성을 극대화함”)  
- **없을 경우 생성 규칙 예시**
  - 제품/서비스:  
    - 경쟁사1~3 → “기본 기능 중심의 표준 서비스 제공”  
    - 자사 → “차별화된 기능과 통합 플랫폼 구조 제공”
  - 가격:  
    - 경쟁사1~3 → “가격 경쟁력 확보 중심”  
    - 자사 → “프리미엄 서비스 대비 합리적 가격 정책 운영”
  - 강점:  
    - 경쟁사1~3 → “시장 인지도 높음”, “유통망 확장”  
    - 자사 → “고객 경험 중심의 UI·UX 및 데이터 기반 맞춤형 서비스”
  - 약점:  
    - 경쟁사1~3 → “기술 고도화 한계”, “개인화 기능 부족”  
    - 자사 → “초기 인지도 확보 단계이나 빠른 성장 중”
  - 시장 포지션:  
    - 경쟁사1~3 → “기존 시장 점유 중심”, “특정 지역 집중형”  
    - 자사 → “고객 중심 혁신형 브랜드로 빠르게 성장 중”

---

📌 **표기 및 작성 규칙**
- 모든 텍스트는 줄바꿈 없이 완전한 문장으로 병합합니다.  
- HTML 태그(`<b>`, `<span>`, `<br>`, `<i>`) 및 불필요한 기호는 제거합니다.  
- 표의 열 순서와 행 순서를 반드시 원본 HTML 순서대로 유지합니다.  
- 값이 존재하지 않으면 위의 **생성 가이드라인**을 따라 논리적으로 일관된 텍스트를 생성합니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **경쟁사 대비 자사의 경쟁력**을 시각적으로 비교하여  
  **시장 내 포지셔닝(Positioning)**과 **차별적 강점(Unique Value Proposition)**을 강조합니다.  
- 상단에는 자사의 핵심 메시지를 제시하고,  
  본문 표에서는 **제품·가격·강점·약점·시장 포지션** 등을 기준으로  
  **3개 경쟁사와 자사**를 객관적으로 비교합니다.  
- 자사 항목은 단순 나열이 아니라, **기술력·서비스 품질·고객 신뢰도**를  
  근거로 한 **우위 포인트**를 강조해야 합니다.

"""

    elif slide_num == 11:
        return f"""{base}
[슬라이드 11: 비즈니스 모델 (Business Model)]
HTML:
{html[:]}

JSON 예시:
{{
  "nodes": [
    {{"id": "customer", "label": ""}},
    {{"id": "company", "label": ""}},
    {{"id": "partner", "label": ""}},
    {{"id": "pet", "label": ""}}
  ],
  "customerToCompanyTop": "",
  "customerToCompanyBottom": "",
  "companyToRestaurantLeft": "",
  "companyToRestaurantRight": "",
  "companyToRiderTop": "",
  "companyToRiderBottom": ""
}}

[글자수 조건]
nodes.label : 최대 4자  
모든 관계선 텍스트 : 최대 10자  

---

조건:
- 반드시 HTML의 내용을 **가장 우선적으로 반영**해야 합니다.  
- HTML 다이어그램에서 실제 표시된 텍스트(도형 내부, 선 위, 선 아래 등)를 직접 추출하세요.  
- 문맥상 불분명하거나 누락된 경우에만 가이드라인을 참고하여 보완 생성합니다.  
- JSON 구조와 키 이름은 절대 변경하지 마세요.  

---

### 🟩 1️⃣ 노드 정보 (nodes)
- 다이어그램에서 원, 네모 등 **참여자(엔터티)** 형태의 도형 내부 텍스트를 추출합니다.  
- 각 노드의 label은 4자 이내로 간결하게 작성합니다.  
- id는 고정이며 다음을 기준으로 HTML 내용과 가장 유사한 명칭을 사용합니다:
  - `customer` → 고객, 사용자, 소비자 등
  - `company` → 자사, 플랫폼, 서비스 운영자 등
  - `partner` → 제휴처, 공급자, 음식점, 매장 등
  - `pet` → 파트너, 라이더, 운송/배송 담당자 등

📌 **주의:**  
HTML 내 실제 명칭이 다를 경우 그대로 사용하되, 의미상 매칭되는 id에 연결하세요.  
(예: “음식점 사장님” → partner.label 로 입력)

---

### 🟩 2️⃣ 관계선 정보 (Flow Lines)
- HTML 내 선(→, ↔, 화살표 등)의 **위·아래 또는 인접한 텍스트**를 정확히 추출하세요.  
- 각 문장은 최대 10자, 불필요한 기호·줄바꿈은 제거하고 간결히 정리합니다.  
- 반드시 HTML 원문 표현을 우선 반영하며, 없을 경우 아래 구조를 참고해 보완합니다.

| 키 | 기본 의미 | HTML 미존재 시 예시 참고 |
|----|------------|----------------|
| customerToCompanyTop | 고객 → 회사 (상단) | 서비스 요청/결제 |
| customerToCompanyBottom | 회사 → 고객 (하단) | 결과 안내/혜택 제공 |
| companyToRestaurantLeft | 회사 → 제휴처 (왼쪽) | 주문 전달/정산 관리 |
| companyToRestaurantRight | 제휴처 → 회사 (오른쪽) | 상품 공급/매출 공유 |
| companyToRiderTop | 회사 → 파트너 (상단) | 배송 요청/배차 지시 |
| companyToRiderBottom | 파트너 → 회사 (하단) | 배송 완료/수수료 정산 |

📌 **주의:**  
- 위 표의 예시는 단순 참고용이며,  
  HTML의 실제 문구가 존재한다면 반드시 그것을 그대로 사용하세요.  
- 예시 문장을 그대로 복사하지 마세요.  

---

📘 **작성 규칙 요약**
- HTML에 나온 실제 텍스트를 최우선으로 사용합니다.  
- 문장은 명사형 또는 짧은 동사형으로 간결히 유지합니다.  
- 금액, 수치, 비율 등은 제거합니다.  
- 불필요한 `<b>`, `<span>`, `<br>` 등 HTML 태그와 기호는 모두 제외합니다.  
- 출력은 JSON 예시에 맞춰 정확히 매칭되도록 합니다.

---

🧭 **페이지 의도 (참고용)**
- 본 슬라이드는 비즈니스 모델의 참여자 관계(누가 누구에게 무엇을 주고받는지)를 시각적으로 표현합니다.  
- 주요 목적은 **거래 흐름(Flow)**과 **가치 교환(Value Exchange)**을 한눈에 전달하는 것입니다.  
- 따라서 HTML 내 도형 및 텍스트 정보를 기반으로,  
  실제 구조를 손상시키지 않는 수준의 보완만 허용합니다.
"""


    elif slide_num == 12:
        return f"""{base}
[슬라이드 12: 수익모델 (Revenue Model)]
HTML:
{html[:]}
JSON 예시:
{{
  "salesPlanTitle": "",
  "salesBasisTitle": "",
  "yAxisUnit": "",
  "deliveryFeeTitle": "",
  "deliveryFeeList": "",
  "adCostTitle": "",
  "adCostList": "",
  "yAxisLabel150": "",
  "yAxisLabel100": "",
  "yAxisLabel50": "",
  "yAxisLabel0": "",
  "xAxisLabel2025": "",
  "xAxisLabel2026": "",
  "xAxisLabel2027": "",
  "xAxisLabel2028": "",
  "chartCategories": [
    {{"key": "category1", "label": "", "color": ""}},
    {{"key": "category2", "label": "", "color": ""}}
  ],
  "chartData": [
    {{"year": 2025, "category1": 0, "category2": 0}},
    {{"year": 2026, "category1": 0, "category2": 0}},
    {{"year": 2027, "category1": 0, "category2": 0}},
    {{"year": 2028, "category1": 0, "category2": 0}}
  ]
}}


### 🟪 [글자수조건]
{{
  "salesPlanTitle": "< 매출 계획 >",
  "salesBasisTitle": "< 매출 산출 근거 >",
  "yAxisUnit": "",
  "deliveryFeeTitle": "- 배달 수수료 -",
  "deliveryFeeList": "",
  "adCostTitle": "- 광고 비용 -",
  "adCostList": "",
  "yAxisLabel150": "",
  "yAxisLabel100": "",
  "yAxisLabel50": "",
  "yAxisLabel0": "",
  "xAxisLabel2025": "",
  "xAxisLabel2026": "",
  "xAxisLabel2027": "",
  "xAxisLabel2028": "",
  "chartCategories": [
    {{"key": "category1", "label": "최대5자", "color": ""}},
    {{"key": "category2", "label": "최대5자", "color": ""}}
  ],
  "chartData": [
    {{"year": 2025, "category1": 0, "category2": 0}},
    {{"year": 2026, "category1": 0, "category2": 0}},
    {{"year": 2027, "category1": 0, "category2": 0}},
    {{"year": 2028, "category1": 0, "category2": 0}}
  ]
}}

조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 구성(그래프 + 근거표)을 기준으로 아래 항목을 추출하거나, 내용이 없을 경우 가이드라인에 따라 생성하세요.

---

### 🟩 **좌측 그래프 영역: 매출 계획 (Sales Plan)**
1) salesPlanTitle  
- 그래프 상단의 제목을 추출합니다.  
  예: “매출 계획”, “Annual Sales Plan”  
- **없을 경우**: “매출 계획”으로 생성합니다.

2) yAxisUnit  
- 그래프 왼쪽 단위 표기(예: “(단위: 억 원)”)를 추출합니다.  
- **없을 경우**: “(단위: 억 원)”으로 생성합니다.

3) yAxisLabel150 / yAxisLabel100 / yAxisLabel50 / yAxisLabel0  
- 그래프의 세로축 레이블(단위 없이 숫자)입니다.  
  예: 150, 100, 50, 0  
- **없을 경우**: 기본값 150 / 100 / 50 / 0 을 설정합니다.

4) xAxisLabel2025~xAxisLabel2028  
- 그래프 하단의 연도 라벨을 추출합니다.  
  예: 2025, 2026, 2027, 2028  
- **없을 경우**: 2025~2028 순서로 기본 생성합니다.

5) chartCategories  
- 그래프 범례(색상별 항목명)를 추출합니다.  
  - category1 → 첫 번째 항목 (예: “배달 수수료”, “구독 수익”)  
  - category2 → 두 번째 항목 (예: “광고 수익”, “제휴 수익”)  
  - color → 스타일에서 추출, 없으면 빈 문자열("")  
- **없을 경우 생성 규칙 (기본 템플릿)**  
  - category1.label → “기본 수익 항목 (예: 배달 수수료)”  
  - category2.label → “부가 수익 항목 (예: 광고 수익)”

6) chartData  
- 연도별 매출 수치 데이터를 추출합니다.  
  - category1: 첫 번째 수익 항목의 수치  
  - category2: 두 번째 수익 항목의 수치  
  - 단위 제거 후 숫자만 기입 (예: 7, 5)  
- **없을 경우 생성 규칙 (예시)**  
  | year | category1 | category2 |  
  |------|------------|------------|  
  | 2025 | 3 | 2 |  
  | 2026 | 6 | 3 |  
  | 2027 | 9 | 5 |  
  | 2028 | 12 | 6 |  

---

### 🟩 **우측 텍스트 영역: 매출 산출 근거 (Sales Basis)**
7) salesBasisTitle  
- 우측 텍스트 영역의 상단 제목을 추출합니다.  
  예: “매출 산출 근거”, “Revenue Basis”  
- **없을 경우**: “매출 산출 근거”로 생성합니다.

8) deliveryFeeTitle / deliveryFeeList  
- 첫 번째 수익 항목의 소제목 및 설명 목록입니다.  
  - deliveryFeeTitle 예: “- 배달 수수료 -”  
  - deliveryFeeList 예:  
    “• 0.5km 이내 - 건당 3,000원\n• 1.5km 이내 - 건당 3,500원”  
- 여러 줄은 `\n`으로 연결합니다.  
- **없을 경우 생성 규칙**  
  - deliveryFeeTitle → “- 구독 수익 -”  
  - deliveryFeeList →  
    “• 월 구독료 9,900원 기준\n• 누적 가입자 증가에 따른 월 매출 성장 반영”

9) adCostTitle / adCostList  
- 두 번째 수익 항목의 소제목 및 설명 목록입니다.  
  - adCostTitle 예: “- 광고 수익 -”  
  - adCostList 예:  
    “• 노출형 광고 - 수수료 6.8%\n• 제휴 프로모션 - 수익 분배율 9.8%”  
- **없을 경우 생성 규칙**  
  - adCostTitle → “- 광고 수익 -”  
  - adCostList →  
    “• 광고 노출 및 클릭당 과금(CPC)\n• 제휴 프로모션 수익 공유 구조 적용”

---

📊 **구성 가이드라인**
- 좌측은 **연도별 매출 목표(정량적)**,  
  우측은 **매출 산출 근거(정성적)**로 구성되어야 합니다.  
- 하나의 수익 항목만 있는 경우라도 **기타 항목을 추가하여 2개 수익원으로 구성**하세요.  
- 수치 값은 정확한 단위가 불명확하면 비례적 형태로 설정합니다 (예: 3 → 6 → 9 → 12).  
- 단위 표기(억, 원 등)는 제거하고 숫자만 남깁니다.  

---

📌 **작성/표기 규칙**
- 줄바꿈, 불릿(`•`), 스타일(`<b>`, `<span>`, `<br>`) 등은 모두 정리합니다.  
- 모든 텍스트는 자연스럽게 이어지도록 구성하며, 값이 없을 경우 위 **생성 가이드라인**에 따라 의미를 유지한 텍스트를 생성합니다.  
- **이 페이지에서는 반드시 “매출 계획”, “매출 산출 근거” 두 제목이 모두 포함**되어야 합니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **성장 전략의 핵심: 수익모델**을 시각적으로 제시합니다.  
- 왼쪽: **연도별 매출 계획(그래프)** → 성장 목표를 수치로 표현  
- 오른쪽: **매출 산출 근거(텍스트)** → 매출 계산의 근거 및 타당성 제시  
- 주요 목적은 **“매출 목표의 실현 가능성과 구조적 타당성”**을 보여주는 것입니다.  
- 수익 항목은 일반적으로 다음과 같습니다:
  - **category1:** 핵심 수익원 (예: 구독, 배달, 판매 수수료 등)  
  - **category2:** 부가 수익원 (예: 광고, 제휴, 데이터 판매 등)  
- 전체적으로 **매출 성장 근거 → 수익 항목별 구성 → 연도별 성과 예측**의 흐름이 명확히 드러나야 합니다.

"""


    elif slide_num == 13:
        return f"""{base}
[슬라이드 13: 시장 전략 (Market Strategy)]
HTML:
{html[:]}
JSON 예시:
{{
  "mainTitle": "",
  "subTitle": "",
  "strategyCards": [
    {{"id": "customer-focus", "title": "", "description": ""}},
    {{"id": "partner-expansion", "title": "", "description": ""}},
    {{"id": "benefit-enhancement", "title": "", "description": ""}}
  ]
}}


### 🟪 글자수조건
{{
  "mainTitle": "최소20자 - 최대35자",
  "subTitle": "최소 50자 - 최대 60자",
  "strategyCards": [
    {{"id": "customer-focus", "title": "최대 10자", "description": "최소 80자 - 최대 90자"}},
    {{"id": "partner-expansion", "title": "최대 10자", "description": "최소 80자 - 최대 90자"}},
    {{"id": "benefit-enhancement", "title": "최대 10자", "description": "최소 80자 - 최대 90자"}}
  ]
}}

조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 구조를 기준으로 텍스트를 추출하거나, 명확한 내용이 없을 경우 아래 가이드라인에 따라 생성하세요.

---

🟩 **상단 메타 정보**
1) leftNumber, leftTitle, leftSubtitle, rightTitle, rightNumber  
- 슬라이드 상단의 기본 정보(번호, 섹션명, 영어 제목 등)를 추출합니다.  
  - leftNumber: 좌측 상단 번호 (예: “07”)  
  - leftTitle: 메인 섹션명 (예: “시장 전략”)  
  - leftSubtitle: 부제목 (예: “시장 진입 및 확장 전략”)  
  - rightTitle: 우측 영어 섹션명 (예: “Market Strategy”)  
  - rightNumber: 우측 하단 페이지 번호 (예: “13”)  
- **없을 경우 생성 규칙**  
  - leftTitle → “시장 전략”  
  - leftSubtitle → “시장 진입 및 판매 전략”  
  - rightTitle → “Market Strategy”

---

🟩 **본문 상단: 시장 공략 핵심 방향**
2) mainTitle  
- 슬라이드 상단 중앙의 메인 문장(핵심 방향)을 추출합니다.  
- 시장 공략의 전체적인 목표나 브랜드 메시지를 요약한 문장입니다.  
  예: “차별화된 고객 경험으로 시장 점유율을 빠르게 확보한다.”  
- **없을 경우 생성 규칙**  
  - mainTitle → “핵심 고객층 집중 공략과 파트너십 확장을 통한 시장 점유율 확대”

3) subTitle  
- mainTitle 아래의 보조 문장으로, 구체적인 실행 요약 문구입니다.  
  예: “20~40대 핵심 고객층 집중 공략과 네트워크 강화를 통해 시장 경쟁력을 강화한다.”  
- **없을 경우 생성 규칙**  
  - subTitle → “핵심 타깃 고객층 확보, 파트너 네트워크 확장, 리워드 전략을 통한 지속 성장 추진”

---

🟩 **하단 전략 카드 (strategyCards)**
4) strategyCards 배열 (3개 항목 고정)
- 각 카드에는 하나의 주요 전략이 포함됩니다.  
- 제목(`title`)과 설명(`description`)을 각각 추출하거나, 없을 경우 생성 가이드라인을 적용하세요.

| id | title (전략명) | description (설명) |
|----|----------------|--------------------|
| customer-focus | 고객 집중 (또는 핵심 타깃 공략) | 20~40대 직장인, 핵심 수요층 등 명확한 타깃 중심의 집중 마케팅 전략 설명 |
| partner-expansion | 파트너 확장 (또는 네트워크 강화) | 지역 매장, 제휴 브랜드, 유통 채널 확장 등 파트너십 확대 전략 설명 |
| benefit-enhancement | 혜택 강화 (또는 리워드 전략) | 고객 리텐션 및 충성도 강화를 위한 포인트, 구독, 프로모션 전략 설명 |

- **없을 경우 생성 규칙 (기본 템플릿 예시)**  
  1️⃣ **customer-focus**  
     - title → “핵심 타깃 공략”  
     - description → “20~40대 주요 고객층을 중심으로 맞춤형 콘텐츠와 서비스를 제공해 초기 시장 점유율을 확보한다.”  
  2️⃣ **partner-expansion**  
     - title → “네트워크 강화”  
     - description → “지역 기반 매장과 전략적 제휴를 통해 공급망을 확장하고 브랜드 신뢰도를 높인다.”  
  3️⃣ **benefit-enhancement**  
     - title → “리워드 전략”  
     - description → “고객 포인트, 구독 혜택 등 보상 프로그램을 통해 재구매율과 고객 충성도를 높인다.”

---

📌 **작성/표기 규칙**
- HTML 내 줄바꿈(`<br>`, `<span>`, `<b>` 등)은 제거하고 순수 텍스트만 추출합니다.  
- 모든 설명(description)은 한 문장으로 병합하며, 문장 끝에는 마침표(`.`)를 붙입니다.  
- 각 전략 항목은 서로 다른 주제를 다뤄야 하며, 반복적인 표현은 피합니다.  
- 값이 없거나 비어 있을 경우 위의 **생성 가이드라인**을 바탕으로 의미가 유지되도록 채웁니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **성장 전략 중 시장 진입·확장 전략(Market Strategy)**을 제시하는 단계입니다.  
- **mainTitle**과 **subTitle**을 통해 전체 방향성을 명확히 제시하고,  
  **strategyCards**를 통해 구체적인 실행 전략을 3개 축으로 요약합니다:  
  1️⃣ 고객 집중 전략 (Customer Focus)  
  2️⃣ 파트너 확장 전략 (Partner Expansion)  
  3️⃣ 혜택 강화 전략 (Benefit Enhancement)  
- 목표는 **시장 확장 방향, 협력 구조, 고객 유지 전략**이 한눈에 보이도록 구성하는 것입니다.  
- 따라서 각 카드의 내용은 **실행 방식 + 기대 효과** 형태로 간결하게 작성하는 것이 바람직합니다.

"""


    elif slide_num == 14:
        return f"""{base}
[슬라이드 14: 정량적·정성적 성과 (Quantitative Results)]
HTML:
{html[:]}
JSON 예시:
{{
  "tableHeaderDivision": "",
  "tableHeaderYear1": "",
  "tableHeaderYear2": "",
  "tableHeaderYear3": "",
  "tableHeaderYear4": "",
  "row1Division": "",
  "row1Year1": "",
  "row1Year2": "",
  "row1Year3": "",
  "row1Year4": "",
  "row2Division": "",
  "row2Year1": "",
  "row2Year2": "",
  "row2Year3": "",
  "row2Year4": "",
  "row3Division": "",
  "row3Year1": "",
  "row3Year2": "",
  "row3Year3": "",
  "row3Year4": "",
  "row4Division": "",
  "row4Year1": "",
  "row4Year2": "",
  "row4Year3": "",
  "row4Year4": "",
  "row5Division": "",
  "row5Year1": "",
  "row5Year2": "",
  "row5Year3": "",
  "row5Year4": "",
  "row6Division": "",
  "row6Year1": "",
  "row6Year2": "",
  "row6Year3": "",
  "row6Year4": "",
  "row7Division": "",
  "row7Year1": "",
  "row7Year2": "",
  "row7Year3": "",
  "row7Year4": ""
}}


조건:
- 모든 글자수는 최대 15자
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 표 구조를 기준으로 아래 항목을 추출하거나, 내용이 없을 경우 가이드라인을 따라 논리적으로 생성하세요.


---

🟩 **테이블 헤더**
1) tableHeaderDivision  
- 첫 번째 헤더 셀(예: “구분”)을 추출합니다.  
- **없을 경우:** “구분”으로 설정합니다.

2) tableHeaderYear1~tableHeaderYear4  
- 나머지 헤더 셀(연도별 항목명)을 추출합니다.  
- 예: “2025년”, “2026년”, “2027년”, “2028년”  
- **없을 경우 기본값:** 2025년 / 2026년 / 2027년 / 2028년 순으로 생성합니다.

---

🟩 **테이블 본문 (row1~row7)**
- 표의 각 행은 아래의 고정 항목을 따릅니다.  
- 각 열은 연도별 목표 또는 실적 수치를 텍스트 그대로 추출합니다.  
- **단위(억 원, 명, 건, 개 등)는 반드시 유지합니다.**

| 행 번호 | 구분(Division) | 설명 / 생성 가이드라인 |
|----------|----------------|-------------------------|
| row1 | 매출 | “매출”이 없을 경우 생성하고, 연도별 매출 수치는 증가 추세로 설정 (예: 5억 원 → 10억 원 → 15억 원 → 20억 원) |
| row2 | 투자 | “투자”가 없을 경우 생성하고, 필요 시 “-” 또는 투자 유치 금액으로 채움 (예: “시드 5억 원”, “A라운드 20억 원”) |
| row3 | 기업가치 | “기업가치”가 없을 경우 생성하고, 매출 대비 성장 반영 (예: “30억 원”, “80억 원”, “150억 원”, “250억 원”) |
| row4 | 고용 | “고용”이 없을 경우 생성하고, 인원 수 증가 형태로 표현 (예: “5명”, “12명”, “25명”, “40명”) |
| row5 | 지재권 | “지재권”이 없을 경우 생성하고, 특허·상표권·저작권 등으로 구성 (예: “특허 1건”, “상표 3건”) |
| row6 | 인증 | “인증”이 없을 경우 생성하고, 비재무적 성과 중심 (예: “벤처기업 인증”, “ISO 9001 획득”) |
| row7 | 고객 | “고객”이 없을 경우 생성하고, 시장 확장성 기반 수치로 표현 (예: “5만 명”, “15만 명”, “30만 명”, “50만 명”) |

- 각 연도(year1~year4)는 tableHeaderYear1~4에 대응합니다.  
- 숫자 또는 단위가 함께 있는 경우 그대로 유지하세요.

---

📊 **표시 예시 (자동 생성 시 기본 템플릿)**

| 구분 | 2025년 | 2026년 | 2027년 | 2028년 |
|------|--------|--------|--------|--------|
| 매출 | 5억 원 | 10억 원 | 15억 원 | 20억 원 |
| 투자 | 시드 5억 원 | A라운드 20억 원 | B라운드 50억 원 | - |
| 기업가치 | 30억 원 | 80억 원 | 150억 원 | 250억 원 |
| 고용 | 5명 | 12명 | 25명 | 40명 |
| 지재권 | 특허 1건 | 특허 3건 | 상표 2건 | - |
| 인증 | 벤처기업 인증 | ISO 9001 획득 | - | - |
| 고객 | 5만 명 | 15만 명 | 30만 명 | 50만 명 |

---

📌 **작성/표기 규칙**
- 숫자, 단위(억 원, 명, 건 등)는 그대로 유지하고 변환하지 않습니다.  
- HTML 내 줄바꿈(`<br>`), 강조(`<b>`, `<span>`) 등은 제거하고 순수 텍스트만 사용합니다.  
- 모든 행(row1~row7)은 순서를 유지해야 하며, 값이 없으면 빈 문자열("")로 둡니다.  
- 텍스트는 한 줄로 병합하며, 숫자 간의 구분은 공백으로 처리하지 않습니다.  
- 필요 시 “-”를 사용해 결측을 명확히 표시할 수 있습니다.  

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **사업의 성과를 정량적·정성적 지표로 요약**하여  
  투자자에게 **성장성과 지속 가능성**을 시각적으로 전달하는 목적을 갖습니다.  
- 정량적 항목(매출, 투자, 기업가치, 고객)은 **수치 기반 성장 추이**를,  
  정성적 항목(지재권, 인증)은 **비재무적 성취 및 신뢰성 확보**를 나타냅니다.  
- 전체적으로 **연도별 성장 경향**과 **목표 달성 계획**을 명확히 보여주며,  
  “정량적·정성적 성과”라는 표현을 반드시 포함해 IR 문서의 공식성을 유지해야 합니다.

"""


    elif slide_num == 15:
        return f"""{base}
[슬라이드 15: 로드맵 (Roadmap)]
HTML:
{html[:]}
JSON 예시:
{{
  "mainTitle": "",
  "phase1Title": "",
  "phase1YearGoal": "",
  "phase1ObjectiveTitle": "",
  "phase1Strategy": "",
  "phase2Title": "",
  "phase2YearGoal": "",
  "phase2ObjectiveTitle": "",
  "phase2Strategy": "",
  "phase3Title": "",
  "phase3YearGoal": "",
  "phase3ObjectiveTitle": "",
  "phase3Strategy": "",
  "phase4Title": "",
  "phase4YearGoal": "",
  "phase4ObjectiveTitle": "",
  "phase4Strategy": ""
}}

### 🟪  [글자수조건]
{{
  "mainTitle": "최소20자-최대30자",
  "phase1Title": "Phase1",
  "phase1YearGoal": "최대10자",
  "phase1ObjectiveTitle": "최대20자",
  "phase1Strategy": "최소62자-최대75자",
  "phase2Title": "Phase2",
  "phase2YearGoal": "최대10자",
  "phase2ObjectiveTitle": "최대20자",
  "phase2Strategy": "최소62자-최대75자",
  "phase3Title": "Phase3",
  "phase3YearGoal": "최대10자",
  "phase3ObjectiveTitle": "최대20자",
  "phase3Strategy": "최소62자-최대75자",
  "phase4Title": "Phase4",
  "phase4YearGoal": "최대10자",
  "phase4ObjectiveTitle": "최대20자",
  "phase4Strategy": "최소62자-최대75자"
}}


조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML 내 시각적 구성(상단 비전 + 하단 단계별 로드맵)에 따라 다음 항목을 추출하거나, 내용이 없을 경우 가이드라인을 참고하여 생성하세요.


---

🟩 **상단 핵심 비전 (mainTitle)**
2) mainTitle  
- 슬라이드 상단 중앙의 핵심 문장(비전 또는 최종 목표)을 추출합니다.  
- 회사의 장기 방향성과 전체 로드맵의 목표를 한 문장으로 제시합니다.  
  예: “지속 가능한 성장과 글로벌 시장 진출을 위한 단계별 실행 전략”  
- **없을 경우 생성 규칙:**  
  - “지속 가능한 성장과 시장 확장을 위한 단계별 실행 로드맵”  

---

🟩 **하단 단계별 로드맵 구성 (Phase 1~4)**
- 각 Phase는 시간 순서대로 배치되며, **Title / YearGoal / ObjectiveTitle / Strategy**로 구성됩니다.  
- 단계별 내용은 아래 가이드라인을 따릅니다.

| Phase | Title | YearGoal | ObjectiveTitle | Strategy |
|--------|--------|-----------|----------------|-----------|
| 1️⃣ | **Phase1: 초기 구축 단계** | 연도 및 기간 (예: 2025) | “서비스 기반 구축” | “핵심 기술 개발, 프로토타입 완성, 초기 테스트 및 안정화” |
| 2️⃣ | **Phase2: 서비스 고도화 단계** | (예: 2026) | “운영 효율화 및 기능 확장” | “데이터 기반 개선, 사용자 피드백 반영, 시스템 최적화” |
| 3️⃣ | **Phase3: 시장 확장 단계** | (예: 2027) | “시장 진입 및 채널 확장” | “파트너십 구축, 마케팅 강화, 유통 채널 확대” |
| 4️⃣ | **Phase4: 브랜드 강화 단계** | (예: 2028) | “브랜드 가치 제고 및 지속 성장” | “해외 진출, 서비스 다각화, ESG 경영 기반 확립” |

- **없을 경우 생성 규칙 (기본 템플릿 적용)**  
  - phase1Title → “Phase 1. 초기 구축 단계”  
  - phase1YearGoal → “2025년”  
  - phase1ObjectiveTitle → “핵심 인프라 및 서비스 기반 구축”  
  - phase1Strategy → “기술 개발 및 안정화, 프로토타입 완성, 초기 사용자 테스트 진행”  

  - phase2Title → “Phase 2. 서비스 고도화 단계”  
  - phase2YearGoal → “2026년”  
  - phase2ObjectiveTitle → “운영 효율화 및 기능 개선”  
  - phase2Strategy → “사용자 피드백 반영, 데이터 기반 기능 고도화, 시스템 최적화”  

  - phase3Title → “Phase 3. 시장 확장 단계”  
  - phase3YearGoal → “2027년”  
  - phase3ObjectiveTitle → “시장 점유율 확대 및 수익 모델 확립”  
  - phase3Strategy → “전략적 제휴, 마케팅 강화, 신규 시장 진입 및 파트너 확대”  

  - phase4Title → “Phase 4. 브랜드 강화 단계”  
  - phase4YearGoal → “2028년”  
  - phase4ObjectiveTitle → “브랜드 신뢰도 강화 및 글로벌 진출 기반 확보”  
  - phase4Strategy → “서비스 다각화, 글로벌 진출, 지속 가능한 성장 체계 구축”  

---

📌 **작성 / 표기 규칙**
- HTML 내 줄바꿈(`<br>`, `<span>`, `<b>`, `<i>`)은 제거하고 순수 텍스트만 추출합니다.  
- 각 Phase의 문장은 한 문장으로 병합하며, 명사형 어미(`-화`, `-확대`, `-강화`)로 끝나도 자연스럽게 유지합니다.  
- 모든 항목은 공백 또는 빈 문자열("")로 두지 말고, 최소한 기본값이라도 채워서 단계 간 연속성을 유지하세요.  
- 연도(YearGoal)는 반드시 포함되어야 하며, **시간 흐름(2025 → 2026 → 2027 → 2028)** 순으로 배치합니다.  
- 단계가 4개 미만일 경우, **빈 Phase**는 공백("")으로 둡니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **사업의 성장 전략을 시간 축(Time-Line) 기반으로 표현하는 핵심 요약 슬라이드**입니다.  
- 각 단계(Phase)는 “초기 구축 → 고도화 → 확장 → 강화”의 순서로 구성되어야 하며,  
  연도별로 명확한 **목표(Goal)**와 **전략(Strategy)**을 제시해야 합니다.  
- 목적은 투자자에게 **“이 회사가 언제, 무엇을, 어떻게 실행할 것인가”**를 명확히 전달하는 것입니다.  
- 정량적 수치보다는 **실행 로드맵의 방향성과 실행력 중심**으로 서술하며,  
  전체 구조는 아래와 같이 자연스럽게 이어집니다:  
  **비전 제시 → 단계별 목표 제시 → 연도별 실행 전략 → 장기 성장 방향**

"""

    elif slide_num == 16:
        return f"""{base}
[슬라이드 16: 자금 조달·소요 계획 (Funding Plan)]
HTML:
{html[:]}
JSON 예시:
{{
  "headerNumber": "",
  "headerMainTitle": "",
  "headerEnglishTitle": "",
  "subtitle": "",
  "pageNumber": "",
  "fundingPlanTitle": "",
  "spendingPlanTitle": "",
  "fundingPlan1Year": "",
  "fundingPlan1Content": "",
  "fundingPlan2Year": "",
  "fundingPlan2Content": "",
  "fundingPlan3Year": "",
  "fundingPlan3Content": "",
  "fundingPlan4Year": "",
  "fundingPlan4Content": "",
  "chartCategories": [
    {{"name": "", "value": 0, "color": "", "labelColor": ""}},
    {{"name": "", "value": 0, "color": "", "labelColor": ""}},
    {{"name": "", "value": 0, "color": "", "labelColor": ""}},
    {{"name": "", "value": 0, "color": "", "labelColor": ""}}
  ]
}}


### 🟪 글자수조건
{{
  "fundingPlanTitle": "< 자금 조달 계획 >",
  "spendingPlanTitle": "< 자금 소요 계획 >",
  "fundingPlan1Year": "",
  "fundingPlan1Content": "최대 18자",
  "fundingPlan2Year": "",
  "fundingPlan2Content": "최대 18자",
  "fundingPlan3Year": "",
  "fundingPlan3Content": "최대 18자",
  "fundingPlan4Year": "",
  "fundingPlan4Content": "최대 18자",
  "chartCategories": [
    {{"name": "연구개발(R&D)", "value": 0, "color": "", "labelColor": ""}},
    {{"name": "인재 채용", "value": 0, "color": "", "labelColor": ""}},
    {{"name": "마케팅", "value": 0, "color": "", "labelColor": ""}},
    {{"name": "기타 운영비", "value": 0, "color": "", "labelColor": ""}}
  ]
}}

조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 레이아웃(좌측: 자금 조달 계획 / 우측: 자금 소요 계획)을 기준으로 아래 항목을 추출하거나, 내용이 없을 경우 가이드라인을 참고하여 생성하세요.


---

🟩 **왼쪽 영역: 자금 조달 계획 (Funding Plan)**
2) fundingPlanTitle  
- 좌측 영역의 상단 제목을 추출합니다.  
  예: “자금 조달 계획”, “Funding Plan”  
- **없을 경우:** “자금 조달 계획”

3) fundingPlan1~4Year / fundingPlan1~4Content  
- 연도별 자금 조달 계획을 추출합니다.  
  - Year: 연도 또는 단계 (예: “2025년”, “2026년”, “2027년”, “2028년”)  
  - Content: 조달 방식, 투자 단계, 조달 금액 등  
    예: “정부 R&D 과제 지원금 5억 원 확보”, “Seed 투자 유치 10억 원”, “Series A 30억 원 유치”  
- **없을 경우 생성 규칙 (기본 템플릿)**  
  | 연도 | 내용 |
  |-------|------|
  | 2025 | 정부지원사업 및 시드 투자(5억 원) 확보 |
  | 2026 | Series A 투자(20억 원) 유치 및 매출 기반 성장 자금 확보 |
  | 2027 | Series B 투자(50억 원) 유치, 서비스 확장 자금 조달 |
  | 2028 | IPO 또는 글로벌 투자 유치 단계 진입 |

---

🟩 **오른쪽 영역: 자금 소요 계획 (Spending Plan)**
4) spendingPlanTitle  
- 우측 상단 제목을 추출합니다.  
  예: “자금 소요 계획”, “Spending Plan”  
- **없을 경우:** “자금 소요 계획”

5) chartCategories (항목별 자금 사용 비율)
- 자금 사용 항목별 이름(name), 비율(value), 색상(color, labelColor)을 추출합니다.  
- 일반적으로 아래 항목들이 포함됩니다:  
  - R&D (연구개발)  
  - 인재 채용 (인건비, 조직 확충)  
  - 마케팅 (브랜딩, 광고 등)  
  - 기타 운영비 (사무, 관리, 플랫폼 운영 등)  
- **없을 경우 생성 규칙 (기본 예시)**  
  | name | value | color | labelColor |
  |------|--------|--------|------------|
  | 연구개발(R&D) | 40 | "" | "" |
  | 인재 채용 | 25 | "" | "" |
  | 마케팅 | 20 | "" | "" |
  | 기타 운영비 | 15 | "" | "" |

- `value`는 퍼센트(%) 또는 전체 금액 대비 비율로 입력하며, 숫자형으로 기입합니다.  
- `color`, `labelColor`는 HTML 스타일에 색상 코드가 있으면 추출하고, 없으면 빈 문자열("")로 둡니다.

---

📊 **페이지 기본 구성 예시 (자동 생성 기준)**

#### 자금 조달 계획 (Funding Plan)
| 연도 | 계획 내용 |
|------|------------|
| 2025 | 정부지원사업 및 시드 투자(5억 원) 확보 |
| 2026 | Series A 투자(20억 원) 유치 및 서비스 확장 준비 |
| 2027 | Series B 투자(50억 원) 유치, 매출 성장 기반 구축 |
| 2028 | 글로벌 투자 유치 및 IPO 단계 진입 |

#### 자금 소요 계획 (Spending Plan)
| 항목 | 비율 |
|------|------|
| 연구개발(R&D) | 40% |
| 인재 채용 | 25% |
| 마케팅 | 20% |
| 기타 운영비 | 15% |

---

📌 **작성 / 표기 규칙**
- 금액 단위(억 원, %, 명 등)는 텍스트 그대로 유지합니다.  
- HTML 내 줄바꿈(`<br>`, `<span>`, `<b>`, `<i>`) 등은 제거하고 순수 텍스트만 사용합니다.  
- 각 항목은 한 문장으로 정리하되, 불필요한 중복 단어는 제거합니다.  
- 연도 순서는 반드시 2025 → 2026 → 2027 → 2028 순으로 유지합니다.  
- 값이 없거나 불명확한 경우 위의 **생성 가이드라인**에 따라 의미를 유지하며 채웁니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **성장 전략의 실행 기반을 수치화한 재무 계획 페이지**입니다.  
- 왼쪽에서는 **언제, 어떤 방식으로 자금을 확보할 것인지**(조달 계획)를,  
  오른쪽에서는 **확보한 자금을 어디에, 어떤 비중으로 사용할 것인지**(소요 계획)를 명확히 제시합니다.  
- 핵심은 **“현실적 자금 확보 + 전략적 자금 배분”의 조화**이며,  
  투자자에게 “재무 구조의 실행 가능성”과 “자금 운용의 효율성”을 동시에 전달해야 합니다.  
- 자금 항목은 일반적으로 다음 네 가지 축을 중심으로 구성됩니다:  
  1️⃣ **연구개발(R&D)** – 기술 고도화, 제품 완성도 향상  
  2️⃣ **인재 채용** – 핵심 인력 확보 및 조직 강화  
  3️⃣ **마케팅** – 시장 진입, 브랜드 확산  
  4️⃣ **기타 운영비** – 플랫폼 운영, 유지보수, 관리 비용  
- 전체적으로 **연도별 조달 → 항목별 사용 → 성장 기반 확보**의 논리적 흐름이 드러나야 합니다.

"""


    elif slide_num == 17:
        return f"""{base}
[슬라이드 17: 팀 구성 (Team Composition)]
HTML:
{html[:]}
JSON 예시:
{{
  "team1Position": "",
  "team1PhotoText": "",
  "team1Name": "",
  "team1Description": "",
  "team2Position": "",
  "team2PhotoText": "",
  "team2Name": "",
  "team2Description": "",
  "team3Position": "",
  "team3PhotoText": "",
  "team3Name": "",
  "team3Description": "",
  "team4Position": "",
  "team4PhotoText": "",
  "team4Name": "",
  "team4Description": ""
}}

### 🟪 글자수조건
{{
  "team1Position": "",
  "team1PhotoText": "인물사진",
  "team1Name": "",
  "team1Description": "최대 22자",
  "team2Position": "",
  "team2PhotoText": "인물사진",
  "team2Name": "",
  "team2Description": "최대 22자",
  "team3Position": "",
  "team3PhotoText": "인물사진",
  "team3Name": "",
  "team3Description": "최대 22자",
  "team4Position": "",
  "team4PhotoText": "인물사진",
  "team4Name": "",
  "team4Description": "최대 22자"
}}


조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML 내 인물 구성 섹션(직책, 이름, 사진 텍스트, 설명문)을 기준으로 데이터를 추출하거나, 내용이 없을 경우 가이드라인에 따라 생성하세요.

---

🟩 **팀원 정보 (team1~team4)**
1) 각 팀원의 정보는 다음 네 가지 항목으로 구성됩니다:  
   - Position (직책 또는 역할명)  
   - PhotoText (사진이 없을 경우 텍스트로 대체된 설명, 예: “CEO”, “CTO”)  
   - Name (이름)  
   - Description (주요 경력 및 역할 설명)

| 항목 | 예시 |
|------|------|
| team1Position | 대표이사(CEO) |
| team1PhotoText | CEO |
| team1Name | 홍길동 |
| team1Description | 10년간 IT 스타트업 운영 경험. AI 기반 서비스 기획 및 투자 유치 주도. |

- 팀원은 최대 4명까지 포함하며, 각 항목이 존재하지 않으면 빈 문자열("")로 둡니다.  
- **팀원이 2명 이하인 경우**, 남은 팀 슬롯(team3~4)은 모두 공백("")으로 채웁니다.  
- **HTML에 이미지 대신 텍스트가 있는 경우**, 해당 텍스트를 `teamXPhotoText`에 입력합니다.  

---

🟩 **없을 경우 생성 규칙 (기본 템플릿)**

| Key | 기본값(예시) |
|-----|----------------|
| team1Position | 대표이사(CEO) |
| team1Name | 김민수 |
| team1Description | 스타트업 창업 및 경영 10년 경력. AI 및 플랫폼 서비스 전략 수립 총괄. |
| team2Position | 기술이사(CTO) |
| team2Name | 박지훈 |
| team2Description | 소프트웨어 아키텍처 및 AI 모델 개발 전문가. 서비스 기술 고도화 담당. |
| team3Position | 마케팅이사(CMO) |
| team3Name | 이수연 |
| team3Description | 디지털 마케팅 및 브랜딩 전문가. 고객 경험 기반 시장 확장 전략 수립. |
| team4Position | 운영이사(COO) |
| team4Name | 정우석 |
| team4Description | 서비스 운영 및 인프라 관리 총괄. 효율적 프로세스 구축 및 조직 관리 담당. |

> 💡 Tip: 팀 규모가 작을 경우 2~3명 구성만 유지하고 나머지는 공백으로 둡니다.  
> 팀이 기술 중심이면 CTO 비중을, 사업 중심이면 CEO/CMO 비중을 강화합니다.

---

📌 **작성 / 표기 규칙**
- 이름(Name)과 직책(Position)은 반드시 함께 구성합니다.  
- Description은 한 문장(최대 2문장 이내)으로 요약하며, 주요 성과·전문분야 중심으로 작성합니다.  
- HTML 내 줄바꿈(`<br>`, `<b>`, `<span>`, `<i>`)은 모두 제거하고 순수 텍스트만 추출합니다.  
- 중복되는 단어(“전문가”, “경험豊富”)는 피하고, 역할 중심으로 명확히 기술합니다.  
- 값이 없는 경우 위 **기본 템플릿**을 참고해 의미 있는 문장으로 채웁니다!!. (없으면 생성한다! 필수!! )

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 **핵심 인력의 전문성과 역할 분담을 강조하는 슬라이드**입니다.  
- 목표는 “이 팀이 실제로 이 사업을 성공시킬 수 있는 역량을 갖추고 있다”는 확신을 투자자에게 주는 것입니다.  
- 각 인물의 설명은 개별 능력보다는 **팀 시너지 중심(예: 기술+운영+마케팅의 균형)**으로 구성하는 것이 좋습니다.  
- 일반적인 구성 예시는 다음과 같습니다:
  1️⃣ 대표이사(CEO) — 사업 총괄 / 비전 제시 / 전략 수립  
  2️⃣ 기술이사(CTO) — 기술 개발 / 제품 고도화  
  3️⃣ 마케팅이사(CMO) — 시장 확장 / 고객 관리  
  4️⃣ 운영이사(COO) — 조직 운영 / 재무 관리  
- 전체적으로 **“역할 명확화 → 전문성 제시 → 조직 신뢰도 강화”**의 흐름을 유지해야 합니다.

"""

    elif slide_num == 18:
        return f"""{base}
[슬라이드 18: 비전 및 결론 (Vision & Conclusion)]
HTML:
{html[:]}
JSON 예시:
{{
  "visionStatement": "",
  "coreMessage": "",
  "closingRemark": ""
}}

### 🟪 [글자수조건]
{{
  "visionStatement": "최소20자 - 최대30자",
  "coreMessage": "최소25자 - 최대38자",
  "closingRemark": ""
}}


조건:
- JSON 구조와 키 이름은 절대 변경하지 마세요.
- HTML의 시각적 구성(중앙 메시지 → 비전 문장 → 하단 문구)을 기준으로 텍스트를 추출하거나, 내용이 없을 경우 아래 가이드라인에 따라 생성하세요.

---

🟩  **요소별 구성 가이드**
1️⃣ **visionStatement (중앙 핵심 메시지)**  
- 페이지의 중앙에 위치한 핵심 문구 또는 일정 안내 문장을 추출합니다.  
  예: “2025년 3월 정식 런칭 예정”, “서비스 오픈 기념 프로모션 진행 중”, “Coming Soon!”  
- 서비스 일정, 주요 이벤트, 향후 계획 등을 간결하게 표현합니다.  
- **없을 경우 생성 규칙:**  
  “2025년 하반기 정식 서비스 런칭 예정” 또는  
  “새로운 여정을 함께할 준비가 되어 있습니다.”  

---

2️⃣ **coreMessage (브랜드 비전 및 다짐 문장)**  
- 핵심 메시지 아래에 위치한 브랜드의 비전, 철학, 또는 팀의 다짐을 추출합니다.  
  예:  
  “우리는 기술을 통해 세상을 더 따뜻하게 만듭니다.”  
  “고객의 일상 속에 스며드는 서비스를 만들어갑니다.”  
  “지속 가능한 혁신으로 새로운 가치를 창출하겠습니다.”  
- **없을 경우 생성 규칙:**  
  “지속 가능한 혁신으로 더 나은 내일을 만들어갑니다.”  

---

3️⃣ **closingRemark (마무리 문구 및 연락 정보)**  
- 하단에 위치한 대표자명, 회사명, 연락처, 이메일 등의 정보를 포함합니다.  
  예:  
  “대표이사 홍길동 | (주)플랭킷 | Email: contact@plankit.kr | Tel: 02-123-4567”  
  “감사합니다. | Team ForYou4Pet | contact@foryou4pet.co.kr”  
- **없을 경우 생성 규칙:**  
  “감사합니다. | (주)플랭킷 | contact@plankit.kr”  
- 문장은 가능한 한 한 줄로 정리하고, “감사합니다.”를 포함하면 좋습니다.

---

📌 **작성 / 표기 규칙**
- 줄바꿈(`<br>`, `<b>`, `<span>` 등 HTML 태그)은 모두 제거하고 순수 텍스트만 추출합니다.  
- 각 항목은 한 문장 단위로 자연스럽게 이어지도록 구성합니다.  
- **값이 비어 있을 경우**, 위의 생성 가이드라인을 참조해 의미가 유지되도록 채웁니다.  
- 불필요한 장식문, 아이콘, 배경 문구는 제외합니다.  
- 연락처, 이메일, 회사명 등은 실제 기업 정보를 기반으로 추출하되, 명확하지 않으면 예시 형태로 생성합니다.

---

🧭 **페이지 의도 (참고용)**
- 이 페이지는 발표의 **마무리(Ending)** 역할을 수행하는 **비전 및 결론(Vision & Conclusion)** 슬라이드입니다.  
- 구성의 핵심은 세 가지입니다:  
  1️⃣ **일정 중심 메시지(visionStatement)** — 향후 계획 또는 런칭 일정  
  2️⃣ **브랜드 비전(coreMessage)** — 서비스 철학, 가치, 다짐  
  3️⃣ **마무리 및 연락 정보(closingRemark)** — 공식적 엔딩 및 정보 전달  
- 전체적으로는 청중에게 **긍정적 인상과 신뢰감**을 남기면서,  
  “우리가 어디로 가고 있는가(비전)”와 “지금 무엇을 준비하고 있는가(일정)”를 명확히 보여줘야 합니다.  
- 따라서 tone은 명확하고 희망적이며, IR Deck의 완결성을 높이는 **공식 마무리 문체**를 유지해야 합니다.

"""
    else:
        raise ValueError("슬라이드 번호는 1~18만 가능합니다.")


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

    for i in range(4, 5):  # 1~18까지
        print(f">> GPT 슬라이드 {i} 생성 중...")
        prompt = build_prompt(i, html)
        slide_data = remove_immutable_meta(call_gpt(prompt))
        save_slide_json(i, slide_data)

    print("\n🎉 모든 슬라이드 JSON 생성이 완료되었습니다!")


if __name__ == "__main__":
    main()
