#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
⚡ Subtitle Translation Pipeline v2.0
Flow: Phân tích toàn bộ phim (1 lần) → Dịch từng SRT → QC Song ngữ tương tác
"""

import os
import re
import sys
import json
import time
import queue
import threading
from typing import List, Dict

import requests
import pysrt
from pyqtspinner import WaitingSpinner

from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSettings
from PyQt5.QtGui import QFont, QTextCursor, QColor
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QGroupBox, QCheckBox, QDialog, QFormLayout, QSpinBox,
    QLineEdit, QTabWidget, QMessageBox, QPlainTextEdit, QSplitter,
    QListWidget, QListWidgetItem, QInputDialog, QAbstractItemView
)

# ===================== APP CONFIG =====================
def app_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

OUTPUT_DIR = os.path.join(app_dir(), "pipeline_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ===================== CONSTANTS =====================
LANG_MAP = {
    "vi": "Tiếng Việt", "en": "English", "ta": "Tamil",
    "hi": "Hindi", "ar": "Arabic", "id": "Indonesian", "it": "Italian",
}

DEFAULT_GENRES = [
    "Modern Romance", "Historical Romance", "Wuxia / Xianxia",
    "Comedy", "Action / Thriller", "School / Youth", "Family / Drama",
]

DEFAULT_SOURCE_LANGS = [
    "Tiếng Trung (Chinese)", "Tiếng Anh (English)",
    "Tiếng Hàn (Korean)", "Tiếng Nhật (Japanese)", "Tiếng Việt",
]

DEFAULT_MODELS = [
    "gemini-pro", "gemini-flash", "gemini-flash-thinking", "gemini-flash-lite",
]

# ===================== STEP METADATA =====================
STEP_NAMES = {
    0: "B0: Phân tích phim",
    1: "B1: Dịch",
    2: "B2: QC",
}

STEP_TAB_NAMES = {
    0: "① Phân tích Phim (toàn bộ SRT)",
    1: "② Dịch (từng SRT)",
    2: "③ QC Dịch (từng SRT)",
}

STEP_VARIABLES_INFO = {
    0: "Biến: {ALL_SRT_DATA}  {SOURCE_LANG}  {TARGET_LANG}  {GENRE}",
    1: "Biến: {SRT_JSON}  {CHAR_PROFILES}  {SOURCE_LANG}  {TARGET_LANG}  {GENRE}",
    2: "Biến: {RAW_TRANSLATION}  {CHAR_PROFILES}  {SRT_DATA}  {SOURCE_LANG}  {TARGET_LANG}  {GENRE}",
}

# ===================== DEFAULT PROMPTS =====================
DEFAULT_PROMPTS = {
    0: """Bạn là chuyên gia phân tích kịch bản phim chuyên nghiệp.

THÔNG TIN PHIM:
- Ngôn ngữ gốc: {SOURCE_LANG}
- Ngôn ngữ đích dịch: {TARGET_LANG}
- Thể loại: {GENRE}

NHIỆM VỤ:
Đọc kỹ TOÀN BỘ phụ đề của bộ phim bên dưới. Phân tích và trích xuất CHI TIẾT:

1. DANH SÁCH NHÂN VẬT — Với mỗi nhân vật:
   - Tên gốc ({SOURCE_LANG}) + Tên đề xuất khi dịch sang {TARGET_LANG}
   - Giới tính, Độ tuổi ước tính
   - Vai trò: Chính / Phụ / Phản diện
   - Tính cách: Mô tả ngắn dựa trên lời thoại
   - Quan hệ với từng nhân vật khác
   - Xưng hô khi dịch sang {TARGET_LANG}: tự xưng gì, gọi từng người khác bằng gì

2. TÓM TẮT NỘI DUNG PHIM (200-500 từ)

3. GIỌNG ĐIỆU & PHONG CÁCH chung

TOÀN BỘ PHỤ ĐỀ:
{ALL_SRT_DATA}""",

    1: """Bạn là chuyên gia dịch phụ đề phim chuyên nghiệp.

# THÔNG TIN NHÂN VẬT (đã phân tích)
{CHAR_PROFILES}

# CẤU HÌNH DỊCH
- Ngôn ngữ nguồn: {SOURCE_LANG}
- Ngôn ngữ đích: {TARGET_LANG}
- Thể loại: {GENRE}

# QUY TẮC DỊCH
1. Dịch chính xác nghĩa, tự nhiên như lời thoại phim bản địa {TARGET_LANG}
2. BẮT BUỘC sử dụng đúng tên nhân vật và xưng hô theo bảng nhân vật
3. Giữ đúng cảm xúc, giọng điệu, tiếng lóng
4. Ngắn gọn, dễ đọc trên màn hình phụ đề
5. KHÔNG thêm, xóa, gộp, tách câu. Giữ nguyên ID, thứ tự, số lượng

# ĐỊNH DẠNG OUTPUT
Trả về DUY NHẤT JSON array:
[{{"id": 1, "text": "bản dịch"}}, {{"id": 2, "text": "bản dịch"}}]
- Ký tự đầu là [ cuối là ]
- KHÔNG markdown, KHÔNG ```, KHÔNG giải thích

# DỮ LIỆU CẦN DỊCH
{SRT_JSON}""",

    2: """# KIỂM DUYỆT BẢN DỊCH PHỤ ĐỀ

## BẢN DỊCH CẦN QC
{RAW_TRANSLATION}

## NHÂN VẬT THAM CHIẾU
{CHAR_PROFILES}

## PHỤ ĐỀ GỐC (đối chiếu)
{SRT_DATA}

## CẤU HÌNH
- Nguồn: {SOURCE_LANG} → Đích: {TARGET_LANG}
- Thể loại: {GENRE}

## NHIỆM VỤ
Rà soát bản dịch, SỬA các lỗi:
1. Tên nhân vật: đúng với bảng nhân vật, nhất quán
2. Xưng hô: đúng quan hệ, phù hợp hoàn cảnh
3. Dịch sai nghĩa: đối chiếu phụ đề gốc
4. Văn phong: tự nhiên, phù hợp thể loại {GENRE}
5. Thiếu/thừa: không bỏ sót, không thêm câu

## QUY TẮC
- CHỈ SỬA những gì sai, giữ nguyên những gì đã đúng
- Giữ nguyên ID, thứ tự, số lượng
- Output: JSON array [{{"id": N, "text": "bản dịch đã QC"}}]
- Ký tự đầu là [ cuối là ]
- KHÔNG markdown, KHÔNG giải thích""",
}

# ===================== UTILITIES =====================

def read_srt_file(filepath: str):
    """Read SRT file with encoding auto-detection. Returns (SubRipFile, raw_text)."""
    for enc in ['utf-8-sig', 'utf-8', 'gbk', 'gb2312', 'gb18030', 'big5', 'euc-kr', 'shift_jis', 'latin-1']:
        try:
            subs = pysrt.open(filepath, encoding=enc)
            with open(filepath, 'r', encoding=enc) as f:
                text = f.read()
            return subs, text
        except (UnicodeDecodeError, UnicodeError):
            continue
    raise RuntimeError(f"Không đọc được file: {filepath}")


def parse_translation_json(text: str, log_fn=None) -> Dict[int, str]:
    """Parse JSON array [{"id": N, "text": "..."}] from LLM response."""
    def _log(msg):
        if log_fn: log_fn(msg)

    if not text or not text.strip():
        _log("❌ Response rỗng!")
        return {}

    cleaned = re.sub(r'```(?:json)?\s*\n?', '', text.strip())
    cleaned = re.sub(r'\n?```\s*$', '', cleaned).strip()
    cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)

    def _extract(arr):
        result = {}
        for item in arr:
            if isinstance(item, dict) and "id" in item and "text" in item:
                result[int(item["id"])] = str(item["text"])
        return result

    # Strategy 1: Direct
    try:
        arr = json.loads(cleaned)
        if isinstance(arr, list):
            result = _extract(arr)
            if result:
                _log(f"✅ JSON parse trực tiếp ({len(result)} items)")
                return result
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: Regex find array
    m = re.search(r'\[\s*\{.*\}\s*\]', cleaned, re.DOTALL)
    if m:
        try:
            arr = json.loads(m.group(0))
            result = _extract(arr)
            if result:
                _log(f"✅ JSON regex extract ({len(result)} items)")
                return result
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 3: Truncated
    if '[' in cleaned and ']' not in cleaned:
        _log("⚠️ Response bị cắt. Đang cứu hộ...")
        arr_start = cleaned.find('[')
        last_brace = cleaned.rfind('}')
        if arr_start >= 0 and last_brace > arr_start:
            try:
                arr = json.loads(cleaned[arr_start:last_brace + 1].rstrip().rstrip(',') + '\n]')
                result = _extract(arr)
                if result:
                    _log(f"✅ Cứu hộ truncated ({len(result)} items)")
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

    # Strategy 4: Regex items
    blocks = re.findall(
        r'\{\s*"id"\s*:\s*(\d+)\s*,\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"\s*\}',
        cleaned, re.DOTALL
    )
    if not blocks:
        blocks = re.findall(
            r'\{\s*"text"\s*:\s*"((?:[^"\\]|\\.)*)"\s*,\s*"id"\s*:\s*(\d+)\s*\}',
            cleaned, re.DOTALL
        )
        if blocks:
            blocks = [(b[1], b[0]) for b in blocks]
    if blocks:
        _log(f"⚠️ Regex rescue: {len(blocks)} items")
        return {int(b[0]): b[1] for b in blocks}

    _log("❌ Không parse được JSON!")
    return {}


