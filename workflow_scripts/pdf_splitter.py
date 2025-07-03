# workflow_scripts/pdf_splitter.py (更新版)
import google.generativeai as genai
import os
import fitz  # PyMuPDF
import json
import logging
import re
from ai_config import PROMPTS
# 導入新的桌面工具函式
from desktop_utils import get_desktop_path, BASE_OUTPUT_FOLDER_NAME

def sanitize_filename(filename):
    """清理檔案名稱，移除不合法的字元。"""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

def run_pdf_split(api_key: str, model_name: str, input_pdf_path: str, output_folder_name: str, progress_queue=None) -> tuple[int, str | None]:
    """
    使用 AI 分析 PDF 目錄並進行分割。
    返回 (成功分割的檔案數量, 輸出資料夾路徑)。
    """
    logging.info(f"開始智能分割 PDF: {os.path.basename(input_pdf_path)}")
    if progress_queue:
        progress_queue.put(json.dumps({'type': 'status', 'status': '初始化模型...', 'percent': 5}))

    try:
        model = genai.GenerativeModel(model_name)
        pdf_document = fitz.open(input_pdf_path)
        num_pages = len(pdf_document)
    except Exception as e:
        logging.error(f"初始化或開啟 PDF 失敗: {e}")
        if progress_queue: progress_queue.put(json.dumps({'type': 'error', 'message': f'開啟 PDF 失敗: {e}'}))
        return -1, None

    # --- 1. 提取頁面圖片以供 AI 分析 ---
    if progress_queue:
        progress_queue.put(json.dumps({'type': 'status', 'status': '準備分析頁面...', 'percent': 10}))
    
    image_parts = []
    pages_to_analyze = list(range(min(15, num_pages))) + list(range(max(15, num_pages - 5), num_pages))
    pages_to_analyze = sorted(list(set(pages_to_analyze)))

    for page_num in pages_to_analyze:
        page = pdf_document.load_page(page_num)
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        image_parts.append({"mime_type": "image/png", "data": img_bytes})

    # --- 2. 呼叫 AI 分析目錄 ---
    if progress_queue:
        progress_queue.put(json.dumps({'type': 'status', 'status': 'AI 正在分析目錄結構...', 'percent': 25}))
    
    try:
        prompt = PROMPTS["PDF_SPLIT_TOC_ANALYSIS"]
        response = model.generate_content([prompt] + image_parts, generation_config={"response_mime_type": "application/json"})
        toc_data_text = response.text
        toc = json.loads(toc_data_text)
        
        if not toc:
            logging.warning("AI 未能從文件中找到目錄。")
            if progress_queue: progress_queue.put(json.dumps({'type': 'error', 'message': 'AI 未能分析出目錄，無法分割。'}))
            return 0, None

        logging.info(f"AI 分析出的目錄結構: {toc}")
    except (json.JSONDecodeError, TypeError, AttributeError) as e:
        logging.error(f"解析 AI 回應的 JSON 失敗: {e}\n原始回應: {response.text if 'response' in locals() else 'N/A'}")
        if progress_queue: progress_queue.put(json.dumps({'type': 'error', 'message': f'AI 回應格式錯誤: {e}'}))
        return -1, None
    except Exception as e:
        logging.error(f"呼叫 AI 分析目錄時發生錯誤: {e}")
        if progress_queue: progress_queue.put(json.dumps({'type': 'error', 'message': f'AI 分析失敗: {e}'}))
        return -1, None

    # --- 3. 處理頁碼並分割 PDF ---
    if progress_queue:
        progress_queue.put(json.dumps({'type': 'status', 'status': '正在根據目錄進行分割...', 'percent': 70}))

    toc.sort(key=lambda x: x.get('page', float('inf')))
    
    try:
        desktop_path = get_desktop_path()
        base_output_dir = os.path.join(desktop_path, BASE_OUTPUT_FOLDER_NAME)
        original_pdf_name = os.path.splitext(os.path.basename(input_pdf_path))[0]
        final_output_dir = os.path.join(base_output_dir, output_folder_name, original_pdf_name)
        os.makedirs(final_output_dir, exist_ok=True)
    except Exception as e:
        logging.error(f"建立輸出資料夾失敗: {e}")
        if progress_queue: progress_queue.put(json.dumps({'type': 'error', 'message': f'建立桌面資料夾失敗: {e}'}))
        return -1, None
        
    split_count = 0
    for i, item in enumerate(toc):
        try:
            title = sanitize_filename(item['title'])
            start_page_printed = item['page']
            
            start_page_index = start_page_printed - 1

            if start_page_index < 0 or start_page_index >= num_pages:
                logging.warning(f"跳過無效頁碼: 標題 '{title}', 頁碼 {start_page_printed}")
                continue

            if i + 1 < len(toc):
                end_page_printed = toc[i+1]['page']
                end_page_index = end_page_printed - 2
            else:
                end_page_index = num_pages - 1
            
            if end_page_index < start_page_index:
                end_page_index = start_page_index

            split_pdf = fitz.open()
            split_pdf.insert_pdf(pdf_document, from_page=start_page_index, to_page=end_page_index)
            
            output_filename = f"{i+1:02d}_{title}.pdf"
            output_path = os.path.join(final_output_dir, output_filename)
            split_pdf.save(output_path)
            split_pdf.close()
            split_count += 1
            logging.info(f"已儲存分割檔案: {output_filename}")
            
            if progress_queue:
                 progress_queue.put(json.dumps({
                     'type': 'progress', 
                     'current': i + 1, 
                     'total': len(toc),
                     'status': f'已分割: {title}'
                 }))

        except (KeyError, TypeError) as e:
            logging.warning(f"跳過格式錯誤的目錄項目: {item}, 錯誤: {e}")
            continue
        except Exception as e:
            logging.error(f"分割章節 '{item.get('title', 'N/A')}' 時出錯: {e}")
            continue
            
    pdf_document.close()
    return split_count, final_output_dir