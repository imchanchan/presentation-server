from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

try:
    from pymongo import MongoClient
except ImportError as exc:  # pragma: no cover - dependency guard
    raise SystemExit(
        "pymongo가 필요합니다. `pip install pymongo` 후 다시 실행하세요."
    ) from exc

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


ROOT = Path(__file__).resolve().parents[1]
TS_PATH = ROOT / "src" / "constants" / "slideTexts.constants.ts"
IMMUTABLE_KEYS = {"leftNumber", "leftTitle", "leftSubtitle", "rightTitle", "rightNumber"}


def c(path: str) -> str:
    """Shortcut to access values inside the MongoDB content field."""
    return f"content.{path}"


def load_env() -> None:
    """Load .env from project root if python-dotenv is available."""
    if load_dotenv is None:
        return

    env_file = ROOT / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


# (json_path, value_type, ts_key)
SLIDE_MAPPINGS: dict[int, List[Tuple[str, str, str]]] = {
    1: [
        (c("subtitle"), "string", "subtitle"),
        (c("mainTitle"), "string", "mainTitle"),
        (c("bottomTitle"), "string", "bottomTitle"),
    ],
    2: [
        (c("mainHeading"), "string", "mainHeading"),
        (c("description"), "string", "description"),  # 삭제
        (c("issue1Title"), "string", "issue1Title"),
        (c("issue1Description"), "string", "issue1Description"),
        (c("issue2Title"), "string", "issue2Title"),
        (c("issue2Description"), "string", "issue2Description"),
        (c("issue3Title"), "string", "issue3Title"),
        (c("issue3Description"), "string", "issue3Description"),
    ],
    3: [
        (c("mainTitle"), "string", "mainTitle"),
        (c("rows[0].division"), "string", "row1Label"),
        (c("rows[0].asIs"), "string", "row1AsIs"),
        (c("rows[0].toBe"), "string", "row1ToBe"),
        (c("rows[1].division"), "string", "row2Label"),
        (c("rows[1].asIs"), "string", "row2AsIs"),
        (c("rows[1].toBe"), "string", "row2ToBe"),
        (c("rows[2].division"), "string", "row3Label"),
        (c("rows[2].asIs"), "string", "row3AsIs"),
        (c("rows[2].toBe"), "string", "row3ToBe"),
        (c("rows[3].division"), "string", "row4Label"),
        (c("rows[3].asIs"), "string", "row4AsIs"),
        (c("rows[3].toBe"), "string", "row4ToBe"),
    ],
    4: [
        (c("leftTopTitle"), "string", "leftTopTitle"), # 고정
        (c("leftTopDescription"), "string", "leftTopDescription"),
        (c("tamLabel"), "string", "tamLabel"), # 고정
        (c("tamAmount"), "string", "tamAmount"),
        (c("tamMarketName"), "string", "tamMarketName"),
        (c("tamDescription"), "string", "tamDescription"),
        (c("samLabel"), "string", "samLabel"), # 고정
        (c("samAmount"), "string", "samAmount"),
        (c("samMarketName"), "string", "samMarketName"),
        (c("samDescription"), "string", "samDescription"), 
        (c("somLabel"), "string", "somLabel"), # 고정
        (c("somAmount"), "string", "somAmount"),
        (c("somMarketName"), "string", "somMarketName"),
        (c("somDescription"), "string", "somDescription"),
        (c("leftBottomTitle"), "string", "leftBottomTitle"), # 고정
        (c("leftBottomDescription"), "string", "leftBottomDescription"),
    ],
    5: [
        (c("personName"), "string", "personName"),
        (c("personInfoValues"), "string", "personInfoValues"), # 삭제
        (c("personInfoItems"), "object_array", "personInfoItems"), # 

        (c("lifestyleContent"), "string", "lifestyleContent"),
        (c("needsContent"), "string", "needsContent"),
        (c("problemsContent"), "string", "problemsContent"),
        (c("infoSourceContent"), "string", "infoSourceContent"),
        (c("decisionFactorsContent"), "string", "decisionFactorsContent"),
        (c("avoidanceFactorsContent"), "string", "avoidanceFactorsContent"),
    ],
    6: [
        (c("mainTitle"), "string", "mainTitle"),
        (c("cards[0].step"), "string", "card1Step"), # 고정
        (c("cards[0].icon"), "string", "card1Icon"), # 고정
        (c("cards[0].title"), "string", "card1Title"),
        (c("cards[0].description"), "string", "card1Description"),
        (c("cards[1].step"), "string", "card2Step"), # 고정
        (c("cards[1].icon"), "string", "card2Icon"), # 고정
        (c("cards[1].title"), "string", "card2Title"),
        (c("cards[1].description"), "string", "card2Description"),
        (c("cards[2].step"), "string", "card3Step"), # 고정
        (c("cards[2].icon"), "string", "card3Icon"), # 고정
        (c("cards[2].title"), "string", "card3Title"),
        (c("cards[2].description"), "string", "card3Description"),
        (c("cards[3].step"), "string", "card4Step"), # 고정
        (c("cards[3].icon"), "string", "card4Icon"), # 고정
        (c("cards[3].title"), "string", "card4Title"),
        (c("cards[3].description"), "string", "card4Description"),
    ],
    7: [
        (c("strength1Title"), "string", "strength1Title"),
        (c("strength1Description"), "string", "strength1Description"),
        (c("strength2Title"), "string", "strength2Title"),
        (c("strength2Description"), "string", "strength2Description"),
        (c("strength3Title"), "string", "strength3Title"),
        (c("strength3Description"), "string", "strength3Description"),
        (c("strength4Title"), "string", "strength4Title"),
        (c("strength4Description"), "string", "strength4Description"),
        (c("centerText"), "string", "centerText"), # 고정
    ],
    8: [
        (c("leftSectionTitle"), "string", "leftSectionTitle"), # 고정
        (c("table[0].number"), "string", "row1Number"), # 고정
        (c("table[0].content"), "string", "row1Content"),
        (c("table[0].performance"), "string", "row1Performance"),
        (c("table[0].highlightedMonths"), "array", "row1HighlightedMonths"),  # 고정
        (c("table[1].number"), "string", "row2Number"),  # 고정
        (c("table[1].content"), "string", "row2Content"),
        (c("table[1].performance"), "string", "row2Performance"),
        (c("table[1].highlightedMonths"), "array", "row2HighlightedMonths"),  # 고정
        (c("table[2].number"), "string", "row3Number"),  # 고정
        (c("table[2].content"), "string", "row3Content"),
        (c("table[2].performance"), "string", "row3Performance"),
        (c("table[2].highlightedMonths"), "array", "row3HighlightedMonths"),  # 고정
        (c("table[3].number"), "string", "row4Number"),  # 고정
        (c("table[3].content"), "string", "row4Content"),
        (c("table[3].performance"), "string", "row4Performance"),
        (c("table[3].highlightedMonths"), "array", "row4HighlightedMonths"),  # 고정
        (c("table[4].number"), "string", "row5Number"),  # 고정
        (c("table[4].content"), "string", "row5Content"),
        (c("table[4].performance"), "string", "row5Performance"),
        (c("table[4].highlightedMonths"), "array", "row5HighlightedMonths"),  # 고정
        (c("table[5].number"), "string", "row6Number"),  # 고정
        (c("table[5].content"), "string", "row6Content"),
        (c("table[5].performance"), "string", "row6Performance"),
        (c("table[5].highlightedMonths"), "array", "row6HighlightedMonths"),  # 고정
        (c("rightSectionTitle"), "string", "rightSectionTitle"),  # 고정
        (c("ipr.title"), "string", "iprTitle"),  # 고정
        (c("ipr.icon"), "string", "iprIcon"), # 고정
        (c("ipr.items"), "object_array", "iprItems"),
        (c("certification.title"), "string", "certificationTitle"),  # 고정
        (c("certification.icon"), "string", "certificationIcon"),  # 고정
        (c("certification.items"), "object_array", "certificationItems"),
    ],
    9: [
        (c("journeyMapTitle"), "string", "journeyMapTitle"), # 고정
        (c("validationStatusTitle"), "string", "validationStatusTitle"), # 고정
        (c("journeyMap[0].step"), "string", "step1Title"), # 고정
        (c("journeyMap[0].description"), "string", "step1Description"),
        (c("journeyMap[1].step"), "string", "step2Title"), # 고정
        (c("journeyMap[1].description"), "string", "step2Description"),
        (c("journeyMap[2].step"), "string", "step3Title"), # 고정
        (c("journeyMap[2].description"), "string", "step3Description"),
        (c("journeyMap[3].step"), "string", "step4Title"), # 고정
        (c("journeyMap[3].description"), "string", "step4Description"),
        (c("journeyMap[4].step"), "string", "step5Title"), # 고정
        (c("journeyMap[4].description"), "string", "step5Description"),
        (c("journeyMap[5].step"), "string", "step6Title"), # 고정
        (c("journeyMap[5].description"), "string", "step6Description"),
        (c("validationTable[0].division"), "string", "row1Division"),
        (c("validationTable[0].content"), "string", "row1Content"),
        (c("validationTable[0].period"), "string", "row1Period"),
        (c("validationTable[1].division"), "string", "row2Division"),
        (c("validationTable[1].content"), "string", "row2Content"),
        (c("validationTable[1].period"), "string", "row2Period"),
        (c("metrics[0].number"), "string", "circle1Number"),
        (c("metrics[0].label"), "string", "circle1Label"), # 고정
        (c("metrics[1].number"), "string", "circle2Number"),
        (c("metrics[1].label"), "string", "circle2Label"), # 고정
        (c("metrics[2].number"), "string", "circle3Number"),
        (c("metrics[2].label"), "string", "circle3Label"), # 고정
    ],
    10: [
        (c("mainHeading"), "string", "mainHeading"),
        (c("headerDivision"), "string", "headerDivision"), # 고정
        (c("headerCompetitor1"), "string", "headerCompetitor1"),
        (c("headerCompetitor2"), "string", "headerCompetitor2"),
        (c("headerCompetitor3"), "string", "headerCompetitor3"),
        (c("headerOurCompany"), "string", "headerOurCompany"),
        (c("row1Division"), "string", "row1Division"), # 고정
        (c("row1Competitor1"), "string", "row1Competitor1"),
        (c("row1Competitor2"), "string", "row1Competitor2"),
        (c("row1Competitor3"), "string", "row1Competitor3"),
        (c("row1OurCompany"), "string", "row1OurCompany"),
        (c("row2Division"), "string", "row2Division"), # 고정
        (c("row2Competitor1"), "string", "row2Competitor1"),
        (c("row2Competitor2"), "string", "row2Competitor2"),
        (c("row2Competitor3"), "string", "row2Competitor3"),
        (c("row2OurCompany"), "string", "row2OurCompany"),
        (c("row3Division"), "string", "row3Division"), # 고정
        (c("row3Competitor1"), "string", "row3Competitor1"),
        (c("row3Competitor2"), "string", "row3Competitor2"),
        (c("row3Competitor3"), "string", "row3Competitor3"),
        (c("row3OurCompany"), "string", "row3OurCompany"),
        (c("row4Division"), "string", "row4Division"), # 고정
        (c("row4Competitor1"), "string", "row4Competitor1"),
        (c("row4Competitor2"), "string", "row4Competitor2"),
        (c("row4Competitor3"), "string", "row4Competitor3"),
        (c("row4OurCompany"), "string", "row4OurCompany"),
    ],
    11: [
        (c("nodes"), "object_array", "nodes"),
        (c("customerToCompanyTop"), "string", "customerToCompanyTop"),
        (c("customerToCompanyBottom"), "string", "customerToCompanyBottom"),
        (c("companyToRestaurantLeft"), "string", "companyTopartner1Left"),
        (c("companyToRestaurantRight"), "string", "companyTopartner1Right"),
        (c("companyToRiderTop"), "string", "companyTopartner2Top"), # 변수 변경 반영하기
        (c("companyToRiderBottom"), "string", "companyTopartner2Bottom"), # 변수 변경 반영하기
    ],
    12: [
        (c("salesPlanTitle"), "string", "salesPlanTitle"), # 고정
        (c("salesBasisTitle"), "string", "salesBasisTitle"), # 고정
        (c("yAxisUnit"), "string", "yAxisUnit"), # 고정
        (c("deliveryFeeTitle"), "string", "deliveryFeeTitle"),
        (c("deliveryFeeList"), "string", "deliveryFeeList"),
        (c("adCostTitle"), "string", "adCostTitle"),
        (c("adCostList"), "string", "adCostList"),
        (c("yAxisLabel150"), "string", "yAxisLabel150"),
        (c("yAxisLabel100"), "string", "yAxisLabel100"),
        (c("yAxisLabel50"), "string", "yAxisLabel50"),
        (c("yAxisLabel0"), "string", "yAxisLabel0"), # 고정 = 0 
        (c("xAxisLabel2025"), "string", "xAxisLabel2025"),  # 고정
        (c("xAxisLabel2026"), "string", "xAxisLabel2026"),  # 고정
        (c("xAxisLabel2027"), "string", "xAxisLabel2027"), # 고정
        (c("xAxisLabel2028"), "string", "xAxisLabel2028"), # 고정
        (c("chartCategories"), "object_array", "chartCategories"),
        (c("chartData"), "object_array", "chartData"),
    ],
    13: [
        (c("mainTitle"), "string", "mainTitle"),
        (c("subTitle"), "string", "subTitle"),
        (c("strategyCards"), "object_array", "strategyCards"),
    ],
    14: [
        (c("tableHeaderDivision"), "string", "tableHeaderDivision"), # 고정 
        (c("tableHeaderYear1"), "string", "tableHeaderYear1"),
        (c("tableHeaderYear2"), "string", "tableHeaderYear2"),
        (c("tableHeaderYear3"), "string", "tableHeaderYear3"),
        (c("tableHeaderYear4"), "string", "tableHeaderYear4"),
        (c("row1Division"), "string", "row1Division"), # 고정
        (c("row1Year1"), "string", "row1Year1"),
        (c("row1Year2"), "string", "row1Year2"),
        (c("row1Year3"), "string", "row1Year3"),
        (c("row1Year4"), "string", "row1Year4"),
        (c("row2Division"), "string", "row2Division"), # 고정
        (c("row2Year1"), "string", "row2Year1"),
        (c("row2Year2"), "string", "row2Year2"),
        (c("row2Year3"), "string", "row2Year3"),
        (c("row2Year4"), "string", "row2Year4"),
        (c("row3Division"), "string", "row3Division"), # 고정
        (c("row3Year1"), "string", "row3Year1"),
        (c("row3Year2"), "string", "row3Year2"),
        (c("row3Year3"), "string", "row3Year3"),
        (c("row3Year4"), "string", "row3Year4"),
        (c("row4Division"), "string", "row4Division"), # 고정
        (c("row4Year1"), "string", "row4Year1"),
        (c("row4Year2"), "string", "row4Year2"),
        (c("row4Year3"), "string", "row4Year3"),
        (c("row4Year4"), "string", "row4Year4"),
        (c("row5Division"), "string", "row5Division"), # 고정
        (c("row5Year1"), "string", "row5Year1"),
        (c("row5Year2"), "string", "row5Year2"),
        (c("row5Year3"), "string", "row5Year3"),
        (c("row5Year4"), "string", "row5Year4"),
        (c("row6Division"), "string", "row6Division"), # 고정
        (c("row6Year1"), "string", "row6Year1"),
        (c("row6Year2"), "string", "row6Year2"),
        (c("row6Year3"), "string", "row6Year3"),
        (c("row6Year4"), "string", "row6Year4"),
        (c("row7Division"), "string", "row7Division"), # 고정
        (c("row7Year1"), "string", "row7Year1"),
        (c("row7Year2"), "string", "row7Year2"),
        (c("row7Year3"), "string", "row7Year3"),
        (c("row7Year4"), "string", "row7Year4"),
    ],
    15: [
        (c("mainTitle"), "string", "mainTitle"), 
        (c("phase1Title"), "string", "phase1Title"), # 고정 
        (c("phase1YearGoal"), "string", "phase1YearGoal"),
        (c("phase1ObjectiveTitle"), "string", "phase1ObjectiveTitle"),
        (c("phase1Strategy"), "string", "phase1Strategy"),
        (c("phase2Title"), "string", "phase2Title"), # 고정
        (c("phase2YearGoal"), "string", "phase2YearGoal"),
        (c("phase2ObjectiveTitle"), "string", "phase2ObjectiveTitle"),
        (c("phase2Strategy"), "string", "phase2Strategy"),
        (c("phase3Title"), "string", "phase3Title"), # 고정
        (c("phase3YearGoal"), "string", "phase3YearGoal"),
        (c("phase3ObjectiveTitle"), "string", "phase3ObjectiveTitle"),
        (c("phase3Strategy"), "string", "phase3Strategy"),
        (c("phase4Title"), "string", "phase4Title"), # 고정
        (c("phase4YearGoal"), "string", "phase4YearGoal"),
        (c("phase4ObjectiveTitle"), "string", "phase4ObjectiveTitle"),
        (c("phase4Strategy"), "string", "phase4Strategy"),
    ],
    16: [
        (c("fundingPlanTitle"), "string", "fundingPlanTitle"), # 고정
        (c("spendingPlanTitle"), "string", "spendingPlanTitle"), # 고정
        (c("fundingPlan1Year"), "string", "fundingPlan1Year"),
        (c("fundingPlan1Content"), "string", "fundingPlan1Content"),
        (c("fundingPlan2Year"), "string", "fundingPlan2Year"),
        (c("fundingPlan2Content"), "string", "fundingPlan2Content"),
        (c("fundingPlan3Year"), "string", "fundingPlan3Year"),
        (c("fundingPlan3Content"), "string", "fundingPlan3Content"),
        (c("fundingPlan4Year"), "string", "fundingPlan4Year"),
        (c("fundingPlan4Content"), "string", "fundingPlan4Content"),
        (c("chartCategories"), "object_array", "chartCategories"), # 고정
    ],
    17: [
        (c("team1Position"), "string", "team1Position"),
        (c("team1PhotoText"), "string", "team1PhotoText"), # 고정
        (c("team1Name"), "string", "team1Name"),
        (c("team1Description"), "string", "team1Description"),
        (c("team2Position"), "string", "team2Position"),
        (c("team2PhotoText"), "string", "team2PhotoText"), # 고정
        (c("team2Name"), "string", "team2Name"),
        (c("team2Description"), "string", "team2Description"),
        (c("team3Position"), "string", "team3Position"),
        (c("team3PhotoText"), "string", "team3PhotoText"), # 고정
        (c("team3Name"), "string", "team3Name"),
        (c("team3Description"), "string", "team3Description"),
        (c("team4Position"), "string", "team4Position"),
        (c("team4PhotoText"), "string", "team4PhotoText"), # 고정
        (c("team4Name"), "string", "team4Name"),
        (c("team4Description"), "string", "team4Description"),
    ],
    18: [
        (c("visionStatement"), "string", "visionStatement"),
        (c("coreMessage"), "string", "coreMessage"),
        (c("closingRemark"), "string", "closingRemark"),
    ],
}