def merge_all_srt_texts(folder_path: str):
    """Gộp tất cả SRT trong folder thành 1 text. Returns (merged_text, sorted_filenames)."""
    files = [f for f in os.listdir(folder_path) if f.lower().endswith('.srt')]
    files.sort(key=lambda x: int(re.sub(r'\D', '', os.path.splitext(x)[0]) or 0))
    parts = []
    for f in files:
        try:
            with open(os.path.join(folder_path, f), 'r', encoding='utf-8-sig', errors='ignore') as fh:
                content = fh.read().strip()
            parts.append(f"========== {f} ==========\n{content}")
        except Exception:
            parts.append(f"========== {f} ==========\n(lỗi đọc file)")
    return "\n\n".join(parts), files


def get_project_dir(source_folder: str) -> str:
    """Get/create project output dir INSIDE source folder."""
    pdir = os.path.join(source_folder, "output")
    os.makedirs(pdir, exist_ok=True)
    os.makedirs(os.path.join(pdir, "translations"), exist_ok=True)
    os.makedirs(os.path.join(pdir, "output_srt"), exist_ok=True)
    return pdir


def save_character_profile(pdir: str, text: str):
    with open(os.path.join(pdir, "character_profile.txt"), "w", encoding="utf-8") as f:
        f.write(text)


def load_character_profile(pdir: str) -> str:
    path = os.path.join(pdir, "character_profile.txt")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def save_translation(pdir: str, srt_filename: str, cues: list):
    path = os.path.join(pdir, "translations", srt_filename.replace('.srt', '.json'))
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cues, f, ensure_ascii=False, indent=2)


def load_translation(pdir: str, srt_filename: str) -> list:
    path = os.path.join(pdir, "translations", srt_filename.replace('.srt', '.json'))
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def get_srt_status(pdir: str, srt_filename: str) -> str:
    """Check translation status for a SRT file."""
    cues = load_translation(pdir, srt_filename)
    if not cues:
        return "⬜ Chưa dịch"
    has_text = sum(1 for c in cues if c.get("text", "").strip())
    edited = sum(1 for c in cues if c.get("edited", False))
    total = len(cues)
    if has_text == 0:
        return "⬜ Chưa dịch"
    label = f"✅ {has_text}/{total}"
    if edited > 0:
        label += f" (✏️{edited})"
    return label


def export_srt_file(source_folder: str, pdir: str, srt_filename: str, log_fn=None):
    """Export translated SRT file. Returns (out_path, replaced_count) or (None, 0)."""
    cues = load_translation(pdir, srt_filename)
    if not cues:
        return None, 0
    trans_dict = {c["id"]: c["text"] for c in cues if c.get("text", "").strip()}
    if not trans_dict:
        return None, 0
    filepath = os.path.join(source_folder, srt_filename)
    try:
        subs, _ = read_srt_file(filepath)
    except Exception as e:
        if log_fn: log_fn(f"⚠️ Export lỗi đọc SRT gốc: {e}")
        return None, 0
    replaced = 0
    for sub in subs:
        if sub.index in trans_dict:
            sub.text = trans_dict[sub.index]
            replaced += 1
    out_dir = os.path.join(pdir, "output_srt")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, srt_filename)
    subs.save(out_path, encoding='utf-8')
    if log_fn: log_fn(f"📤 Xuất SRT: {srt_filename} ({replaced}/{len(subs)} câu)")
    return out_path, replaced


