import argparse
import json
import os
import sys
from pathlib import Path
import re
from typing import Optional

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError



# DEFAULT_COLLECTION_NAME = "cashbrush"
DEFAULT_COLLECTION_NAME = "retort_1219_one"

def load_env():
    project_root = Path(__file__).resolve().parents[1]
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


def parse_args():
    default_collection = os.getenv("MONGO_COLLECTION_NAME", DEFAULT_COLLECTION_NAME)
    parser = argparse.ArgumentParser(
        description="슬라이드 JSON을 MongoDB에 적재합니다."
    )
    parser.add_argument(
        "--collection",
        "-c",
        default=default_collection,
        help="적재할 MongoDB 컬렉션 이름 (기본값: %(default)s)",
    )
    parser.add_argument(
        "--database",
        "-d",
        default=None,
        help="DB 이름을 덮어씌웁니다. 지정하지 않으면 .env 의 MONGO_DB_NAME 사용",
    )
    parser.add_argument(
        "--slides-dir",
        default=None,
        help="슬라이드 JSON이 위치한 경로 (기본값: <project_root>/slides)",
    )
    return parser.parse_args()


def get_slides_dir(override: Optional[str] = None) -> Path:
    if override:
        return Path(override).expanduser().resolve()
    project_root = Path(__file__).resolve().parents[1]
    return project_root / "slides"


def ensure_collection(db, name: str):
    if name not in db.list_collection_names():
        db.create_collection(name)
        print(f"[NEW] 새로운 컬렉션 생성: '{name}'")
    else:
        print(f"[INFO] 컬렉션 '{name}' 이미 존재함")


def read_json(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def extract_slide_number(filename: str) -> int:
    stem = Path(filename).stem
    match = re.search(r"slide(\d+)", stem)
    return int(match.group(1)) if match else None


def insert_document(collection, payload, filename: str):
    slide_number = extract_slide_number(filename)
    if slide_number is None:
        print(f"[WARN] {filename} 에서 슬라이드 번호를 찾을 수 없습니다. 건너뜀.")
        return

    # _id만 slide_number로 사용
    doc = {
        "_id": slide_number,
        "content": payload
    }

    collection.replace_one({"_id": slide_number}, doc, upsert=True)
    print(f"[OK] 슬라이드 #{slide_number} 삽입 완료 ({filename})")


def main():
    load_env()
    args = parse_args()

    mongo_uri = os.getenv("MONGO_URI")
    mongo_db_name = args.database or os.getenv("MONGO_DB_NAME")
    collection_name = args.collection

    if not mongo_uri:
        print("[ERROR] 환경 변수 'MONGO_URI'가 설정되어 있지 않습니다.")
        sys.exit(1)

    slides_dir = get_slides_dir(args.slides_dir)
    if not slides_dir.exists():
        print(f"[ERROR] 슬라이드 폴더를 찾을 수 없습니다: {slides_dir}")
        sys.exit(1)

    json_files = sorted(slides_dir.glob("*.json"), key=lambda p: extract_slide_number(p.name))
    print(f"[INFO] 총 {len(json_files)}개의 슬라이드 JSON 파일을 찾았습니다.")

    if not json_files:
        print("[WARN] 처리할 JSON 파일이 없습니다. 프로그램을 종료합니다.")
        return

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)
    try:
        client.admin.command("ping")
        print("[SUCCESS] MongoDB 연결 성공")

        if mongo_db_name:
            target_db = client[mongo_db_name]
        else:
            try:
                target_db = client.get_default_database()
            except ConfigurationError as err:
                print("[ERROR] 데이터베이스 이름이 지정되지 않았습니다. 'MONGO_DB_NAME'을 설정하거나 URI에 DB명을 포함하세요.")
                print(f"         상세 정보: {err}")
                sys.exit(1)

        ensure_collection(target_db, collection_name)
        collection = target_db[collection_name]

        # 기존 데이터 전부 삭제
        deleted_count = collection.delete_many({}).deleted_count
        print(f"[INFO] 기존 문서 {deleted_count}개 삭제 완료")

        for json_file in json_files:
            try:
                payload = read_json(json_file)
            except json.JSONDecodeError as err:
                print(f"[ERROR] {json_file.name} 파싱 실패: {err}")
                continue

            insert_document(collection, payload, json_file.name)

        print("[DONE] 모든 슬라이드 삽입이 완료되었습니다.")
    except Exception as err:
        print(f"[ERROR] 슬라이드 데이터 입력 중 오류 발생: {err}")
        sys.exit(1)
    finally:
        client.close()
        print("[INFO] MongoDB 연결 종료")


if __name__ == "__main__":
    main()
