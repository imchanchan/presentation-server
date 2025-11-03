import fs from "fs";
import path from "path";
import mongoose from "mongoose";
import dotenv from "dotenv";
import Slide from "../models/slideModel.js";

// .env 환경변수 로드
dotenv.config();

// 현재 디렉토리 기준으로 slides 폴더 경로 설정
const slidesDir = path.resolve(process.cwd(), "slides");

async function seedSlides() {
  try {
    // 1) MongoDB 연결
    await mongoose.connect(process.env.MONGO_URI);
    console.log("✅ MongoDB Connected");

    // 2) 슬라이드 JSON 파일 목록 읽기
    const files = fs.readdirSync(slidesDir).filter(f => f.endsWith(".json"));
    console.log(`📄 Found ${files.length} slide JSON files`);

    if (files.length === 0) {
      console.warn("⚠️ No JSON files found in slides directory");
      return;
    }

    // 3) 각 파일을 DB에 삽입
    for (const file of files) {
      const filePath = path.join(slidesDir, file);
      const data = JSON.parse(fs.readFileSync(filePath, "utf-8"));

      await Slide.create(data);
      console.log(`📥 Inserted ${file}`);
    }

    // 4) 완료 후 연결 종료
    console.log("🎉 All slides inserted successfully!");
    await mongoose.connection.close();
  } catch (err) {
    console.error("❌ Error while seeding slides:", err);
    await mongoose.connection.close();
  }
}

// 실행
seedSlides();
