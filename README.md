# Subtitle Translation Pipeline

Tool dịch phụ đề SRT hàng loạt cho phim bộ, drama dài tập bằng AI (Gemini, GPT, DeepSeek...), có giao diện đồ họa (PyQt5).

Điểm ăn tiền nhất: **Tự động quét cả bộ phim để lập bảng nhân vật & quan hệ xưng hô trước khi dịch**, giúp các tập không bị loạn ngôi xưng (tập trước anh-em, tập sau tôi-cô).

---

## 🛠 Tool làm được gì?

- **Tự phân tích nhân vật:** Đọc hết các file SRT trong folder để tóm tắt cốt truyện, trích xuất tên nhân vật và cách xưng hô (anh/em, tỷ/muội, sếp/em...).
- **Dịch hàng loạt theo ngữ cảnh:** Áp bảng nhân vật vào từng tập khi dịch, đảm bảo nhất quán toàn bộ phim.
- **Giao diện QC song ngữ:** Hiển thị đối chiếu câu gốc - câu dịch. Click đúp sửa tay trực tiếp hoặc bôi đen một đoạn bất kỳ bấm "Dịch lại".
- **Hỗ trợ mọi API chuẩn OpenAI:** Dùng được với Gemini, GPT-4o, DeepSeek, Claude, vLLM hoặc Ollama (hỗ trợ stream chữ thời gian thực).
- **Tự động xuất file:** Xuất thẳng ra file `.srt` chuẩn UTF-8, giữ nguyên timeline gốc.

---

## 📦 Cài đặt

Yêu cầu Python 3.8+. Cài các thư viện cần thiết:

```bash
pip install PyQt5 pysrt requests pyqtspinner