load_env()

DEFAULT_MONGO_URI = os.getenv(
    "MONGO_URI",
    "mongodb://root:0422@127.0.0.1:27017/presentationDB?authSource=admin",
)
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME") or os.getenv("MONGO_DB") or "presentation_db"
MONGO_COLLECTION_NAME = os.getenv("MONGO_COLLECTION", "slides")

_mongo_client: Optional[MongoClient] = None


def get_mongo_collection():
    global _mongo_client

    if _mongo_client is None:
        _mongo_client = MongoClient(DEFAULT_MONGO_URI, serverSelectionTimeoutMS=5000)

    return _mongo_client[MONGO_DB_NAME][MONGO_COLLECTION_NAME]


def load_slide_document(slide_num: int) -> Dict[str, Any]:
    collection = get_mongo_collection()
    document = collection.find_one({"_id": slide_num})

    if document is None:
        raise ValueError(
            f"슬라이드 {slide_num}에 해당하는 MongoDB 문서를 찾을 수 없습니다. (_id={slide_num})"
        )

    # MongoDB 메타 필드는 제거
    document.pop("_id", None)
    document.pop("__v", None)

    # find_one이 반환한 객체는 Mutability 보장을 위해 dict로 변환
    return dict(document)


def extract_value(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for part in _split_path(path):
        if isinstance(part, tuple):
            key, index = part
            current = current.get(key, []) if isinstance(current, dict) else []
            if not isinstance(current, list):
                return None
            try:
                current = current[index]
            except IndexError:
                return None
        else:
            if not isinstance(current, dict):
                return None
            current = current.get(part)
        if current is None:
            return None
    return current


def _split_path(path: str) -> Iterable[Any]:
    token_pattern = re.compile(r"([^.\[]+)(?:\[(\d+)])?")
    for match in token_pattern.finditer(path):
        key, index = match.groups()
        if index is None:
            yield key
        else:
            yield (key, int(index))


def format_ts_string(value: Any, quote: str = "'") -> str:
    if value is None:
        value = ""
    text = str(value)
    text = text.replace("\\", "\\\\")
    if quote == "'":
        text = text.replace("'", "\\'")
    elif quote == '"':
        text = text.replace('"', '\\"')
    elif quote == "`":
        text = text.replace("`", "\\`")
    else:
        text = text.replace("'", "\\'")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\n", "\\n")
    return text


def format_ts_array(value: Any) -> str:
    if not value:
        return "[]"
    if isinstance(value, list):
        if all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value):
            return "[" + ", ".join(str(item) for item in value) + "]"
        return "[" + ", ".join(f"'{format_ts_string(item)}'" for item in value) + "]"
    # 기본적으로 문자열로 처리
    return "[]"


