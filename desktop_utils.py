# desktop_utils.py

import os
import shutil
import logging
import subprocess
import sys

BASE_OUTPUT_FOLDER_NAME = "AI 工具輸出"

def get_desktop_path():
    """安全地獲取桌面路徑，如果不存在則返回使用者根目錄。"""
    desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
    if not os.path.isdir(desktop_path):
        desktop_path = os.path.expanduser('~')
        logging.warning(f"桌面資料夾 (~/Desktop) 不存在，將使用使用者根目錄: {desktop_path}")
    return desktop_path

def copy_to_desktop_folder(source_path: str, subfolder_name: str, desired_filename: str) -> tuple[str | None, str | None]:
    """
    將檔案複製到桌面「AI 工具輸出」下的指定子資料夾中。
    (注意：現在 subfolder_name 直接是 '翻譯檔案', '摘要檔案' 等)
    """
    if not os.path.exists(source_path):
        logging.error(f"來源檔案不存在，無法複製: {source_path}")
        return None, None

    try:
        desktop_path = get_desktop_path()
        base_output_folder = os.path.join(desktop_path, BASE_OUTPUT_FOLDER_NAME)
        target_folder = os.path.join(base_output_folder, subfolder_name)
        os.makedirs(target_folder, exist_ok=True)

        # 處理檔名衝突
        final_desktop_path = os.path.join(target_folder, desired_filename)
        counter = 1
        name, ext = os.path.splitext(desired_filename)
        while os.path.exists(final_desktop_path):
            final_desktop_path = os.path.join(target_folder, f"{name}_{counter}{ext}")
            counter += 1

        final_display_filename = os.path.basename(final_desktop_path)
        shutil.copy2(source_path, final_desktop_path)
        logging.info(f"成功複製檔案到: {final_desktop_path}")
        return final_desktop_path, final_display_filename
    except Exception as e:
        logging.error(f"複製檔案 '{os.path.basename(source_path)}' 到桌面資料夾 '{subfolder_name}' 失敗: {e}", exc_info=True)
        return None, None

def open_folder_in_explorer(folder_path: str):
    """在作業系統的檔案總管中打開指定資料夾。"""
    if not os.path.isdir(folder_path):
        # 如果路徑不存在，嘗試打開其父目錄
        parent_dir = os.path.dirname(folder_path)
        if os.path.isdir(parent_dir):
            folder_path = parent_dir
        else:
            logging.warning(f"嘗試打開不存在的資料夾及其父目錄: {folder_path}")
            return

    try:
        if sys.platform == "win32":
            os.startfile(os.path.realpath(folder_path))
        elif sys.platform == "darwin": # macOS
            subprocess.Popen(["open", folder_path])
        else: # Linux
            subprocess.Popen(["xdg-open", folder_path])
        logging.info(f"已請求打開資料夾: {folder_path}")
    except Exception as e:
        logging.error(f"無法打開資料夾 '{folder_path}': {e}")