import express from "express";
import Slide from "../models/slideModel.js";

const router = express.Router();

// 모든 슬라이드 조회
router.get("/", async (req, res) => {
  try {
    const slides = await Slide.find();
    res.json(slides);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// 슬라이드 단건 조회
router.get("/:id", async (req, res) => {
  try {
    const slide = await Slide.findById(req.params.id);
    if (!slide) return res.status(404).json({ message: "Slide not found" });
    res.json(slide);
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

export default router;