def format_ts_object_value(value: Any) -> str:
    if value is None:
        return "''"
    if isinstance(value, str):
        return f"'{format_ts_string(value)}'"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, list):
        return format_ts_array(value)
    if isinstance(value, dict):
        # 중첩 객체는 문자열로 직렬화
        return f"'{format_ts_string(json.dumps(value, ensure_ascii=False))}'"
    return f"'{format_ts_string(str(value))}'"


def format_ts_object_array(value: Any, base_indent: str) -> str:
    if not isinstance(value, list) or not value:
        return "[]"

    item_indent = base_indent + "  "
    value_indent = item_indent + "  "
    lines: list[str] = ["["]

    for item in value:
        if not isinstance(item, dict):
            continue
        lines.append(f"{item_indent}{{")
        for key, raw_value in item.items():
            lines.append(f"{value_indent}{key}: {format_ts_object_value(raw_value)},")
        lines.append(f"{item_indent}}},")

    lines.append(f"{base_indent}]")
    return "\n".join(lines)


def _leading_whitespace(text: str) -> str:
    if "\n" in text:
        text = text.split("\n")[-1]
    stripped = text.lstrip(" \t")
    return text[: len(text) - len(stripped)]


def update_ts_block(block: str, key: str, value: Any, value_type: str) -> str:
    if value_type in {"array", "object_array"}:
        pattern = re.compile(
            rf"(?P<prefix>\s+{re.escape(key)}\s*:\s*)\[[^\]]*\](?P<post>\s*(?:as\s+const)?)?(?P<suffix>,?)",
            re.DOTALL,
        )

        def _replace_array(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            suffix = match.group("suffix")
            post = match.group("post") or ""
            indent = _leading_whitespace(prefix)
            if value_type == "array":
                formatted_value = format_ts_array(value)
            else:
                formatted_value = format_ts_object_array(value, indent)
            return f"{prefix}{formatted_value}{post}{suffix}"

        new_block, count = pattern.subn(_replace_array, block, count=1)
        if count:
            return new_block
        raise ValueError(f"{key} 배열 필드를 업데이트하지 못했습니다.")

    pattern = re.compile(
        rf"(?P<prefix>\s+{re.escape(key)}\s*:\s*)(?P<quote>['\"`])(?:\\.|(?:(?!(?P=quote)).))*?(?P=quote)(?P<suffix>,?)",
        re.DOTALL,
    )

    def _replace(match: re.Match[str]) -> str:
        quote = match.group("quote")
        formatted = format_ts_string(value, quote)
        return f"{match.group('prefix')}{quote}{formatted}{quote}{match.group('suffix')}"

    new_block, count = pattern.subn(_replace, block, count=1)
    if count:
        return new_block
    raise ValueError(f"{key} 문자열 필드를 업데이트하지 못했습니다.")


def apply_slide(ts_text: str, slide_num: int, mapping: List[Tuple[str, str, str]]) -> str:
    pattern = re.compile(
        rf"(export\s+const\s+SLIDE{slide_num}_TEXTS\s*=\s*\{{[\s\S]*?\}}\s*as\s+const;)",
        re.MULTILINE,
    )
    match = pattern.search(ts_text)
    if not match:
        raise ValueError(f"Slide {slide_num} 블록을 찾을 수 없습니다.")

    block = match.group(1)
    data = load_slide_document(slide_num)

    updated_block = block
    for json_path, value_type, ts_key in mapping:
        if ts_key in IMMUTABLE_KEYS:
            continue
        value = extract_value(data, json_path)
        updated_block = update_ts_block(updated_block, ts_key, value, value_type)

    return ts_text[: match.start()] + updated_block + ts_text[match.end():]


def main() -> None:
    global _mongo_client

    original_text = TS_PATH.read_text(encoding="utf-8")
    updated_text = original_text

    try:
        for slide_num, mapping in SLIDE_MAPPINGS.items():
            updated_text = apply_slide(updated_text, slide_num, mapping)
            print(f"✅ Slide {slide_num} 반영 완료")

        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup_path = TS_PATH.with_name(f"slideTexts.constants.backup-{timestamp}.ts")
        try:
            backup_path.write_text(original_text, encoding="utf-8")
            print(f"백업 저장: {backup_path}")
        except PermissionError as exc:
            print(f"⚠️ 백업 파일 저장 실패: {exc}")

        TS_PATH.write_text(updated_text, encoding="utf-8")
        print("slideTexts.constants.ts 업데이트 완료")
    finally:
        if _mongo_client is not None:
            _mongo_client.close()


if __name__ == "__main__":
    main()
