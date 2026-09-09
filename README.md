# ⚡ LLM Subtitle Translation Pipeline (v2.0)

> **AI-Powered Context-Aware Subtitle Translation & Interactive QC Studio**  
> Dịch phụ đề phim đa tập thông minh bằng LLM: Tự động phân tích quan hệ nhân vật & đồng bộ xưng hô toàn bộ phim, tích hợp giao diện QC song ngữ tương tác.

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://www.python.org/)
[![PyQt5](https://img.shields.io/badge/GUI-PyQt5-brightgreen.svg)](https://riverbankcomputing.com/software/pyqt/)
[![OpenAI Compatible](https://img.shields.io/badge/API-OpenAI%20Compatible-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 💡 Điểm Khác Biệt (Why This Project?)

Khi dịch phim nhiều tập (đặc biệt là phim Trung, Hàn, Nhật, drama ngắn), các công cụ dịch máy thông thường thường gặp lỗi nghiêm trọng:
- **Lẫn lộn nhân vật & xưng hô**: Tập 1 xưng "anh - em", tập 2 thành "tôi - cô", tập 3 thành "huynh - muội".
- **Mất ngữ cảnh**: Dịch từng câu hoặc từng file đơn lẻ mà không hiểu toàn cảnh kịch bản và quan hệ giữa các tuyến nhân vật.
- **Khó soát lỗi**: Thiếu công cụ đối chiếu song ngữ trực quan để sửa nhanh các đoạn dịch chưa mượt.

**LLM Subtitle Pipeline** giải quyết triệt để vấn đề này với quy trình 3 bước chuẩn công nghiệp:
1. **Phân tích toàn phim (Story & Character Profiling)**: Gộp toàn bộ kịch bản SRT để LLM trích xuất bảng nhân vật, tính cách, bối cảnh và ma trận xưng hô.
2. **Dịch giữ ngữ cảnh (Context-Aware Batch Translation)**: Sử dụng bảng hồ sơ nhân vật làm prompt nền khi dịch từng tập, đảm bảo nhất quán 100% ngôi xưng và văn phong.
3. **QC Song ngữ tương tác (Interactive QC & Re-translate)**: Giao diện bảng song ngữ trực quan, hỗ trợ dịch lại theo từng vùng chọn hoặc tự động QC rà soát lỗi.

---

## ✨ Tính Năng Nổi Bật

- 🔍 **Character Profiling tự động**: Trích xuất tên gốc, tên dịch, giới tính, vai trò, xưng hô và tóm tắt cốt truyện chỉ với 1 cú click.
- 🚀 **Batch Processing & Streaming**: Dịch hàng loạt toàn bộ folder SRT với tiến trình hiển thị dạng real-time token stream.
- 🛠️ **Cơ chế cứu hộ JSON thông minh**: Tự động phục hồi khi LLM trả JSON bị cắt đuôi (truncated) hoặc sai định dạng nhờ regex recovery.
- 📝 **Interactive QC Studio**:
  - Xem đối chiếu song ngữ theo từng câu (ID, câu gốc, bản dịch, trạng thái).
  - Nhấp đúp để chỉnh sửa trực tiếp.
  - **Dịch lại linh hoạt**: Chọn một hoặc nhiều câu bất kỳ để yêu cầu LLM dịch lại theo ngữ cảnh.
- 🔌 **Hỗ trợ mọi LLM (OpenAI API Standard)**: Dễ dàng cấu hình với OpenAI (GPT-4o), Google Gemini, DeepSeek, Claude, Ollama hoặc các proxy nội bộ.
- ✍️ **Tùy biến Prompt**: Cho phép can thiệp và lưu template prompt cho cả 3 bước (Phân tích, Dịch, QC).
- 📤 **Tự động xuất SRT**: Tự động đóng gói và ghi đè bản dịch vào file `.srt` chuẩn UTF-8, giữ nguyên timeline gốc.

---

## 🖥️ Giao Diện Ứng Dụng

| 1. Phân tích nhân vật & cốt truyện | 2. Dịch hàng loạt & Stream log |
| :---: | :---: |
| *(Chèn ảnh chụp màn hình Tab 1 vào đây)* | *(Chèn ảnh chụp màn hình Tab 2 vào đây)* |

| 3. QC Song ngữ & Dịch lại tương tác | 4. Cấu hình Prompt động |
| :---: | :---: |
| *(Chèn ảnh chụp màn hình Tab 3 vào đây)* | *(Chèn ảnh chụp màn hình Tab 4 vào đây)* |

---

## 📦 Cài Đặt

### 1. Yêu cầu hệ thống
- Python 3.8 trở lên
- Hệ điều hành: Windows, macOS hoặc Linux

### 2. Cài đặt thư viện
```bash
git clone https://github.com/<your-username>/llm-subtitle-pipeline.git
cd llm-subtitle-pipeline

# Khởi tạo môi trường ảo (khuyên dùng)
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Cài đặt dependencies
pip install -r requirements.txt
