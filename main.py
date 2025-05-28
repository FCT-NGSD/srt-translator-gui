import os
import json
import flet as ft # type: ignore
from pathlib import Path
import pysrt # pysrtライブラリをインポート

# --- アプリケーション設定 ---
APP_NAME = "SRTTranslator"

# --- 設定ファイルのパス設定 ---
if os.name == "nt":  # Windows
    CONFIG_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
else:  # macOS, Linux (Codespacesはこちら)
    CONFIG_DIR = Path.home() / ".config" / APP_NAME

CONFIG_DIR.mkdir(parents=True, exist_ok=True) # 設定ディレクトリがなければ作成
CONFIG_PATH = CONFIG_DIR / "config.json"

# --- 設定ファイルの読み込み関数 ---
def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # 設定ファイルが壊れている場合はデフォルト値を返す
            return {"deepl_api_key": ""}
    return {"deepl_api_key": ""} # 設定ファイルがなければデフォルト値を返す

# --- 設定ファイルの保存関数 ---
def save_config(config_data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

# --- メインアプリケーションロジック ---
def main(page: ft.Page): # 'page' はここで引数として受け取ります
    page.title = "SRT Translator"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE # スクロールを有効に

    # --- 初期設定読み込み ---
    config = load_config()

    # --- APIキー関連のUIコントロール定義 ---
    api_key_field = ft.TextField(
        label="DeepL API Key",
        value=config.get("deepl_api_key", ""),
        password=True,
        can_reveal_password=True,
        width=400
    )

    # APIキー保存ボタンのコールバック関数
    def save_api_key_clicked(e):
        config["deepl_api_key"] = api_key_field.value # 'api_key_field' を使用
        save_config(config)
        page.snack_bar = ft.SnackBar( # 'page' を使用
            ft.Text("APIキーを保存しました。"),
            open=True
        )
        page.update() # 'page' を使用

    save_api_key_button = ft.ElevatedButton(
        text="APIキーを保存 (Save API Key)",
        on_click=save_api_key_clicked
    )

    # --- SRTファイル処理関連のUIコントロール定義 ---
    selected_srt_path = ft.Text("ファイルが選択されていません。")
    srt_parse_results_display = ft.Text("") # 解析結果表示用

    # ファイル選択ダイアログのコールバック関数
    def on_file_selected(e: ft.FilePickerResultEvent):
        selected_srt_path.value = "" # 表示を初期化: 'selected_srt_path' を使用
        selected_srt_path.error_text = None
        srt_parse_results_display.value = "" # 解析結果表示も初期化: 'srt_parse_results_display' を使用

        print(f"DEBUG: FilePickerResultEvent received. e.files: {e.files}")
        if e.files and len(e.files) > 0:
            file_obj = e.files[0]
            print(f"DEBUG: file_obj attributes:")
            print(f"  name: {getattr(file_obj, 'name', 'N/A')}")
            print(f"  path: {getattr(file_obj, 'path', 'N/A')}")
            print(f"  size: {getattr(file_obj, 'size', 'N/A')}")

            file_path_str = file_obj.path

            if file_path_str is None:
                selected_srt_path.value = "ファイルパスが取得できませんでした (e.files[0].path is None)."
                print("ERROR: file_path_str is None after selecting a file.")
            else:
                selected_srt_path.value = f"選択ファイル (サーバーパス試行): {file_path_str}"
                try:
                    file_path_obj = Path(file_path_str)
                    with open(file_path_obj, "r", encoding="utf-8") as f:
                        srt_content = f.read()

                    try:
                        subs = pysrt.from_string(srt_content)
                        srt_parse_results_display.value = f"字幕数: {len(subs)}件\n--- 最初の3件の字幕 (確認用) ---"
                        for i, sub_item in enumerate(subs[:3]):
                            srt_parse_results_display.value += f"\n{i+1}: {sub_item.start} --> {sub_item.end}\n{sub_item.text[:30]}..."
                        print(f"SRT parsed successfully. Found {len(subs)} subtitles.")
                    except Exception as parse_err:
                        selected_srt_path.error_text = f"SRT解析エラー: {parse_err}"
                        srt_parse_results_display.value = ""
                        print(f"SRT parsing error: {parse_err}")
                except Exception as read_err:
                    selected_srt_path.error_text = f"ファイル読み込みエラー: {read_err} (パス: {file_path_str})"
                    srt_parse_results_display.value = ""
                    print(f"File reading error: {read_err} for path: {file_path_str}")
        else:
            selected_srt_path.value = "ファイル選択がキャンセルされたか、ファイル情報がありません。"
            print("INFO: File selection cancelled or e.files is empty/None.")

        page.update() # 'page' を使用

    # ファイルピッカーの定義とページへの追加
    file_picker = ft.FilePicker(on_result=on_file_selected)
    page.overlay.append(file_picker) # 'page' を使用

    select_srt_button = ft.ElevatedButton(
        "SRTファイルを選択 (Select SRT File)",
        icon=ft.Icons.UPLOAD_FILE, # 大文字 I
        on_click=lambda _: file_picker.pick_files(
            allow_multiple=False,
            allowed_extensions=["srt"]
        )
    )

    # --- ページ全体のレイアウト ---
    page.add( # 'page' を使用
        ft.Column(
            [
                ft.Text("SRT Translator 設定", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("1. DeepL APIキーを入力してください。", size=16),
                api_key_field,         # UIコントロール
                save_api_key_button,   # UIコントロール
                ft.Text(f"設定ファイルパス: {CONFIG_PATH}", size=10, color=ft.Colors.GREY_500), # 大文字 C

                ft.Divider(),

                ft.Text("SRTファイル翻訳", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("2. 翻訳するSRTファイルを選択してください。", size=16),
                select_srt_button,
                selected_srt_path,
                srt_parse_results_display, # UIコントロール
                # Future: 言語選択や翻訳ボタンなどをここに追加
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
            width=600
        )
    )

# --- アプリケーションの起動 ---
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets", port=8080) # 'main' 関数をターゲットとして指定