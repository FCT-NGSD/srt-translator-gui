import os
import json
import flet as ft # type: ignore
from pathlib import Path
import pysrt # pysrtライブラリ
import deepl # deeplライブラリ

# --- アプリケーション設定 ---
APP_NAME = "SRTTranslator"

# --- 設定ファイルのパス設定 ---
if os.name == "nt":  # Windows
    CONFIG_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
else:  # macOS, Linux (Codespacesはこちら)
    CONFIG_DIR = Path.home() / ".config" / APP_NAME

CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "config.json"

# --- 設定ファイルの読み込み関数 ---
def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {"deepl_api_key": ""}
    return {"deepl_api_key": ""}

# --- 設定ファイルの保存関数 ---
def save_config(config_data):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=4, ensure_ascii=False)

# --- メインアプリケーションロジック ---
def main(page: ft.Page):
    page.title = "SRT Translator"
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.scroll = ft.ScrollMode.ADAPTIVE

    # --- アプリケーション内で状態を保持する変数 ---
    current_srt_subs = None # 解析されたSRTデータ (SubRipFileオブジェクト) を保持

    # --- 初期設定読み込み ---
    config = load_config()

    # --- UIコントロールの定義 ---

    # APIキー関連
    api_key_field = ft.TextField(
        label="DeepL API Key",
        value=config.get("deepl_api_key", ""),
        password=True,
        can_reveal_password=True,
        width=400
    )

    def save_api_key_clicked(e):
        config["deepl_api_key"] = api_key_field.value
        save_config(config)
        page.snack_bar = ft.SnackBar(ft.Text("APIキーを保存しました。"), open=True)
        page.update()

    save_api_key_button = ft.ElevatedButton("APIキーを保存", on_click=save_api_key_clicked)

    # SRTファイル処理関連
    selected_srt_path_display = ft.Text("ファイルが選択されていません。")
    translation_status_display = ft.Text("") # 翻訳結果や進捗を表示

    def on_file_selected(e: ft.FilePickerResultEvent):
        nonlocal current_srt_subs # 外側のmain関数のcurrent_srt_subsを参照・代入する
        selected_srt_path_display.value = ""
        selected_srt_path_display.error_text = None
        translation_status_display.value = "" # 表示をクリア
        current_srt_subs = None # 古いデータをクリア

        print(f"DEBUG: FilePickerResultEvent received. e.files: {e.files}")
        if e.files and len(e.files) > 0:
            file_obj = e.files[0]
            print(f"DEBUG: file_obj attributes: name='{file_obj.name}', path='{file_obj.path}', size={file_obj.size}")
            file_path_str = file_obj.path

            if file_path_str is None:
                selected_srt_path_display.value = "ファイルパスが取得できませんでした (Codespacesプレビュー時の既知の問題の可能性あり)。EXEでテストしてください。"
                print("ERROR: file_path_str is None after selecting a file.")
            else:
                selected_srt_path_display.value = f"選択ファイル: {file_path_str}"
                try:
                    file_path_obj = Path(file_path_str)
                    with open(file_path_obj, "r", encoding="utf-8") as f:
                        srt_content = f.read()
                    try:
                        subs = pysrt.from_string(srt_content)
                        current_srt_subs = subs # 解析結果を保持
                        translation_status_display.value = f"字幕数: {len(subs)}件。翻訳準備完了。"
                        print(f"SRT parsed successfully. Found {len(subs)} subtitles.")
                    except Exception as parse_err:
                        selected_srt_path_display.error_text = f"SRT解析エラー: {parse_err}"
                        print(f"SRT parsing error: {parse_err}")
                except Exception as read_err:
                    selected_srt_path_display.error_text = f"ファイル読み込みエラー: {read_err} (パス: {file_path_str})"
                    print(f"File reading error: {read_err} for path: {file_path_str}")
        else:
            selected_srt_path_display.value = "ファイル選択がキャンセルされたか、ファイル情報がありません。"
            print("INFO: File selection cancelled or e.files is empty/None.")
        page.update()

    file_picker = ft.FilePicker(on_result=on_file_selected)
    page.overlay.append(file_picker)

    select_srt_button = ft.ElevatedButton(
        "SRTファイルを選択",
        icon=ft.Icons.UPLOAD_FILE,
        on_click=lambda _: file_picker.pick_files(allow_multiple=False, allowed_extensions=["srt"])
    )

    # 翻訳言語選択UI
    source_lang_dropdown = ft.Dropdown(
        label="翻訳元の言語", width=250, value="AUTO",
        options=[
            ft.dropdown.Option(key="AUTO", text="自動検出"),
            ft.dropdown.Option(key="EN", text="英語"),
            ft.dropdown.Option(key="JA", text="日本語"),
        ]
    )
    target_lang_dropdown = ft.Dropdown(
        label="翻訳先の言語", width=250, value="JA",
        options=[
            ft.dropdown.Option(key="JA", text="日本語"),
            ft.dropdown.Option(key="EN-US", text="英語 (アメリカ)"),
            ft.dropdown.Option(key="EN-GB", text="英語 (イギリス)"),
        ]
    )

    # 翻訳実行ボタンと処理
    def translate_srt_clicked(e):
        nonlocal current_srt_subs # 外側のmain関数のcurrent_srt_subsを参照
        
        api_key = config.get("deepl_api_key")
        if not api_key:
            page.snack_bar = ft.SnackBar(ft.Text("DeepL APIキーが設定されていません。"), open=True)
            page.update()
            return
        if current_srt_subs is None:
            page.snack_bar = ft.SnackBar(ft.Text("SRTファイルが選択されていないか、解析に失敗しています。"), open=True)
            page.update()
            return

        source_lang_key = source_lang_dropdown.value
        target_lang_key = target_lang_dropdown.value

        if not target_lang_key: # ターゲット言語は必須
            page.snack_bar = ft.SnackBar(ft.Text("翻訳先の言語を選択してください。"), open=True)
            page.update()
            return
        
        # "AUTO" の場合は deepl ライブラリでは None を渡す
        source_lang_for_api = source_lang_key if source_lang_key != "AUTO" else None

        translation_status_display.value = "翻訳中..."
        page.update()

        try:
            translator = deepl.Translator(api_key)
            
            texts_to_translate = [sub.text for sub in current_srt_subs]
            
            # DeepLは一度に複数のテキストを翻訳できる
            # target_lang は 'EN-US' や 'EN-GB' をそのまま使える。'EN' だけだと 'EN-US' になることが多い。
            translated_results = translator.translate_text(
                texts_to_translate,
                source_lang=source_lang_for_api,
                target_lang=target_lang_key
            )
            
            for i, translated_text_obj in enumerate(translated_results):
                current_srt_subs[i].text = translated_text_obj.text
            
            translation_status_display.value = f"翻訳完了！ 字幕数: {len(current_srt_subs)}件。\n--- 最初の3件の翻訳後字幕 (確認用) ---"
            for i, sub in enumerate(current_srt_subs[:3]):
                translation_status_display.value += f"\n{i+1}: {sub.start} --> {sub.end}\n{sub.text[:30]}..."
            page.snack_bar = ft.SnackBar(ft.Text("翻訳が完了しました。"), open=True)

        except deepl.QuotaExceededException:
            translation_status_display.value = "エラー: DeepL APIの利用上限に達しました。"
            page.snack_bar = ft.SnackBar(ft.Text("エラー: DeepL APIの利用上限超過"), open=True)
        except deepl.AuthenticationException:
            translation_status_display.value = "エラー: DeepL APIキーが無効です。"
            page.snack_bar = ft.SnackBar(ft.Text("エラー: DeepL APIキー認証失敗"), open=True)
        except deepl.DeepLException as de_err:
            translation_status_display.value = f"DeepL APIエラー: {de_err}"
            page.snack_bar = ft.SnackBar(ft.Text(f"DeepL APIエラー"), open=True)
        except Exception as err:
            translation_status_display.value = f"翻訳中に予期せぬエラーが発生しました: {err}"
            page.snack_bar = ft.SnackBar(ft.Text("翻訳エラー"), open=True)
            print(f"Unexpected translation error: {err}")
        
        page.update()

    translate_button = ft.ElevatedButton("翻訳実行", icon=ft.Icons.TRANSLATE, on_click=translate_srt_clicked)

    # --- ページ全体のレイアウト ---
    page.add(
        ft.Column(
            [
                ft.Text("SRT Translator 設定", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("1. DeepL APIキー", size=16),
                api_key_field,
                save_api_key_button,
                ft.Text(f"設定ファイルパス: {CONFIG_PATH}", size=10, color=ft.Colors.GREY_500),
                ft.Divider(),
                ft.Text("SRTファイル翻訳処理", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("2. SRTファイル選択", size=16),
                select_srt_button,
                selected_srt_path_display,
                ft.Text("3. 言語選択", size=16),
                ft.Row([source_lang_dropdown, target_lang_dropdown], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("4. 翻訳実行", size=16),
                translate_button,
                ft.Divider(),
                ft.Text("ステータス／結果プレビュー", size=16),
                translation_status_display, # 翻訳ステータスや結果の一部を表示
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=15,
            width=600,
            scroll=ft.ScrollMode.ADAPTIVE # Column自体もスクロール可能に
        )
    )

# --- アプリケーションの起動 ---
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets", port=8080)