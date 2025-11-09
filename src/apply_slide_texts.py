from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, List, Tuple


ROOT = Path(__file__).resolve().parents[1]
SLIDES_DIR = ROOT / "slides"
TS_PATH = ROOT / "src" / "constants" / "slideTexts.constants.ts"
IMMUTABLE_KEYS = {"leftNumber", "leftTitle", "leftSubtitle", "rightTitle", "rightNumber"}


# (json_path, value_type, ts_key)
SLIDE_MAPPINGS: dict[int, List[Tuple[str, str, str]]] = {
    1: [
        ("subtitle", "string", "subtitle"),
        ("mainTitle", "string", "mainTitle"),
        ("bottomTitle", "string", "bottomTitle"),
    ],
    2: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("mainHeading", "string", "mainHeading"),
        ("description", "string", "description"),
        ("issue1Title", "string", "issue1Title"),
        ("issue1Description", "string", "issue1Description"),
        ("issue2Title", "string", "issue2Title"),
        ("issue2Description", "string", "issue2Description"),
        ("issue3Title", "string", "issue3Title"),
        ("issue3Description", "string", "issue3Description"),
    ],
    3: [
        ("mainTitle", "string", "mainTitle"),
        ("rows[0].division", "string", "row1Label"),
        ("rows[0].asIs", "string", "row1AsIs"),
        ("rows[0].toBe", "string", "row1ToBe"),
        ("rows[1].division", "string", "row2Label"),
        ("rows[1].asIs", "string", "row2AsIs"),
        ("rows[1].toBe", "string", "row2ToBe"),
        ("rows[2].division", "string", "row3Label"),
        ("rows[2].asIs", "string", "row3AsIs"),
        ("rows[2].toBe", "string", "row3ToBe"),
        ("rows[3].division", "string", "row4Label"),
        ("rows[3].asIs", "string", "row4AsIs"),
        ("rows[3].toBe", "string", "row4ToBe"),
    ],
    4: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("leftTopTitle", "string", "leftTopTitle"),
        ("leftTopDescription", "string", "leftTopDescription"),
        ("tamLabel", "string", "tamLabel"),
        ("tamAmount", "string", "tamAmount"),
        ("tamMarketName", "string", "tamMarketName"),
        ("tamDescription", "string", "tamDescription"),
        ("samLabel", "string", "samLabel"),
        ("samAmount", "string", "samAmount"),
        ("samMarketName", "string", "samMarketName"),
        ("samDescription", "string", "samDescription"),
        ("somLabel", "string", "somLabel"),
        ("somAmount", "string", "somAmount"),
        ("somMarketName", "string", "somMarketName"),
        ("somDescription", "string", "somDescription"),
        ("leftBottomTitle", "string", "leftBottomTitle"),
        ("leftBottomDescription", "string", "leftBottomDescription"),
    ],
    5: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("personName", "string", "personName"),
        ("personInfoValues", "string", "personInfoValues"),
        ("lifestyleContent", "string", "lifestyleContent"),
        ("needsContent", "string", "needsContent"),
        ("problemsContent", "string", "problemsContent"),
        ("infoSourceContent", "string", "infoSourceContent"),
        ("decisionFactorsContent", "string", "decisionFactorsContent"),
        ("avoidanceFactorsContent", "string", "avoidanceFactorsContent"),
    ],
    6: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("mainTitle", "string", "mainTitle"),
        ("cards[0].step", "string", "card1Step"),
        ("cards[0].icon", "string", "card1Icon"),
        ("cards[0].title", "string", "card1Title"),
        ("cards[0].description", "string", "card1Description"),
        ("cards[1].step", "string", "card2Step"),
        ("cards[1].icon", "string", "card2Icon"),
        ("cards[1].title", "string", "card2Title"),
        ("cards[1].description", "string", "card2Description"),
        ("cards[2].step", "string", "card3Step"),
        ("cards[2].icon", "string", "card3Icon"),
        ("cards[2].title", "string", "card3Title"),
        ("cards[2].description", "string", "card3Description"),
        ("cards[3].step", "string", "card4Step"),
        ("cards[3].icon", "string", "card4Icon"),
        ("cards[3].title", "string", "card4Title"),
        ("cards[3].description", "string", "card4Description"),
    ],
    7: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("strength1Title", "string", "strength1Title"),
        ("strength1Description", "string", "strength1Description"),
        ("strength2Title", "string", "strength2Title"),
        ("strength2Description", "string", "strength2Description"),
        ("strength3Title", "string", "strength3Title"),
        ("strength3Description", "string", "strength3Description"),
        ("strength4Title", "string", "strength4Title"),
        ("strength4Description", "string", "strength4Description"),
        ("centerText", "string", "centerText"),
    ],
    8: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("leftSectionTitle", "string", "leftSectionTitle"),
        ("table[0].number", "string", "row1Number"),
        ("table[0].content", "string", "row1Content"),
        ("table[0].performance", "string", "row1Performance"),
        ("table[0].highlightedMonths", "array", "row1HighlightedMonths"),
        ("table[1].number", "string", "row2Number"),
        ("table[1].content", "string", "row2Content"),
        ("table[1].performance", "string", "row2Performance"),
        ("table[1].highlightedMonths", "array", "row2HighlightedMonths"),
        ("table[2].number", "string", "row3Number"),
        ("table[2].content", "string", "row3Content"),
        ("table[2].performance", "string", "row3Performance"),
        ("table[2].highlightedMonths", "array", "row3HighlightedMonths"),
        ("table[3].number", "string", "row4Number"),
        ("table[3].content", "string", "row4Content"),
        ("table[3].performance", "string", "row4Performance"),
        ("table[3].highlightedMonths", "array", "row4HighlightedMonths"),
        ("table[4].number", "string", "row5Number"),
        ("table[4].content", "string", "row5Content"),
        ("table[4].performance", "string", "row5Performance"),
        ("table[4].highlightedMonths", "array", "row5HighlightedMonths"),
        ("table[5].number", "string", "row6Number"),
        ("table[5].content", "string", "row6Content"),
        ("table[5].performance", "string", "row6Performance"),
        ("table[5].highlightedMonths", "array", "row6HighlightedMonths"),
        ("rightSectionTitle", "string", "rightSectionTitle"),
        ("ipr.title", "string", "iprTitle"),
        ("ipr.list", "string", "iprList"),
        ("ipr.dates", "string", "iprDates"),
        ("ipr.icon", "string", "iprIcon"),
        ("certification.title", "string", "certificationTitle"),
        ("certification.list", "string", "certificationList"),
        ("certification.dates", "string", "certificationDates"),
        ("certification.icon", "string", "certificationIcon"),
    ],
    9: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("journeyMapTitle", "string", "journeyMapTitle"),
        ("validationStatusTitle", "string", "validationStatusTitle"),
        ("journeyMap[0].step", "string", "step1Title"),
        ("journeyMap[0].description", "string", "step1Description"),
        ("journeyMap[1].step", "string", "step2Title"),
        ("journeyMap[1].description", "string", "step2Description"),
        ("journeyMap[2].step", "string", "step3Title"),
        ("journeyMap[2].description", "string", "step3Description"),
        ("journeyMap[3].step", "string", "step4Title"),
        ("journeyMap[3].description", "string", "step4Description"),
        ("journeyMap[4].step", "string", "step5Title"),
        ("journeyMap[4].description", "string", "step5Description"),
        ("journeyMap[5].step", "string", "step6Title"),
        ("journeyMap[5].description", "string", "step6Description"),
        ("validationTable[0].division", "string", "row1Division"),
        ("validationTable[0].content", "string", "row1Content"),
        ("validationTable[0].period", "string", "row1Period"),
        ("validationTable[1].division", "string", "row2Division"),
        ("validationTable[1].content", "string", "row2Content"),
        ("validationTable[1].period", "string", "row2Period"),
        ("metrics[0].number", "string", "circle1Number"),
        ("metrics[0].label", "string", "circle1Label"),
        ("metrics[1].number", "string", "circle2Number"),
        ("metrics[1].label", "string", "circle2Label"),
        ("metrics[2].number", "string", "circle3Number"),
        ("metrics[2].label", "string", "circle3Label"),
    ],
    10: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("mainHeading", "string", "mainHeading"),
        ("headerDivision", "string", "headerDivision"),
        ("headerCompetitor1", "string", "headerCompetitor1"),
        ("headerCompetitor2", "string", "headerCompetitor2"),
        ("headerCompetitor3", "string", "headerCompetitor3"),
        ("headerOurCompany", "string", "headerOurCompany"),
        ("row1Division", "string", "row1Division"),
        ("row1Competitor1", "string", "row1Competitor1"),
        ("row1Competitor2", "string", "row1Competitor2"),
        ("row1Competitor3", "string", "row1Competitor3"),
        ("row1OurCompany", "string", "row1OurCompany"),
        ("row2Division", "string", "row2Division"),
        ("row2Competitor1", "string", "row2Competitor1"),
        ("row2Competitor2", "string", "row2Competitor2"),
        ("row2Competitor3", "string", "row2Competitor3"),
        ("row2OurCompany", "string", "row2OurCompany"),
        ("row3Division", "string", "row3Division"),
        ("row3Competitor1", "string", "row3Competitor1"),
        ("row3Competitor2", "string", "row3Competitor2"),
        ("row3Competitor3", "string", "row3Competitor3"),
        ("row3OurCompany", "string", "row3OurCompany"),
        ("row4Division", "string", "row4Division"),
        ("row4Competitor1", "string", "row4Competitor1"),
        ("row4Competitor2", "string", "row4Competitor2"),
        ("row4Competitor3", "string", "row4Competitor3"),
        ("row4OurCompany", "string", "row4OurCompany"),
    ],
    11: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("nodes", "object_array", "nodes"),
        ("customerToCompanyTop", "string", "customerToCompanyTop"),
        ("customerToCompanyBottom", "string", "customerToCompanyBottom"),
        ("companyToRestaurantLeft", "string", "companyToRestaurantLeft"),
        ("companyToRestaurantRight", "string", "companyToRestaurantRight"),
        ("companyToRiderTop", "string", "companyToRiderTop"),
        ("companyToRiderBottom", "string", "companyToRiderBottom"),
    ],
    12: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("salesPlanTitle", "string", "salesPlanTitle"),
        ("salesBasisTitle", "string", "salesBasisTitle"),
        ("yAxisUnit", "string", "yAxisUnit"),
        ("deliveryFeeTitle", "string", "deliveryFeeTitle"),
        ("deliveryFeeList", "string", "deliveryFeeList"),
        ("adCostTitle", "string", "adCostTitle"),
        ("adCostList", "string", "adCostList"),
        ("yAxisLabel150", "string", "yAxisLabel150"),
        ("yAxisLabel100", "string", "yAxisLabel100"),
        ("yAxisLabel50", "string", "yAxisLabel50"),
        ("yAxisLabel0", "string", "yAxisLabel0"),
        ("xAxisLabel2025", "string", "xAxisLabel2025"),
        ("xAxisLabel2026", "string", "xAxisLabel2026"),
        ("xAxisLabel2027", "string", "xAxisLabel2027"),
        ("xAxisLabel2028", "string", "xAxisLabel2028"),
        ("chartCategories", "object_array", "chartCategories"),
        ("chartData", "object_array", "chartData"),
    ],
    13: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("mainTitle", "string", "mainTitle"),
        ("subTitle", "string", "subTitle"),
        ("strategyCards", "object_array", "strategyCards"),
    ],
    14: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("tableHeaderDivision", "string", "tableHeaderDivision"),
        ("tableHeaderYear1", "string", "tableHeaderYear1"),
        ("tableHeaderYear2", "string", "tableHeaderYear2"),
        ("tableHeaderYear3", "string", "tableHeaderYear3"),
        ("tableHeaderYear4", "string", "tableHeaderYear4"),
        ("row1Division", "string", "row1Division"),
        ("row1Year1", "string", "row1Year1"),
        ("row1Year2", "string", "row1Year2"),
        ("row1Year3", "string", "row1Year3"),
        ("row1Year4", "string", "row1Year4"),
        ("row2Division", "string", "row2Division"),
        ("row2Year1", "string", "row2Year1"),
        ("row2Year2", "string", "row2Year2"),
        ("row2Year3", "string", "row2Year3"),
        ("row2Year4", "string", "row2Year4"),
        ("row3Division", "string", "row3Division"),
        ("row3Year1", "string", "row3Year1"),
        ("row3Year2", "string", "row3Year2"),
        ("row3Year3", "string", "row3Year3"),
        ("row3Year4", "string", "row3Year4"),
        ("row4Division", "string", "row4Division"),
        ("row4Year1", "string", "row4Year1"),
        ("row4Year2", "string", "row4Year2"),
        ("row4Year3", "string", "row4Year3"),
        ("row4Year4", "string", "row4Year4"),
        ("row5Division", "string", "row5Division"),
        ("row5Year1", "string", "row5Year1"),
        ("row5Year2", "string", "row5Year2"),
        ("row5Year3", "string", "row5Year3"),
        ("row5Year4", "string", "row5Year4"),
        ("row6Division", "string", "row6Division"),
        ("row6Year1", "string", "row6Year1"),
        ("row6Year2", "string", "row6Year2"),
        ("row6Year3", "string", "row6Year3"),
        ("row6Year4", "string", "row6Year4"),
        ("row7Division", "string", "row7Division"),
        ("row7Year1", "string", "row7Year1"),
        ("row7Year2", "string", "row7Year2"),
        ("row7Year3", "string", "row7Year3"),
        ("row7Year4", "string", "row7Year4"),
    ],
    15: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("mainTitle", "string", "mainTitle"),
        ("phase1Title", "string", "phase1Title"),
        ("phase1YearGoal", "string", "phase1YearGoal"),
        ("phase1ObjectiveTitle", "string", "phase1ObjectiveTitle"),
        ("phase1Strategy", "string", "phase1Strategy"),
        ("phase2Title", "string", "phase2Title"),
        ("phase2YearGoal", "string", "phase2YearGoal"),
        ("phase2ObjectiveTitle", "string", "phase2ObjectiveTitle"),
        ("phase2Strategy", "string", "phase2Strategy"),
        ("phase3Title", "string", "phase3Title"),
        ("phase3YearGoal", "string", "phase3YearGoal"),
        ("phase3ObjectiveTitle", "string", "phase3ObjectiveTitle"),
        ("phase3Strategy", "string", "phase3Strategy"),
        ("phase4Title", "string", "phase4Title"),
        ("phase4YearGoal", "string", "phase4YearGoal"),
        ("phase4ObjectiveTitle", "string", "phase4ObjectiveTitle"),
        ("phase4Strategy", "string", "phase4Strategy"),
    ],
    16: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("fundingPlanTitle", "string", "fundingPlanTitle"),
        ("spendingPlanTitle", "string", "spendingPlanTitle"),
        ("fundingPlan1Year", "string", "fundingPlan1Year"),
        ("fundingPlan1Content", "string", "fundingPlan1Content"),
        ("fundingPlan2Year", "string", "fundingPlan2Year"),
        ("fundingPlan2Content", "string", "fundingPlan2Content"),
        ("fundingPlan3Year", "string", "fundingPlan3Year"),
        ("fundingPlan3Content", "string", "fundingPlan3Content"),
        ("fundingPlan4Year", "string", "fundingPlan4Year"),
        ("fundingPlan4Content", "string", "fundingPlan4Content"),
        ("chartCategories", "object_array", "chartCategories"),
    ],
    17: [
        ("leftNumber", "string", "leftNumber"),
        ("leftTitle", "string", "leftTitle"),
        ("leftSubtitle", "string", "leftSubtitle"),
        ("rightTitle", "string", "rightTitle"),
        ("rightNumber", "string", "rightNumber"),
        ("team1Position", "string", "team1Position"),
        ("team1PhotoText", "string", "team1PhotoText"),
        ("team1Name", "string", "team1Name"),
        ("team1Description", "string", "team1Description"),
        ("team2Position", "string", "team2Position"),
        ("team2PhotoText", "string", "team2PhotoText"),
        ("team2Name", "string", "team2Name"),
        ("team2Description", "string", "team2Description"),
        ("team3Position", "string", "team3Position"),
        ("team3PhotoText", "string", "team3PhotoText"),
        ("team3Name", "string", "team3Name"),
        ("team3Description", "string", "team3Description"),
        ("team4Position", "string", "team4Position"),
        ("team4PhotoText", "string", "team4PhotoText"),
        ("team4Name", "string", "team4Name"),
        ("team4Description", "string", "team4Description"),
    ],
    18: [
        ("visionStatement", "string", "visionStatement"),
        ("coreMessage", "string", "coreMessage"),
        ("closingRemark", "string", "closingRemark"),
    ],
}


