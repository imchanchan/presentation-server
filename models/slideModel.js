import mongoose from "mongoose";

// 모든 JSON 구조 허용 (유연하게)
const slideSchema = new mongoose.Schema({}, { strict: false });

const Slide = mongoose.model("Slide", slideSchema);
export default Slide;
