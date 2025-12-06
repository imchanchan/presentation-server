import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient


def load_env():
    project_root = Path(__file__).resolve().parents[1]
    env_file = project_root / ".env"

    if env_file.exists():
        load_dotenv(env_file)
    else:
        load_dotenv()


def main():
    load_env()

    mongo_uri = os.getenv("MONGO_URI")
    mongo_db_name = os.getenv("MONGO_DB_NAME")

    if not mongo_uri:
        print(" [!] MONGO_URI가 설정되어 있지 않습니다.")
        sys.exit(1)

    client = MongoClient(mongo_uri, serverSelectionTimeoutMS=5000)

    try:
        client.admin.command("ping")

        print("=" * 60)
        print(" MongoDB Connection Successful")
        print("=" * 60)

        if mongo_db_name:
            db = client[mongo_db_name]
            collections = db.list_collection_names()

            print(f" Database     : {mongo_db_name}")
            print(" Collections  :")

            if collections:
                for name in collections:
                    print(f"   - {name}")
            else:
                print("   (No collections found)")
        else:
            print(" Database name not provided.")

        print("=" * 60)


    except Exception as err:
        print(f" [!] MongoDB 연결 실패: {err}")
        sys.exit(1)
    finally:
        client.close()


if __name__ == "__main__":
    main()