def save_project_meta(pdir: str, meta: dict):
    """Save project metadata to project.json."""
    path = os.path.join(pdir, "project.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)


def load_project_meta(pdir: str) -> dict:
    """Load project metadata from project.json."""
    path = os.path.join(pdir, "project.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


# ===================== PIPELINE WORKER =====================

class PipelineWorker(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int, int)       # (current, total)
    analysis_done = pyqtSignal(str)               # profile_text
    srt_status_signal = pyqtSignal(str, str)      # (srt_filename, status)
    translation_done = pyqtSignal(str, list)      # (srt_filename, cues)
    stream_chunk_signal = pyqtSignal(str)
    stream_clear_signal = pyqtSignal(str)
    finished_signal = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.stop_flag = False
        self.use_stream = True

        # API config
        self.api_url = ""
        self.api_key = ""
        self.model = ""
        self.timeout = 300
        self.max_retries = 2

        # Task config
        self.task_type = ""   # "analysis", "translate_all", "translate_one", "retranslate_range"
        self.task_data = {}

        # Prompts
        self.prompts: Dict[int, str] = {}

    def _log(self, msg: str):
        self.log_signal.emit(msg)

    def _call_api(self, prompt: str, step_name: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": self.use_stream,
        }

        mode = "Stream" if self.use_stream else "Non-stream"
        self._log(f"📡 {step_name}: Gửi request [{mode}] ({len(prompt):,} chars)...")
        t0 = time.time()

        try:
            req_timeout = (15, None) if self.use_stream else (15, self.timeout)
            resp = requests.post(
                self.api_url, json=payload, headers=headers,
                stream=self.use_stream, timeout=req_timeout
            )
            resp.raise_for_status()
        except requests.exceptions.ConnectionError:
            raise RuntimeError(f"Không kết nối được API: {self.api_url}")
        except requests.exceptions.Timeout:
            raise RuntimeError(f"API timeout ({self.timeout}s)")
        except requests.exceptions.HTTPError as e:
            raise RuntimeError(f"HTTP Error: {e.response.status_code} - {e.response.text[:200]}")

        if not self.use_stream:
            try:
                data = resp.json()
                full_text = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                raise RuntimeError(f"Parse error: {e}")
            elapsed = time.time() - t0
            self._log(f"✅ {step_name}: Hoàn tất ({len(full_text):,} ký tự, {elapsed:.1f}s)")
            self.stream_clear_signal.emit(step_name)
            self.stream_chunk_signal.emit(full_text)
            return full_text

        # Stream mode
        full_text = ""
        last_log = time.time()
        first_chunk = True

        for line in resp.iter_lines(decode_unicode=True):
            if self.stop_flag:
                resp.close()
                raise RuntimeError("USER_STOPPED")
            if not line:
                continue
            if line.startswith("data: "):
                data_str = line[6:].strip()
                if data_str == "[DONE]":
                    break
                try:
                    data = json.loads(data_str)
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("delta", {}).get("content", "")
                        if content:
                            if first_chunk:
                                self.stream_clear_signal.emit(step_name)
                                first_chunk = False
                            full_text += content
                            self.stream_chunk_signal.emit(content)
                except (json.JSONDecodeError, KeyError, IndexError):
                    continue
            now = time.time()
            if now - last_log > 5:
                self._log(f"⏳ {step_name}: Đang nhận... ({len(full_text):,} ký tự, {now - t0:.0f}s)")
                last_log = now

        elapsed = time.time() - t0
        self._log(f"✅ {step_name}: Hoàn tất ({len(full_text):,} ký tự, {elapsed:.1f}s)")
        return full_text

    def _call_api_with_retry(self, prompt: str, step_name: str) -> str:
        for attempt in range(self.max_retries + 1):
            if self.stop_flag:
                raise RuntimeError("USER_STOPPED")
            try:
                result = self._call_api(prompt, step_name)
                if result.strip():
                    return result
                self._log("⚠️ Response rỗng!")
            except RuntimeError as e:
                if "USER_STOPPED" in str(e):
                    raise
                self._log(f"⚠️ Lỗi: {e}")
            if attempt < self.max_retries:
                self._log(f"🔄 Thử lại ({attempt + 2}/{self.max_retries + 1})...")
                time.sleep(3)
        raise RuntimeError(f"{step_name}: không có kết quả sau {self.max_retries + 1} lần thử!")

    def run(self):
        try:
            if self.task_type == "analysis":
                self._run_analysis()
            elif self.task_type == "translate_all":
                self._run_translate_all()
            elif self.task_type == "translate_one":
                self._run_translate_one()
            elif self.task_type == "retranslate_range":
                self._run_retranslate_range()
            else:
                self._log(f"❌ Unknown task type: {self.task_type}")
        except RuntimeError as e:
            if "USER_STOPPED" in str(e):
                self._log("🛑 Đã dừng bởi người dùng.")
            else:
                self._log(f"❌ Lỗi: {e}")
        except Exception as e:
            self._log(f"🔥 Lỗi hệ thống: {e}")
        finally:
            self.finished_signal.emit()

    def _build_prompt(self, step: int, variables: dict) -> str:
        template = self.prompts.get(step, "")
        for key, val in variables.items():
            template = template.replace(f"{{{key}}}", str(val))
        return template

    # ---------- ANALYSIS (B0) ----------
    def _run_analysis(self):
        d = self.task_data
        folder = d["folder"]
        self._log("🔍 Đang gộp tất cả SRT files...")
        all_text, files = merge_all_srt_texts(folder)
        self._log(f"📂 Gộp {len(files)} files ({len(all_text):,} ký tự)")

        variables = {
            "ALL_SRT_DATA": all_text,
            "SOURCE_LANG": d["source_lang"],
            "TARGET_LANG": d["target_lang"],
            "GENRE": d["genre"],
        }
        prompt = self._build_prompt(0, variables)
        result = self._call_api_with_retry(prompt, "Phân tích phim")

        save_character_profile(d["project_dir"], result)
        self._log(f"💾 Đã lưu profile nhân vật ({len(result):,} ký tự)")
        self.analysis_done.emit(result)

    # ---------- TRANSLATE ALL (B1+B2 for all SRTs) ----------
    def _run_translate_all(self):
        d = self.task_data
        folder = d["folder"]
        pdir = d["project_dir"]
        srt_files = d["srt_files"]
        profile = d["profile"]
        skip_existing = d.get("skip_existing", True)

        total = len(srt_files)
        translated = 0
        skipped = 0

        for i, srt_file in enumerate(srt_files):
            if self.stop_flag:
                raise RuntimeError("USER_STOPPED")

            # Skip if already translated
            if skip_existing:
                existing = load_translation(pdir, srt_file)
                if existing and any(c.get("text", "").strip() for c in existing):
                    self._log(f"⏭ [{i+1}/{total}] {srt_file} đã dịch. Bỏ qua.")
                    skipped += 1
                    self.progress_signal.emit(i + 1, total)
                    continue

            self._log(f"\n{'═' * 50}")
            self._log(f"📋 [{i+1}/{total}] {srt_file}")
            self.srt_status_signal.emit(srt_file, "🔄 Đang dịch...")
            self.progress_signal.emit(i, total)

            cues = self._translate_single_srt(folder, pdir, srt_file, profile, d)

            if cues:
                translated += 1
                status = get_srt_status(pdir, srt_file)
                self.srt_status_signal.emit(srt_file, status)
                self.translation_done.emit(srt_file, cues)
            else:
                self.srt_status_signal.emit(srt_file, "❌ Lỗi")

            if not self.stop_flag and i < total - 1:
                time.sleep(1)

        self.progress_signal.emit(total, total)
        self._log(f"\n🏁 Hoàn tất! Dịch: {translated}, Bỏ qua: {skipped}, Tổng: {total}")

    # ---------- TRANSLATE ONE ----------
    def _run_translate_one(self):
        d = self.task_data
        srt_file = d["srt_file"]
        self._log(f"\n{'═' * 50}")
        self._log(f"📋 Dịch lại: {srt_file}")
        self.srt_status_signal.emit(srt_file, "🔄 Đang dịch...")

        cues = self._translate_single_srt(d["folder"], d["project_dir"], srt_file, d["profile"], d)

        if cues:
            status = get_srt_status(d["project_dir"], srt_file)
            self.srt_status_signal.emit(srt_file, status)
            self.translation_done.emit(srt_file, cues)
        else:
            self.srt_status_signal.emit(srt_file, "❌ Lỗi")

    def _translate_single_srt(self, folder, pdir, srt_file, profile, d) -> list:
        """Translate a single SRT (B1 + optional B2). Returns cues list or []."""
        filepath = os.path.join(folder, srt_file)
        try:
            subs, srt_data = read_srt_file(filepath)
        except Exception as e:
            self._log(f"❌ Không đọc được {srt_file}: {e}")
            return []

        srt_json_arr = [{"id": s.index, "text": s.text.strip()} for s in subs]
        srt_json = json.dumps(srt_json_arr, ensure_ascii=False, indent=2)
        self._log(f"📂 {len(subs)} câu phụ đề")

        variables = {
            "SRT_JSON": srt_json, "SRT_DATA": srt_data,
            "CHAR_PROFILES": profile,
            "SOURCE_LANG": d["source_lang"], "TARGET_LANG": d["target_lang"],
            "GENRE": d["genre"],
        }

        # B1: Translate
        prompt_b1 = self._build_prompt(1, variables)
        raw_result = self._call_api_with_retry(prompt_b1, f"Dịch {srt_file}")
        trans_dict = parse_translation_json(raw_result, self._log)

        if not trans_dict:
            self._log(f"❌ Không parse được kết quả dịch {srt_file}")
            return []

        # B2: QC (nếu có prompt)
        prompt_b2_template = self.prompts.get(2, "").strip()
        if prompt_b2_template:
            variables["RAW_TRANSLATION"] = raw_result
            prompt_b2 = self._build_prompt(2, variables)
            try:
                qc_result = self._call_api_with_retry(prompt_b2, f"QC {srt_file}")
                qc_dict = parse_translation_json(qc_result, self._log)
                if qc_dict:
                    self._log(f"✅ QC cập nhật {len(qc_dict)} câu")
                    trans_dict.update(qc_dict)
            except Exception as e:
                self._log(f"⚠️ QC lỗi (giữ bản dịch thô): {e}")

        # Build cues
        cues = []
        for sub in subs:
            cues.append({
                "id": sub.index,
                "original": sub.text.strip(),
                "text": trans_dict.get(sub.index, ""),
                "edited": False,
            })

        save_translation(pdir, srt_file, cues)
        ok = sum(1 for c in cues if c["text"].strip())
        self._log(f"💾 Lưu {srt_file}: {ok}/{len(subs)} câu")

        # Auto-export SRT
        export_srt_file(folder, pdir, srt_file, self._log)

        return cues

    # ---------- RETRANSLATE RANGE ----------
    def _run_retranslate_range(self):
        d = self.task_data
        srt_file = d["srt_file"]
        cue_ids = set(d["cue_ids"])
        folder = d["folder"]
        pdir = d["project_dir"]
        profile = d["profile"]

        self._log(f"🔄 Dịch lại {len(cue_ids)} cue từ {srt_file}...")
        self.srt_status_signal.emit(srt_file, "🔄 Re-translate...")

        filepath = os.path.join(folder, srt_file)
        try:
            subs, _ = read_srt_file(filepath)
        except Exception as e:
            self._log(f"❌ Không đọc được: {e}")
            return

        selected = [{"id": s.index, "text": s.text.strip()} for s in subs if s.index in cue_ids]
        srt_json = json.dumps(selected, ensure_ascii=False, indent=2)

        variables = {
            "SRT_JSON": srt_json, "CHAR_PROFILES": profile,
            "SOURCE_LANG": d["source_lang"], "TARGET_LANG": d["target_lang"],
            "GENRE": d["genre"],
        }
        prompt = self._build_prompt(1, variables)
        result = self._call_api_with_retry(prompt, f"Re-translate {len(cue_ids)} cue")
        new_dict = parse_translation_json(result, self._log)

        if not new_dict:
            self._log("❌ Không parse được kết quả!")
            return

        # Update existing translation
        existing = load_translation(pdir, srt_file)
        if not existing:
            self._log("⚠️ Chưa có bản dịch gốc!")
            return

        updated = 0
        for cue in existing:
            if cue["id"] in new_dict:
                cue["text"] = new_dict[cue["id"]]
                cue["edited"] = False
                updated += 1

        save_translation(pdir, srt_file, existing)
        self._log(f"✅ Đã cập nhật {updated}/{len(cue_ids)} cue")

        # Auto-export SRT
        export_srt_file(folder, pdir, srt_file, self._log)

        status = get_srt_status(pdir, srt_file)
        self.srt_status_signal.emit(srt_file, status)
        self.translation_done.emit(srt_file, existing)


# ===================== SETTINGS DIALOG =====================

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚙️ Cài đặt Pipeline")
        self.setMinimumWidth(450)
        self.settings = QSettings("ThienTools", "SubPipelineV2")
        layout = QFormLayout(self)
        layout.setSpacing(14)

        self.spin_timeout = QSpinBox()
        self.spin_timeout.setRange(1, 30)
        self.spin_timeout.setSuffix(" phút")
        self.spin_timeout.setValue(self.settings.value("timeout", 5, type=int))
        layout.addRow("⏳ Timeout mỗi bước:", self.spin_timeout)

        self.spin_retries = QSpinBox()
        self.spin_retries.setRange(0, 10)
        self.spin_retries.setValue(self.settings.value("retries", 2, type=int))
        layout.addRow("🔄 Số lần thử lại:", self.spin_retries)

        btn_save = QPushButton("💾 Lưu")
        btn_save.clicked.connect(self._save)
        layout.addRow("", btn_save)

    def _save(self):
        self.settings.setValue("timeout", self.spin_timeout.value())
        self.settings.setValue("retries", self.spin_retries.value())
        self.accept()


# ===================== GENRE MANAGER DIALOG =====================

class GenreManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🎬 Quản lý Thể loại")
        self.resize(500, 420)
        self.settings = QSettings("ThienTools", "SubPipelineV2")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Thêm, sửa, xóa thể loại:"))

        self.list_widget = QListWidget()
        saved = self.settings.value("genres", DEFAULT_GENRES)
        if isinstance(saved, str):
            try: saved = json.loads(saved)
            except: saved = DEFAULT_GENRES
        if not isinstance(saved, list): saved = DEFAULT_GENRES
        for g in saved:
            if str(g).strip(): self.list_widget.addItem(str(g).strip())
        layout.addWidget(self.list_widget)

        add_lay = QHBoxLayout()
        self.line_new = QLineEdit()
        self.line_new.setPlaceholderText("Tên thể loại mới...")
        btn_add = QPushButton("➕ Thêm")
        btn_add.clicked.connect(self._add)
        self.line_new.returnPressed.connect(self._add)
        add_lay.addWidget(self.line_new)
        add_lay.addWidget(btn_add)
        layout.addLayout(add_lay)

        act_lay = QHBoxLayout()
        for text, fn in [("✏️ Sửa", self._edit), ("🗑️ Xóa", self._delete), ("🔄 Mặc định", self._reset)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            act_lay.addWidget(b)
        layout.addLayout(act_lay)

        bot_lay = QHBoxLayout()
        btn_save = QPushButton("💾 Lưu")
        btn_save.clicked.connect(self._save)
        bot_lay.addStretch()
        bot_lay.addWidget(btn_save)
        layout.addLayout(bot_lay)

    def _add(self):
        txt = self.line_new.text().strip()
        if not txt: return
        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        if txt in items: return
        self.list_widget.addItem(txt)
        self.line_new.clear()

    def _edit(self):
        cur = self.list_widget.currentItem()
        if not cur: return
        val, ok = QInputDialog.getText(self, "Sửa", "Tên mới:", text=cur.text())
        if ok and val.strip(): cur.setText(val.strip())

    def _delete(self):
        row = self.list_widget.currentRow()
        if row >= 0: self.list_widget.takeItem(row)

    def _reset(self):
        if QMessageBox.question(self, "Xác nhận", "Khôi phục mặc định?") == QMessageBox.Yes:
            self.list_widget.clear()
            for g in DEFAULT_GENRES: self.list_widget.addItem(g)

    def _save(self):
        items = [self.list_widget.item(i).text().strip() for i in range(self.list_widget.count()) if self.list_widget.item(i).text().strip()]
        if not items: items = DEFAULT_GENRES
        self.settings.setValue("genres", json.dumps(items, ensure_ascii=False))
        self.accept()


# ===================== SOURCE LANG MANAGER DIALOG =====================

class SourceLangManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("🌐 Quản lý Ngôn ngữ Nguồn")
        self.resize(500, 420)
        self.settings = QSettings("ThienTools", "SubPipelineV2")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Thêm, sửa, xóa ngôn ngữ nguồn:"))

        self.list_widget = QListWidget()
        saved = self.settings.value("source_langs", DEFAULT_SOURCE_LANGS)
        if isinstance(saved, str):
            try: saved = json.loads(saved)
            except: saved = DEFAULT_SOURCE_LANGS
        if not isinstance(saved, list): saved = DEFAULT_SOURCE_LANGS
        for s in saved:
            if str(s).strip(): self.list_widget.addItem(str(s).strip())
        layout.addWidget(self.list_widget)

        add_lay = QHBoxLayout()
        self.line_new = QLineEdit()
        self.line_new.setPlaceholderText("Tên ngôn ngữ mới...")
        btn_add = QPushButton("➕ Thêm")
        btn_add.clicked.connect(self._add)
        self.line_new.returnPressed.connect(self._add)
        add_lay.addWidget(self.line_new)
        add_lay.addWidget(btn_add)
        layout.addLayout(add_lay)

        act_lay = QHBoxLayout()
        for text, fn in [("✏️ Sửa", self._edit), ("🗑️ Xóa", self._delete), ("🔄 Mặc định", self._reset)]:
            b = QPushButton(text)
            b.clicked.connect(fn)
            act_lay.addWidget(b)
        layout.addLayout(act_lay)

        bot_lay = QHBoxLayout()
        btn_save = QPushButton("💾 Lưu")
        btn_save.clicked.connect(self._save)
        bot_lay.addStretch()
        bot_lay.addWidget(btn_save)
        layout.addLayout(bot_lay)

    def _add(self):
        txt = self.line_new.text().strip()
        if not txt: return
        items = [self.list_widget.item(i).text() for i in range(self.list_widget.count())]
        if txt in items: return
        self.list_widget.addItem(txt)
        self.line_new.clear()

    def _edit(self):
        cur = self.list_widget.currentItem()
        if not cur: return
        val, ok = QInputDialog.getText(self, "Sửa", "Tên mới:", text=cur.text())
        if ok and val.strip(): cur.setText(val.strip())

    def _delete(self):
        row = self.list_widget.currentRow()
        if row >= 0: self.list_widget.takeItem(row)

    def _reset(self):
        if QMessageBox.question(self, "Xác nhận", "Khôi phục mặc định?") == QMessageBox.Yes:
            self.list_widget.clear()
            for s in DEFAULT_SOURCE_LANGS: self.list_widget.addItem(s)

    def _save(self):
        items = [self.list_widget.item(i).text().strip() for i in range(self.list_widget.count()) if self.list_widget.item(i).text().strip()]
        if not items: items = DEFAULT_SOURCE_LANGS
        self.settings.setValue("source_langs", json.dumps(items, ensure_ascii=False))
        self.accept()


# ===================== MAIN WINDOW =====================

class MainWindow(QWidget):
    test_api_done_sig = pyqtSignal(object, str)

    def __init__(self):
        super().__init__()
        self.test_api_done_sig.connect(self._test_done)
        self.setWindowTitle("⚡ Subtitle Translation Pipeline v2.0")
        self.resize(1200, 850)
        self.setMinimumSize(900, 650)

        self.settings = QSettings("ThienTools", "SubPipelineV2")
        self.worker: PipelineWorker = None
        self.srt_folder = ""
        self.project_dir = ""
        self.srt_files: List[str] = []
        self.char_profile = ""

        # Log queue & timer
        self._log_q = queue.Queue()
        self._log_timer = QTimer(self)
        self._log_timer.setInterval(50)
        self._log_timer.timeout.connect(self._flush_logs)
        self._log_timer.start()

        # Prompt save debounce
        self._save_prompt_timer = QTimer(self)
        self._save_prompt_timer.setSingleShot(True)
        self._save_prompt_timer.setInterval(1200)
        self._save_prompt_timer.timeout.connect(self._save_prompts)

        self._build_gui()
        self._load_settings()

    # ═══════════ BUILD GUI ═══════════

    def _build_gui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)

        # ═══════════ TOP: API & CONFIG ═══════════
        top_group = QGroupBox("⚙️ Cấu hình API & Dịch thuật")
        top_lay = QVBoxLayout(top_group)
        top_lay.setSpacing(5)

        # Row 1: API
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("API URL:"))
        self.api_url = QLineEdit()
        self.api_url.setPlaceholderText("http://103.118.29.131:5918/openai/v1/chat/completions")
        row1.addWidget(self.api_url, 3)
        row1.addWidget(QLabel("Key:"))
        self.api_key = QLineEdit()
        self.api_key.setEchoMode(QLineEdit.Password)
        row1.addWidget(self.api_key, 1)
        row1.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        self.model_combo.addItems(DEFAULT_MODELS)
        row1.addWidget(self.model_combo, 1)
        self.chk_stream = QCheckBox("Stream")
        self.chk_stream.setChecked(True)
        row1.addWidget(self.chk_stream)
        self.btn_test = QPushButton("🧪 Test API")
        self.btn_test.clicked.connect(self._test_api)
        row1.addWidget(self.btn_test)
        top_lay.addLayout(row1)

        # Row 2: Genre, Source Lang, Target Lang
        row2 = QHBoxLayout()
        row2.addWidget(QLabel("Thể loại:"))
        self.genre_combo = QComboBox()
        row2.addWidget(self.genre_combo, 1)
        btn_genre = QPushButton("⚙️")
        btn_genre.setFixedWidth(36)
        btn_genre.clicked.connect(self._open_genre_manager)
        row2.addWidget(btn_genre)

        row2.addWidget(QLabel("NN Nguồn:"))
        self.source_combo = QComboBox()
        row2.addWidget(self.source_combo, 1)
        btn_src = QPushButton("⚙️")
        btn_src.setFixedWidth(36)
        btn_src.clicked.connect(self._open_source_lang_manager)
        row2.addWidget(btn_src)

        row2.addWidget(QLabel("NN Đích:"))
        self.lang_checks: Dict[str, QCheckBox] = {}
        for code, name in LANG_MAP.items():
            chk = QCheckBox(name)
            self.lang_checks[code] = chk
            row2.addWidget(chk)
        row2.addStretch()
        top_lay.addLayout(row2)

        # Row 3: Folder + Settings
        row3 = QHBoxLayout()
        self.btn_folder = QPushButton("📂 Chọn Folder SRT")
        self.btn_folder.clicked.connect(self._select_folder)
        row3.addWidget(self.btn_folder)
        self.btn_recent = QPushButton("📋 Recent Projects")
        self.btn_recent.clicked.connect(self._open_recent_project)
        row3.addWidget(self.btn_recent)
        self.btn_settings = QPushButton("⚙️ Cài đặt")
        self.btn_settings.clicked.connect(self._open_settings)
        row3.addWidget(self.btn_settings)
        self.lbl_info = QLabel("Chưa chọn folder")
        row3.addWidget(self.lbl_info, 1)
        top_lay.addLayout(row3)

        root.addWidget(top_group)

        # ═══════════ MAIN TABS ═══════════
        self.main_tabs = QTabWidget()
        self.main_tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #ccc; border-top: 2px solid #0078D7; }
            QTabBar::tab {
                background: #E8E8E8; border: 1px solid #ccc; border-bottom: none;
                padding: 8px 18px; margin-right: 2px; border-top-left-radius: 4px; border-top-right-radius: 4px;
                font-size: 13px; min-width: 120px;
            }
            QTabBar::tab:selected {
                background: white; border-bottom: 2px solid white; font-weight: bold; color: #0078D7;
            }
            QTabBar::tab:hover:!selected { background: #D0E8FF; }
        """)
        root.addWidget(self.main_tabs, 1)

        self._build_tab_analysis()
        self._build_tab_translate()
        self._build_tab_qc()
        self._build_tab_prompts()

    # ─────────── TAB 1: PHÂN TÍCH PHIM ───────────

    def _build_tab_analysis(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # Control row
        ctrl = QHBoxLayout()
        self.btn_analyze = QPushButton("🔍 Phân tích Phim (gộp tất cả SRT)")
        self.btn_analyze.setMinimumHeight(36)
        self.btn_analyze.setStyleSheet("QPushButton { background-color: #0078D7; color: white; font-weight: bold; padding: 6px 20px; border-radius: 4px; } QPushButton:hover { background-color: #005A9E; } QPushButton:disabled { background-color: #999; }")
        self.btn_analyze.clicked.connect(self._start_analysis)
        ctrl.addWidget(self.btn_analyze)

        self.btn_load_profile = QPushButton("📂 Load Profile đã có")
        self.btn_load_profile.setMinimumHeight(36)
        self.btn_load_profile.clicked.connect(self._load_existing_profile)
        ctrl.addWidget(self.btn_load_profile)

        ctrl.addStretch()

        # Spinner for analysis
        self.spinner_analysis = WaitingSpinner(self, center_on_parent=False, roundness=70.0, fade=70.0, lines=12, line_length=8, line_width=3, radius=8, speed=1.2, color=QColor(0, 120, 215))
        ctrl.addWidget(self.spinner_analysis)

        self.lbl_profile_status = QLabel("")
        ctrl.addWidget(self.lbl_profile_status)
        lay.addLayout(ctrl)

        # Splitter: Left (profile editor) | Right (stream viewer)
        splitter = QSplitter(Qt.Horizontal)

        # Left: Profile editor
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)
        left_lay.addWidget(QLabel("📋 Profile Nhân vật & Tóm tắt phim (có thể chỉnh sửa):"))
        self.profile_editor = QPlainTextEdit()
        self.profile_editor.setPlaceholderText("Profile nhân vật sẽ hiển thị ở đây sau khi phân tích...\nHoặc bạn có thể paste/edit thủ công.")
        left_lay.addWidget(self.profile_editor, 1)
        btn_row = QHBoxLayout()
        btn_save_profile = QPushButton("💾 Lưu Profile")
        btn_save_profile.clicked.connect(self._save_profile_manual)
        btn_row.addStretch()
        btn_row.addWidget(btn_save_profile)
        left_lay.addLayout(btn_row)
        splitter.addWidget(left_w)

        # Right: Analysis stream viewer
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)
        self.analysis_stream_label = QLabel("📡 Response Phân tích (real-time)")
        right_lay.addWidget(self.analysis_stream_label)
        self.analysis_stream_viewer = QPlainTextEdit()
        self.analysis_stream_viewer.setReadOnly(True)
        self.analysis_stream_viewer.setPlaceholderText("Response từ API sẽ hiển thị ở đây theo thời gian thực khi phân tích...")
        right_lay.addWidget(self.analysis_stream_viewer, 1)
        splitter.addWidget(right_w)

        splitter.setSizes([500, 500])
        lay.addWidget(splitter, 1)

        self.main_tabs.addTab(tab, "🔍 Phân tích Phim")

    # ─────────── TAB 2: DỊCH & TIẾN ĐỘ ───────────

    def _build_tab_translate(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # Control row
        ctrl = QHBoxLayout()
        self.btn_translate_all = QPushButton("🚀 Dịch tất cả")
        self.btn_translate_all.setMinimumHeight(36)
        self.btn_translate_all.setStyleSheet("QPushButton { background-color: #0078D7; color: white; font-weight: bold; padding: 6px 20px; border-radius: 4px; } QPushButton:hover { background-color: #005A9E; } QPushButton:disabled { background-color: #999; }")
        self.btn_translate_all.clicked.connect(self._start_translate_all)
        ctrl.addWidget(self.btn_translate_all)

        self.btn_stop = QPushButton("🛑 Dừng")
        self.btn_stop.setMinimumHeight(36)
        self.btn_stop.setStyleSheet("QPushButton { background-color: #D83B01; color: white; font-weight: bold; padding: 6px 14px; border-radius: 4px; } QPushButton:hover { background-color: #B33000; } QPushButton:disabled { background-color: #999; }")
        self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(self._stop_worker)
        ctrl.addWidget(self.btn_stop)

        self.chk_skip_existing = QCheckBox("Bỏ qua file đã dịch")
        self.chk_skip_existing.setChecked(True)
        ctrl.addWidget(self.chk_skip_existing)

        ctrl.addStretch()

        # Spinner for translate
        self.spinner_translate = WaitingSpinner(self, center_on_parent=False, roundness=70.0, fade=70.0, lines=12, line_length=8, line_width=3, radius=8, speed=1.2, color=QColor(0, 120, 215))
        ctrl.addWidget(self.spinner_translate)

        self.lbl_progress = QLabel("")
        ctrl.addWidget(self.lbl_progress)
        lay.addLayout(ctrl)

        # Splitter: Left (table+log) | Right (stream)
        h_splitter = QSplitter(Qt.Horizontal)

        # Left
        left_splitter = QSplitter(Qt.Vertical)

        self.translate_table = QTableWidget(0, 3)
        self.translate_table.setHorizontalHeaderLabels(["File SRT", "Trạng thái", "Câu"])
        hdr = self.translate_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Stretch)
        hdr.setSectionResizeMode(1, QHeaderView.Fixed)
        hdr.setSectionResizeMode(2, QHeaderView.Fixed)
        self.translate_table.setColumnWidth(1, 180)
        self.translate_table.setColumnWidth(2, 80)
        self.translate_table.verticalHeader().setVisible(False)
        self.translate_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.translate_table.setEditTriggers(QTableWidget.NoEditTriggers)
        left_splitter.addWidget(self.translate_table)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setPlaceholderText("Log xử lý...")
        left_splitter.addWidget(self.log_box)
        left_splitter.setSizes([250, 250])

        h_splitter.addWidget(left_splitter)

        # Right: Stream viewer
        self.stream_panel = QWidget()
        stream_lay = QVBoxLayout(self.stream_panel)
        stream_lay.setContentsMargins(0, 0, 0, 0)
        self.stream_label = QLabel("📡 Response real-time")
        stream_lay.addWidget(self.stream_label)
        self.stream_viewer = QPlainTextEdit()
        self.stream_viewer.setReadOnly(True)
        self.stream_viewer.setPlaceholderText("Response API real-time...")
        stream_lay.addWidget(self.stream_viewer, 1)
        h_splitter.addWidget(self.stream_panel)
        h_splitter.setSizes([550, 400])

        self.stream_panel.setVisible(self.chk_stream.isChecked())
        self.chk_stream.toggled.connect(self.stream_panel.setVisible)

        lay.addWidget(h_splitter, 1)
        self.main_tabs.addTab(tab, "📋 Dịch & Tiến độ")

    # ─────────── TAB 3: QC SONG NGỮ ───────────

    def _build_tab_qc(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.setSpacing(6)

        # Top: Action buttons + navigation
        top_row = QHBoxLayout()

        self.btn_qc_prev = QPushButton("◀ Prev")
        self.btn_qc_prev.setMinimumHeight(32)
        self.btn_qc_prev.clicked.connect(self._qc_prev_srt)
        top_row.addWidget(self.btn_qc_prev)

        self.btn_qc_next = QPushButton("Next ▶")
        self.btn_qc_next.setMinimumHeight(32)
        self.btn_qc_next.clicked.connect(self._qc_next_srt)
        top_row.addWidget(self.btn_qc_next)

        top_row.addSpacing(12)

        self.btn_qc_retranslate_selected = QPushButton("🔄 Dịch lại đoạn chọn")
        self.btn_qc_retranslate_selected.setMinimumHeight(32)
        self.btn_qc_retranslate_selected.setStyleSheet("QPushButton { background-color: #E67E22; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px; }")
        self.btn_qc_retranslate_selected.clicked.connect(self._qc_retranslate_selected)
        top_row.addWidget(self.btn_qc_retranslate_selected)

        self.btn_qc_retranslate_all = QPushButton("🔄 Dịch lại toàn bộ")
        self.btn_qc_retranslate_all.setMinimumHeight(32)
        self.btn_qc_retranslate_all.setStyleSheet("QPushButton { background-color: #D83B01; color: white; font-weight: bold; padding: 4px 12px; border-radius: 4px; }")
        self.btn_qc_retranslate_all.clicked.connect(self._qc_retranslate_all)
        top_row.addWidget(self.btn_qc_retranslate_all)

        self.btn_qc_save = QPushButton("💾 Lưu")
        self.btn_qc_save.setMinimumHeight(32)
        self.btn_qc_save.clicked.connect(self._qc_save_edits)
        top_row.addWidget(self.btn_qc_save)

        top_row.addStretch()
        lay.addLayout(top_row)

        # Splitter: Left (SRT file list) | Right (QC table)
        qc_splitter = QSplitter(Qt.Horizontal)

        # Left: SRT file list with status
        left_w = QWidget()
        left_lay = QVBoxLayout(left_w)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.setSpacing(4)

        self.lbl_qc_file_count = QLabel("📂 Danh sách SRT")
        left_lay.addWidget(self.lbl_qc_file_count)

        self.qc_file_list = QListWidget()
        self.qc_file_list.setMinimumWidth(160)
        self.qc_file_list.currentItemChanged.connect(self._qc_file_selected)
        self.qc_file_list.setStyleSheet("""
            QListWidget::item { padding: 4px 6px; }
            QListWidget::item:selected { background-color: #0078D7; color: white; }
            QListWidget::item:hover:!selected { background-color: #E8F0FE; }
        """)
        left_lay.addWidget(self.qc_file_list, 1)
        qc_splitter.addWidget(left_w)

        # Right: QC table
        right_w = QWidget()
        right_lay = QVBoxLayout(right_w)
        right_lay.setContentsMargins(0, 0, 0, 0)
        right_lay.setSpacing(4)

        self.lbl_qc_current = QLabel("📝 Chọn file SRT bên trái để xem")
        right_lay.addWidget(self.lbl_qc_current)

        self.qc_table = QTableWidget(0, 4)
        self.qc_table.setHorizontalHeaderLabels(["ID", "Câu gốc", "Bản dịch (click đúp để sửa)", "TT"])
        hdr = self.qc_table.horizontalHeader()
        hdr.setSectionResizeMode(0, QHeaderView.Fixed)
        hdr.setSectionResizeMode(1, QHeaderView.Stretch)
        hdr.setSectionResizeMode(2, QHeaderView.Stretch)
        hdr.setSectionResizeMode(3, QHeaderView.Fixed)
        self.qc_table.setColumnWidth(0, 50)
        self.qc_table.setColumnWidth(3, 50)
        self.qc_table.verticalHeader().setVisible(False)
        self.qc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.qc_table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.qc_table.setWordWrap(True)
        self.qc_table.verticalHeader().setDefaultSectionSize(40)
        self.qc_table.cellChanged.connect(self._qc_cell_changed)
        right_lay.addWidget(self.qc_table, 1)

        # Status bar
        self.lbl_qc_status = QLabel("")
        right_lay.addWidget(self.lbl_qc_status)

        qc_splitter.addWidget(right_w)
        qc_splitter.setSizes([180, 820])

        lay.addWidget(qc_splitter, 1)

        self.main_tabs.addTab(tab, "📝 QC Song ngữ")

    # ─────────── TAB 4: CẤU HÌNH PROMPT ───────────

    def _build_tab_prompts(self):
        tab = QWidget()
        lay = QVBoxLayout(tab)
        lay.setContentsMargins(6, 6, 6, 6)

        self.prompt_subtabs = QTabWidget()
        self.prompt_editors: Dict[int, QPlainTextEdit] = {}

        for step in [0, 1, 2]:
            sub_tab = QWidget()
            sub_lay = QVBoxLayout(sub_tab)
            sub_lay.setSpacing(6)

            vars_label = QLabel(STEP_VARIABLES_INFO[step])
            vars_label.setWordWrap(True)
            sub_lay.addWidget(vars_label)

            editor = QPlainTextEdit()
            editor.setPlaceholderText(f"Prompt cho {STEP_TAB_NAMES[step]}...")
            editor.textChanged.connect(self._save_prompt_timer.start)
            sub_lay.addWidget(editor, 1)

            btn_row = QHBoxLayout()
            btn_reset = QPushButton("🔄 Khôi phục mặc định")
            btn_reset.clicked.connect(lambda _, s=step: self._reset_prompt(s))
            btn_row.addWidget(btn_reset)
            btn_row.addStretch()
            sub_lay.addLayout(btn_row)

            self.prompt_editors[step] = editor
            self.prompt_subtabs.addTab(sub_tab, STEP_TAB_NAMES[step])

        lay.addWidget(self.prompt_subtabs)
        self.main_tabs.addTab(tab, "✍️ Cấu hình 3 Prompt")

    # ═══════════ SETTINGS ═══════════

    def _load_settings(self):
        s = self.settings
        self.api_url.setText(s.value("api_url", "http://103.118.29.131:5918/openai/v1/chat/completions"))
        self.api_key.setText(s.value("api_key", "lytamhoan"))
        model = s.value("model", "gemini-pro")
        idx = self.model_combo.findText(model)
        if idx >= 0: self.model_combo.setCurrentIndex(idx)
        else: self.model_combo.setCurrentText(model)

        # Genres
        self._refresh_genres()
        last_genre = s.value("last_genre", "")
        if last_genre: self.genre_combo.setCurrentText(last_genre)

        # Source langs
        self._refresh_source_langs()
        last_src = s.value("last_source", "Tiếng Trung (Chinese)")
        if last_src: self.source_combo.setCurrentText(last_src)

        # Target langs
        saved_targets = s.value("target_langs", ["vi"])
        if isinstance(saved_targets, str):
            try: saved_targets = json.loads(saved_targets)
            except: saved_targets = ["vi"]
        if not isinstance(saved_targets, list): saved_targets = ["vi"]
        for code, chk in self.lang_checks.items():
            chk.setChecked(code in saved_targets)

        # Stream
        saved_stream = s.value("use_stream", True, type=bool)
        self.chk_stream.setChecked(saved_stream)
        self.stream_panel.setVisible(saved_stream)

        # Prompts
        for step in [0, 1, 2]:
            saved = s.value(f"prompt_step_{step}", "")
            if saved and saved.strip():
                self.prompt_editors[step].setPlainText(saved)
            else:
                self.prompt_editors[step].setPlainText(DEFAULT_PROMPTS[step])

        # Last folder
        last_folder = s.value("last_srt_folder", "")
        if last_folder and os.path.isdir(last_folder):
            self._set_folder(last_folder)

    def _save_settings(self):
        s = self.settings
        s.setValue("api_url", self.api_url.text().strip())
        s.setValue("api_key", self.api_key.text().strip())
        s.setValue("model", self.model_combo.currentText().strip())
        s.setValue("last_genre", self.genre_combo.currentText().strip())
        s.setValue("last_source", self.source_combo.currentText().strip())
        s.setValue("use_stream", self.chk_stream.isChecked())
        targets = [code for code, chk in self.lang_checks.items() if chk.isChecked()]
        s.setValue("target_langs", targets)
        s.setValue("last_srt_folder", self.srt_folder)
        self._save_prompts()

        # Save per-project meta
        if self.project_dir:
            self._save_project_meta()

    def _save_prompts(self):
        for step in [0, 1, 2]:
            self.settings.setValue(f"prompt_step_{step}", self.prompt_editors[step].toPlainText())

    def _reset_prompt(self, step: int):
        if QMessageBox.question(self, "Xác nhận", f"Khôi phục prompt mặc định cho {STEP_TAB_NAMES[step]}?") == QMessageBox.Yes:
            self.prompt_editors[step].setPlainText(DEFAULT_PROMPTS[step])

    def _refresh_genres(self):
        cur = self.genre_combo.currentText()
        self.genre_combo.clear()
        saved = self.settings.value("genres", DEFAULT_GENRES)
        if isinstance(saved, str):
            try: saved = json.loads(saved)
            except: saved = DEFAULT_GENRES
        if not isinstance(saved, list): saved = DEFAULT_GENRES
        self.genre_combo.addItems([str(g).strip() for g in saved if str(g).strip()])
        if cur:
            idx = self.genre_combo.findText(cur)
            if idx >= 0: self.genre_combo.setCurrentIndex(idx)

    def _refresh_source_langs(self):
        cur = self.source_combo.currentText()
        self.source_combo.clear()
        saved = self.settings.value("source_langs", DEFAULT_SOURCE_LANGS)
        if isinstance(saved, str):
            try: saved = json.loads(saved)
            except: saved = DEFAULT_SOURCE_LANGS
        if not isinstance(saved, list): saved = DEFAULT_SOURCE_LANGS
        self.source_combo.addItems([str(s).strip() for s in saved if str(s).strip()])
        if cur:
            idx = self.source_combo.findText(cur)
            if idx >= 0: self.source_combo.setCurrentIndex(idx)

    def _open_genre_manager(self):
        dlg = GenreManagerDialog(self)
        if dlg.exec_() == QDialog.Accepted: self._refresh_genres()

    def _open_source_lang_manager(self):
        dlg = SourceLangManagerDialog(self)
        if dlg.exec_() == QDialog.Accepted: self._refresh_source_langs()

    def _open_settings(self):
        SettingsDialog(self).exec_()

    # ═══════════ FOLDER & PROJECT ═══════════

    def _select_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Chọn folder chứa SRT", self.srt_folder or "")
        if folder:
            self._set_folder(folder)

    def _reset_gui(self):
        """Reset all GUI tabs to clean state when switching folder."""
        # --- Tab 1: Phân tích ---
        self.profile_editor.clear()
        self.char_profile = ""
        self.lbl_profile_status.setText("⬜ Chưa phân tích")
        self.analysis_stream_viewer.clear()
        self.analysis_stream_viewer.setPlaceholderText("Response từ API sẽ hiển thị ở đây theo thời gian thực khi phân tích...")

        # --- Tab 2: Dịch ---
        self.translate_table.setRowCount(0)
        self.stream_viewer.clear()
        self.stream_viewer.setPlaceholderText("Response API real-time...")

        # --- Tab 3: QC ---
        self.qc_file_list.clear()
        self.qc_table.setRowCount(0)
        if hasattr(self, 'lbl_qc_file_count'):
            self.lbl_qc_file_count.setText("📂 0 files SRT")

        # --- Log ---
        self.log_box.clear()

    def _set_folder(self, folder: str):
        # Save current project before switching
        if self.project_dir:
            self._save_project_meta()

        # Reset GUI first so user sees clean state
        self._reset_gui()

        self.srt_folder = folder
        self.project_dir = get_project_dir(folder)
        self.srt_files = sorted(
            [f for f in os.listdir(folder) if f.lower().endswith('.srt')],
            key=lambda x: int(re.sub(r'\D', '', os.path.splitext(x)[0]) or 0)
        )
        self.settings.setValue("last_srt_folder", folder)

        # Track in recent projects
        self._add_recent_project(folder)

        # Load project meta (restore genre, lang, etc.)
        meta = load_project_meta(self.project_dir)
        if meta:
            # Restore genre
            genre = meta.get("genre", "")
            if genre:
                idx = self.genre_combo.findText(genre)
                if idx >= 0: self.genre_combo.setCurrentIndex(idx)
            # Restore source lang
            src = meta.get("source_lang", "")
            if src:
                idx = self.source_combo.findText(src)
                if idx >= 0: self.source_combo.setCurrentIndex(idx)
            # Restore target langs
            tgt = meta.get("target_langs", [])
            if tgt:
                for code, chk in self.lang_checks.items():
                    chk.setChecked(code in tgt)
            self.log(f"📂 Đã load project settings từ project.json")
        else:
            # First time — save current settings
            self._save_project_meta()

        # Update info label
        self.lbl_info.setText(f"📂 {folder}  |  {len(self.srt_files)} files SRT  |  Output: {self.project_dir}")

        # Update translate table
        self._refresh_translate_table()

        # Update QC file list
        self._refresh_qc_file_list()

        # Load existing profile
        profile = load_character_profile(self.project_dir)
        if profile:
            self.char_profile = profile
            self.profile_editor.setPlainText(profile)
            self.lbl_profile_status.setText(f"✅ Profile đã có ({len(profile):,} ký tự)")
        else:
            self.lbl_profile_status.setText("⬜ Chưa phân tích")

        self.log(f"📂 Đã chọn folder: {folder} ({len(self.srt_files)} SRT files)")

    def _save_project_meta(self):
        """Save current UI settings to project.json."""
        if not self.project_dir:
            return
        targets = [code for code, chk in self.lang_checks.items() if chk.isChecked()]
        meta = {
            "srt_folder": self.srt_folder,
            "genre": self.genre_combo.currentText().strip(),
            "source_lang": self.source_combo.currentText().strip(),
            "target_langs": targets,
            "total_srt": len(self.srt_files),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_project_meta(self.project_dir, meta)

    def _add_recent_project(self, folder: str):
        """Add folder to recent projects list."""
        recent = self.settings.value("recent_projects", [])
        if isinstance(recent, str):
            try: recent = json.loads(recent)
            except: recent = []
        if not isinstance(recent, list):
            recent = []
        # Remove if exists, add to front
        recent = [f for f in recent if f != folder]
        recent.insert(0, folder)
        recent = recent[:10]  # Keep max 10
        self.settings.setValue("recent_projects", recent)

    def _open_recent_project(self):
        """Show recent projects and switch."""
        recent = self.settings.value("recent_projects", [])
        if isinstance(recent, str):
            try: recent = json.loads(recent)
            except: recent = []
        if not isinstance(recent, list) or not recent:
            QMessageBox.information(self, "Thông báo", "Chưa có project nào!")
            return

        items = []
        for f in recent:
            pdir = get_project_dir(f)
            meta = load_project_meta(pdir)
            name = os.path.basename(f)
            genre = meta.get("genre", "?")
            total = meta.get("total_srt", "?")
            updated = meta.get("updated_at", "?")
            items.append(f"{name}  [{genre}]  {total} SRT  ({updated})")

        item, ok = QInputDialog.getItem(self, "📂 Chọn Project", "Chọn project để mở:", items, 0, False)
        if ok and item:
            idx = items.index(item)
            folder = recent[idx]
            if os.path.isdir(folder):
                self._set_folder(folder)
            else:
                QMessageBox.warning(self, "Lỗi", f"Folder không tồn tại: {folder}")

    def _refresh_translate_table(self):
        self.translate_table.setRowCount(0)
        for srt_file in self.srt_files:
            row = self.translate_table.rowCount()
            self.translate_table.insertRow(row)

            self.translate_table.setItem(row, 0, QTableWidgetItem(srt_file))
            status = get_srt_status(self.project_dir, srt_file) if self.project_dir else "⬜"
            self.translate_table.setItem(row, 1, QTableWidgetItem(status))

            # Count cues
            if self.srt_folder:
                try:
                    subs, _ = read_srt_file(os.path.join(self.srt_folder, srt_file))
                    self.translate_table.setItem(row, 2, QTableWidgetItem(str(len(subs))))
                except Exception:
                    self.translate_table.setItem(row, 2, QTableWidgetItem("?"))

    # ═══════════ LOG ═══════════

    def log(self, text: str):
        self._log_q.put(text)

    def _flush_logs(self):
        while not self._log_q.empty():
            self.log_box.append(self._log_q.get())

    # ═══════════ STREAM ═══════════

    def _on_stream_chunk(self, chunk: str):
        # Route to correct viewer based on active task
        viewer = self.analysis_stream_viewer if self._worker_tab == "analysis" else self.stream_viewer
        cursor = viewer.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(chunk)
        viewer.setTextCursor(cursor)
        viewer.ensureCursorVisible()

    def _on_stream_clear(self, step_name: str):
        if self._worker_tab == "analysis":
            self.analysis_stream_viewer.clear()
            self.analysis_stream_label.setText(f"📡 Response: {step_name}")
        else:
            self.stream_viewer.clear()
            self.stream_label.setText(f"📡 Response: {step_name}")

    # ═══════════ TEST API ═══════════

    def _test_api(self):
        url = self.api_url.text().strip()
        key = self.api_key.text().strip()
        model = self.model_combo.currentText().strip()
        if not url:
            QMessageBox.warning(self, "Lỗi", "Nhập API URL!")
            return

        self.btn_test.setEnabled(False)
        self.btn_test.setText("⏳ Testing...")
        self.log("🧪 Test API...")

        def _do():
            try:
                headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}"}
                payload = {"model": model, "messages": [{"role": "user", "content": "Trả lời 1 từ: OK"}], "stream": False}
                t0 = time.time()
                r = requests.post(url, json=payload, headers=headers, timeout=15)
                elapsed = time.time() - t0
                if r.status_code == 200:
                    reply = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                    self.log(f"✅ API OK ({elapsed:.2f}s) — {reply.strip()}")
                    self.test_api_done_sig.emit(True, f"OK ({elapsed:.2f}s)\n{reply.strip()}")
                else:
                    self.log(f"❌ HTTP {r.status_code}")
                    self.test_api_done_sig.emit(False, f"HTTP {r.status_code}\n{r.text[:300]}")
            except Exception as e:
                self.log(f"❌ {e}")
                self.test_api_done_sig.emit(None, str(e))

        threading.Thread(target=_do, daemon=True).start()

    def _test_done(self, ok, msg):
        self.btn_test.setEnabled(True)
        self.btn_test.setText("🧪 Test API")
        if ok is True:
            QMessageBox.information(self, "OK", msg)
        elif ok is False:
            QMessageBox.warning(self, "Lỗi", msg)
        else:
            QMessageBox.critical(self, "Lỗi", msg)

    # ═══════════ WORKER MANAGEMENT ═══════════

    _worker_tab = "translate"  # tracks which tab the worker is serving

    def _create_worker(self) -> PipelineWorker:
        w = PipelineWorker()
        w.api_url = self.api_url.text().strip()
        w.api_key = self.api_key.text().strip()
        w.model = self.model_combo.currentText().strip()
        w.use_stream = self.chk_stream.isChecked()

        timeout_min = self.settings.value("timeout", 5, type=int)
        w.timeout = timeout_min * 60
        w.max_retries = self.settings.value("retries", 2, type=int)

        for step in [0, 1, 2]:
            w.prompts[step] = self.prompt_editors[step].toPlainText()

        w.log_signal.connect(self.log)
        w.stream_chunk_signal.connect(self._on_stream_chunk)
        w.stream_clear_signal.connect(self._on_stream_clear)
        w.finished_signal.connect(self._on_worker_finished)
        w.srt_status_signal.connect(self._on_srt_status)
        w.translation_done.connect(self._on_translation_done)
        w.progress_signal.connect(self._on_progress)
        w.analysis_done.connect(self._on_analysis_done)

        return w

    def _start_worker(self, task_type: str, task_data: dict):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "Đang chạy", "Đợi task hiện tại hoàn thành!")
            return False

        self._save_settings()
        self._worker_tab = "analysis" if task_type == "analysis" else "translate"
        self.worker = self._create_worker()
        self.worker.task_type = task_type
        self.worker.task_data = task_data

        self.btn_stop.setEnabled(True)
        self.btn_translate_all.setEnabled(False)
        self.btn_analyze.setEnabled(False)

        if self._worker_tab == "analysis":
            self.btn_analyze.setText("⏳ Đang phân tích...")
            self.analysis_stream_viewer.clear()
            self.analysis_stream_label.setText("📡 Đang chờ response...")
            self.lbl_profile_status.setText("")
            self.spinner_analysis.start()
        else:
            self.stream_viewer.clear()
            self.spinner_translate.start()

        self.worker.start()
        return True

    def _stop_worker(self):
        if self.worker:
            self.worker.stop_flag = True
            self.log("🛑 Đang dừng...")

    def _on_worker_finished(self):
        self.btn_stop.setEnabled(False)
        self.btn_translate_all.setEnabled(True)
        self.btn_analyze.setEnabled(True)
        self.btn_analyze.setText("🔍 Phân tích Phim (gộp tất cả SRT)")
        self.spinner_analysis.stop()
        self.spinner_translate.stop()

    def _on_srt_status(self, srt_file: str, status: str):
        for row in range(self.translate_table.rowCount()):
            item = self.translate_table.item(row, 0)
            if item and item.text() == srt_file:
                self.translate_table.setItem(row, 1, QTableWidgetItem(status))
                break
        # Also update QC file list icon
        for i in range(self.qc_file_list.count()):
            item = self.qc_file_list.item(i)
            if item and item.data(Qt.UserRole) == srt_file:
                if "🔄" in status or "Đang" in status:
                    icon = "🔄"
                elif "❌" in status:
                    icon = "❌"
                elif "✅" in status:
                    icon = "✅"
                else:
                    icon = "⬜"
                item.setText(f"{icon} {srt_file}")
                break

    def _on_translation_done(self, srt_file: str, cues: list):
        # Refresh QC table if currently viewing this file
        if self._qc_current_srt() == srt_file:
            self._qc_populate_table(cues)
        # Refresh QC file list status
        self._refresh_qc_file_list_item(srt_file)

    def _on_progress(self, current: int, total: int):
        if total > 0:
            self.lbl_progress.setText(f"📊 {current}/{total}")
        else:
            self.lbl_progress.setText("")

    def _on_analysis_done(self, profile: str):
        self.char_profile = profile
        self.profile_editor.setPlainText(profile)
        self.lbl_profile_status.setText(f"✅ Profile OK ({len(profile):,} ký tự)")

    # ═══════════ ANALYSIS (B0) ═══════════

    def _start_analysis(self):
        if not self.srt_folder:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn folder SRT!")
            return
        if not self.srt_files:
            QMessageBox.warning(self, "Lỗi", "Folder không có file SRT!")
            return

        self._start_worker("analysis", {
            "folder": self.srt_folder,
            "project_dir": self.project_dir,
            "source_lang": self.source_combo.currentText(),
            "target_lang": self._get_target_lang_name(),
            "genre": self.genre_combo.currentText(),
        })

    def _load_existing_profile(self):
        if self.project_dir:
            profile = load_character_profile(self.project_dir)
            if profile:
                self.char_profile = profile
                self.profile_editor.setPlainText(profile)
                self.lbl_profile_status.setText(f"✅ Loaded ({len(profile):,} ký tự)")
                self.log("📂 Đã load profile từ file")
                return

        path, _ = QFileDialog.getOpenFileName(self, "Chọn file profile", "", "Text (*.txt);;All (*)")
        if path:
            with open(path, "r", encoding="utf-8") as f:
                profile = f.read()
            self.char_profile = profile
            self.profile_editor.setPlainText(profile)
            if self.project_dir:
                save_character_profile(self.project_dir, profile)
            self.lbl_profile_status.setText(f"✅ Loaded ({len(profile):,} ký tự)")
            self.log(f"📂 Đã load profile từ: {path}")

    def _save_profile_manual(self):
        text = self.profile_editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Lỗi", "Profile trống!")
            return
        self.char_profile = text
        if self.project_dir:
            save_character_profile(self.project_dir, text)
            self.lbl_profile_status.setText(f"💾 Đã lưu ({len(text):,} ký tự)")
            self.log("💾 Đã lưu profile nhân vật")
        else:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn folder SRT!")

    # ═══════════ TRANSLATE ALL ═══════════

    def _start_translate_all(self):
        if not self.srt_folder or not self.srt_files:
            QMessageBox.warning(self, "Lỗi", "Chưa chọn folder SRT!")
            return

        profile = self.profile_editor.toPlainText().strip()
        if not profile:
            QMessageBox.warning(self, "Lỗi", "Chưa có profile nhân vật! Hãy chạy Phân tích Phim trước.")
            return

        self.char_profile = profile

        self._start_worker("translate_all", {
            "folder": self.srt_folder,
            "project_dir": self.project_dir,
            "srt_files": self.srt_files,
            "profile": profile,
            "source_lang": self.source_combo.currentText(),
            "target_lang": self._get_target_lang_name(),
            "genre": self.genre_combo.currentText(),
            "skip_existing": self.chk_skip_existing.isChecked(),
        })

    def _get_target_lang_name(self) -> str:
        for code, chk in self.lang_checks.items():
            if chk.isChecked():
                return LANG_MAP.get(code, code)
        return "Tiếng Việt"

    # ═══════════ QC TAB ═══════════

    def _qc_current_srt(self) -> str:
        """Get currently selected SRT filename from QC file list."""
        item = self.qc_file_list.currentItem()
        if item:
            # Item text format: "✅ 1.srt" — extract filename after status icon
            text = item.data(Qt.UserRole) or item.text()
            return text
        return ""

    def _refresh_qc_file_list(self):
        """Rebuild the entire QC file list with status icons."""
        self.qc_file_list.blockSignals(True)
        current_srt = self._qc_current_srt()
        self.qc_file_list.clear()

        select_idx = -1
        for i, srt_file in enumerate(self.srt_files):
            status = get_srt_status(self.project_dir, srt_file) if self.project_dir else "⬜"
            icon = "✅" if "✅" in status else ("✏️" if "✏️" in status else "⬜")
            item_text = f"{icon} {srt_file}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, srt_file)  # Store clean filename
            self.qc_file_list.addItem(item)
            if srt_file == current_srt:
                select_idx = i

        if select_idx >= 0:
            self.qc_file_list.setCurrentRow(select_idx)

        self.qc_file_list.blockSignals(False)
        self.lbl_qc_file_count.setText(f"📂 {len(self.srt_files)} files SRT")

    def _refresh_qc_file_list_item(self, srt_file: str):
        """Update just one item in the QC file list (faster than full refresh)."""
        for i in range(self.qc_file_list.count()):
            item = self.qc_file_list.item(i)
            if item and item.data(Qt.UserRole) == srt_file:
                status = get_srt_status(self.project_dir, srt_file)
                icon = "✅" if "✅" in status else ("✏️" if "✏️" in status else "⬜")
                item.setText(f"{icon} {srt_file}")
                break

    def _qc_file_selected(self, current, previous):
        """Called when user clicks a file in the QC list."""
        if not current:
            return
        srt_file = current.data(Qt.UserRole) or current.text()
        self._qc_load_srt(srt_file)

    def _qc_prev_srt(self):
        """Navigate to previous SRT in list."""
        row = self.qc_file_list.currentRow()
        if row > 0:
            self.qc_file_list.setCurrentRow(row - 1)

    def _qc_next_srt(self):
        """Navigate to next SRT in list."""
        row = self.qc_file_list.currentRow()
        if row < self.qc_file_list.count() - 1:
            self.qc_file_list.setCurrentRow(row + 1)

    def _qc_load_srt(self, srt_file: str):
        if not srt_file or not self.project_dir:
            return
        self.lbl_qc_current.setText(f"📝 {srt_file}")
        cues = load_translation(self.project_dir, srt_file)
        if not cues:
            self.qc_table.setRowCount(0)
            self.lbl_qc_status.setText(f"⬜ {srt_file}: chưa có bản dịch")
            return
        self._qc_populate_table(cues)

    def _qc_populate_table(self, cues: list):
        self.qc_table.blockSignals(True)
        self.qc_table.setRowCount(0)

        for cue in cues:
            row = self.qc_table.rowCount()
            self.qc_table.insertRow(row)

            # ID (read-only)
            id_item = QTableWidgetItem(str(cue.get("id", "")))
            id_item.setFlags(id_item.flags() & ~Qt.ItemIsEditable)
            self.qc_table.setItem(row, 0, id_item)

            # Original (read-only)
            orig_item = QTableWidgetItem(cue.get("original", ""))
            orig_item.setFlags(orig_item.flags() & ~Qt.ItemIsEditable)
            orig_item.setBackground(QColor(245, 245, 245))
            self.qc_table.setItem(row, 1, orig_item)

            # Translation (EDITABLE)
            trans_item = QTableWidgetItem(cue.get("text", ""))
            self.qc_table.setItem(row, 2, trans_item)

            # Status (read-only)
            edited = cue.get("edited", False)
            status_item = QTableWidgetItem("✏️" if edited else "✅")
            status_item.setFlags(status_item.flags() & ~Qt.ItemIsEditable)
            status_item.setTextAlignment(Qt.AlignCenter)
            self.qc_table.setItem(row, 3, status_item)

        self.qc_table.blockSignals(False)
        self.qc_table.scrollToTop()

        total = len(cues)
        translated = sum(1 for c in cues if c.get("text", "").strip())
        edited = sum(1 for c in cues if c.get("edited", False))
        srt = self._qc_current_srt()
        self.lbl_qc_status.setText(f"📝 {srt}: {translated}/{total} câu dịch  |  {edited} đã sửa thủ công")

    def _qc_cell_changed(self, row: int, col: int):
        if col != 2:
            return
        status_item = self.qc_table.item(row, 3)
        if status_item:
            status_item.setText("✏️")

    def _qc_save_edits(self):
        srt_file = self._qc_current_srt()
        if not srt_file or not self.project_dir:
            return

        cues = []
        for row in range(self.qc_table.rowCount()):
            id_item = self.qc_table.item(row, 0)
            orig_item = self.qc_table.item(row, 1)
            trans_item = self.qc_table.item(row, 2)
            status_item = self.qc_table.item(row, 3)

            cues.append({
                "id": int(id_item.text()) if id_item else 0,
                "original": orig_item.text() if orig_item else "",
                "text": trans_item.text() if trans_item else "",
                "edited": (status_item.text() == "✏️") if status_item else False,
            })

        save_translation(self.project_dir, srt_file, cues)
        self.log(f"💾 Đã lưu chỉnh sửa QC: {srt_file} ({len(cues)} cue)")

        # Auto re-export SRT with edits
        export_srt_file(self.srt_folder, self.project_dir, srt_file, self.log)

        self.lbl_qc_status.setText(f"💾 Đã lưu & xuất SRT: {srt_file}")

        # Refresh status
        self._refresh_qc_file_list_item(srt_file)
        status = get_srt_status(self.project_dir, srt_file)
        self._on_srt_status(srt_file, status)

    def _qc_retranslate_selected(self):
        selected_rows = set(idx.row() for idx in self.qc_table.selectedIndexes())
        if not selected_rows:
            QMessageBox.information(self, "Thông báo", "Chọn các dòng cần dịch lại!")
            return

        cue_ids = []
        for row in selected_rows:
            id_item = self.qc_table.item(row, 0)
            if id_item:
                cue_ids.append(int(id_item.text()))

        if not cue_ids:
            return

        srt_file = self._qc_current_srt()
        profile = self.profile_editor.toPlainText().strip()
        if not profile:
            QMessageBox.warning(self, "Lỗi", "Chưa có profile nhân vật!")
            return

        self.log(f"🔄 Dịch lại {len(cue_ids)} cue từ {srt_file}: {cue_ids}")
        self._qc_save_edits()

        self._start_worker("retranslate_range", {
            "folder": self.srt_folder,
            "project_dir": self.project_dir,
            "srt_file": srt_file,
            "cue_ids": cue_ids,
            "profile": profile,
            "source_lang": self.source_combo.currentText(),
            "target_lang": self._get_target_lang_name(),
            "genre": self.genre_combo.currentText(),
        })

    def _qc_retranslate_all(self):
        srt_file = self._qc_current_srt()
        if not srt_file:
            return

        reply = QMessageBox.question(self, "Xác nhận",
            f"Dịch lại TOÀN BỘ {srt_file}?\n(Bản dịch hiện tại sẽ bị ghi đè)")
        if reply != QMessageBox.Yes:
            return

        profile = self.profile_editor.toPlainText().strip()
        if not profile:
            QMessageBox.warning(self, "Lỗi", "Chưa có profile nhân vật!")
            return

        self._start_worker("translate_one", {
            "folder": self.srt_folder,
            "project_dir": self.project_dir,
            "srt_file": srt_file,
            "profile": profile,
            "source_lang": self.source_combo.currentText(),
            "target_lang": self._get_target_lang_name(),
            "genre": self.genre_combo.currentText(),
        })

    # ═══════════ CLOSE ═══════════

    def closeEvent(self, event):
        self._save_settings()
        if self.worker and self.worker.isRunning():
            self.worker.stop_flag = True
            self.worker.wait(3000)
        super().closeEvent(event)


# ===================== MAIN =====================

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MainWindow()
    w.show()
    sys.exit(app.exec_())