def load_latest_slide_json(slide_num: int) -> dict[str, Any]:
    if not SLIDES_DIR.exists():
        raise FileNotFoundError(f"슬라이드 디렉터리가 없습니다: {SLIDES_DIR}")

    candidates = sorted(SLIDES_DIR.glob(f"slide{slide_num}_*.json"))
    if not candidates:
        raise FileNotFoundError(f"slide{slide_num} JSON 파일을 찾을 수 없습니다 (예: slide{slide_num}_YYYYMMDD-HHMMSS.json)")

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    with latest.open(encoding="utf-8") as f:
        return json.load(f)


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
        pattern = re.compile(rf"(?P<prefix>\s+{re.escape(key)}\s*:\s*)\[[^\]]*\](?P<suffix>,?)", re.DOTALL)

        def _replace_array(match: re.Match[str]) -> str:
            prefix = match.group("prefix")
            suffix = match.group("suffix")
            indent = _leading_whitespace(prefix)
            if value_type == "array":
                formatted_value = format_ts_array(value)
            else:
                formatted_value = format_ts_object_array(value, indent)
            return f"{prefix}{formatted_value}{suffix}"

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
    data = load_latest_slide_json(slide_num)

    updated_block = block
    for json_path, value_type, ts_key in mapping:
        if ts_key in IMMUTABLE_KEYS:
            continue
        value = extract_value(data, json_path)
        updated_block = update_ts_block(updated_block, ts_key, value, value_type)

    return ts_text[: match.start()] + updated_block + ts_text[match.end():]


def main() -> None:
    original_text = TS_PATH.read_text(encoding="utf-8")
    updated_text = original_text

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


if __name__ == "__main__":
    main()
