# Subtitle Translation Pipeline

Tool dịch phụ đề SRT hàng loạt cho phim bộ, drama dài tập bằng AI (Gemini, GPT, DeepSeek...), có giao diện đồ họa (PyQt5).

Điểm ăn tiền nhất: **Tự động quét cả bộ phim để lập bảng nhân vật & quan hệ xưng hô trước khi dịch**, giúp các tập không bị loạn ngôi xưng (tập trước anh-em, tập sau tôi-cô).

---

## 📦 Cài đặt

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

pip install PyQt5 pysrt requests pyqtspinner
