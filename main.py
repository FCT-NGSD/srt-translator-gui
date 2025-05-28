import os
import json
import flet as ft # type: ignore
from pathlib import Path
import pysrt # pysrtライブラリ
import deepl # deeplライブラリ

# --- アプリケーション設定 ---
APP_NAME = "SRTTranslator"
DEEPL_FREE_CHAR_LIMIT = 500000 # ★★★ DeepL Free版の文字数上限 ★★★

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
    current_srt_subs = None
    original_srt_filename = None

    # --- 初期設定読み込み ---
    config = load_config()

    # --- UIコントロールの定義 ---
    api_key_field = ft.TextField(label="DeepL API Key", value=config.get("deepl_api_key", ""), password=True, can_reveal_password=True, width=400)
    
    def save_api_key_config(e):
        config["deepl_api_key"] = api_key_field.value
        save_config(config)
        page.snack_bar = ft.SnackBar(ft.Text("APIキーを保存しました。"), open=True)
        page.update()
    save_api_key_button = ft.ElevatedButton("APIキーを保存", on_click=save_api_key_config)

    selected_srt_path_display = ft.Text("ファイルが選択されていません。")
    translation_status_display = ft.Text("")
    char_count_display = ft.Text("") # ★★★ 文字数表示用のTextコントロールを追加 ★★★

    save_srt_button = ft.ElevatedButton("翻訳結果を名前を付けて保存", icon=ft.Icons.SAVE, on_click=lambda e: save_translated_srt(e), disabled=True)
    translate_button = ft.ElevatedButton("翻訳実行", icon=ft.Icons.TRANSLATE, on_click=lambda e: translate_srt_clicked(e), disabled=True) # ★★★ 初期状態は無効 ★★★


    def on_file_selected_callback(e: ft.FilePickerResultEvent):
        nonlocal current_srt_subs, original_srt_filename
        selected_srt_path_display.value = ""
        selected_srt_path_display.error_text = None
        translation_status_display.value = ""
        char_count_display.value = "" # ★★★ 文字数表示をクリア ★★★
        char_count_display.color = None # ★★★ 文字色をデフォルトに戻す ★★★
        current_srt_subs = None
        original_srt_filename = None
        save_srt_button.disabled = True
        translate_button.disabled = True # ★★★ ファイル選択時に翻訳ボタンを無効化 ★★★

        print(f"DEBUG: FilePickerResultEvent received (pick_files). e.files: {e.files}")
        if e.files and len(e.files) > 0:
            file_obj = e.files[0]
            original_srt_filename = file_obj.name
            print(f"DEBUG: file_obj attributes: name='{file_obj.name}', path='{file_obj.path}', size={file_obj.size}")
            file_path_str = file_obj.path

            if file_path_str is None:
                selected_srt_path_display.value = f"ファイル名: {original_srt_filename} (Codespacesプレビューでは内容直接処理を検討)"
                translation_status_display.value = "注意: Webプレビューではパスが取得できません。EXEでテストしてください。"
                print(f"INFO: file_path_str is None for {original_srt_filename}. Relying on EXE for path-based operations.")
            else:
                selected_srt_path_display.value = f"選択ファイル: {file_path_str}"
                try:
                    file_path_obj = Path(file_path_str)
                    with open(file_path_obj, "r", encoding="utf-8") as f:
                        srt_content = f.read()
                    try:
                        subs = pysrt.from_string(srt_content)
                        current_srt_subs = subs
                        
                        # ★★★ 文字数カウントと制限判定処理 ここから ★★★
                        total_chars = 0
                        if current_srt_subs:
                            for sub_item in current_srt_subs:
                                total_chars += len(sub_item.text)
                        
                        char_count_display.value = f"翻訳対象の総文字数: {total_chars} 文字"
                        
                        if total_chars == 0 and current_srt_subs is not None:
                            char_count_display.value += "\n注意: 翻訳対象のテキストがありません。"
                            char_count_display.color = ft.Colors.ORANGE # 警告色
                            translate_button.disabled = True
                        elif total_chars > DEEPL_FREE_CHAR_LIMIT:
                            char_count_display.value += f"\n警告: 文字数が上限 ({DEEPL_FREE_CHAR_LIMIT}文字) を超えています。翻訳できません。"
                            char_count_display.color = ft.Colors.RED # エラー色
                            translate_button.disabled = True
                            page.snack_bar = ft.SnackBar(
                                ft.Text(f"文字数超過: {total_chars}/{DEEPL_FREE_CHAR_LIMIT}。翻訳実行は無効です。"),
                                open=True
                            )
                        else: # 文字数OK
                            char_count_display.value += f"\n上限 ({DEEPL_FREE_CHAR_LIMIT}文字) 以内です。翻訳可能です。"
                            char_count_display.color = ft.Colors.GREEN # 成功色
                            translate_button.disabled = False # ★★★ 翻訳ボタンを有効化 ★★★
                        # ★★★ 文字数カウントと制限判定処理 ここまで ★★★

                        translation_status_display.value = f"字幕数: {len(subs)}件。上記の文字数を確認してください。"
                        print(f"SRT parsed successfully. Found {len(subs)} subtitles. Total chars: {total_chars}")

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

    # on_save_srt_result (ファイル保存ダイアログの結果処理)
    def on_save_srt_result(e: ft.FilePickerResultEvent):
        nonlocal current_srt_subs
        # 保存ダイアログが閉じられた後、file_pickerのon_resultを元に戻す
        file_picker.on_result = on_file_selected_callback

        if e.path:
            save_file_path = Path(e.path)
            try:
                if current_srt_subs:
                    current_srt_subs.save(str(save_file_path), encoding='utf-8')
                    page.snack_bar = ft.SnackBar(ft.Text(f"翻訳済みファイルを保存しました: {save_file_path}"), open=True)
                    print(f"Translated SRT saved to: {save_file_path}")
                else:
                    page.snack_bar = ft.SnackBar(ft.Text("エラー: 保存する翻訳済みデータがありません。"), open=True)
            except Exception as err:
                page.snack_bar = ft.SnackBar(ft.Text(f"ファイル保存エラー: {err}"), open=True)
                print(f"Error saving file: {err}")
        else:
            page.snack_bar = ft.SnackBar(ft.Text("ファイル保存がキャンセルされました。"), open=True)
        page.update()

    file_picker = ft.FilePicker(on_result=on_file_selected_callback)
    page.overlay.append(file_picker)

    def save_translated_srt(e):
        nonlocal original_srt_filename, current_srt_subs
        if current_srt_subs is None:
            page.snack_bar = ft.SnackBar(ft.Text("保存する翻訳済みデータがありません。"), open=True)
            page.update(); return

        default_save_filename = "translated.srt"
        if original_srt_filename:
            base, ext = os.path.splitext(original_srt_filename)
            default_save_filename = f"{base}_translated{ext}"
        
        file_picker.on_result = on_save_srt_result # ★★★ 保存操作用にコールバックを一時的に差し替え ★★★
        file_picker.save_file(
            dialog_title="翻訳済みSRTファイルを保存",
            file_name=default_save_filename,
            allowed_extensions=["srt"]
        )
        # on_save_srt_result の中で file_picker.on_result は元に戻される

    select_srt_button = ft.ElevatedButton("SRTファイルを選択", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(allow_multiple=False, allowed_extensions=["srt"]))
    
    source_lang_dropdown = ft.Dropdown(label="翻訳元の言語", width=250, value="AUTO", options=[ft.dropdown.Option(key="AUTO", text="自動検出"), ft.dropdown.Option(key="EN", text="英語"), ft.dropdown.Option(key="JA", text="日本語")])
    target_lang_dropdown = ft.Dropdown(label="翻訳先の言語", width=250, value="JA", options=[ft.dropdown.Option(key="JA", text="日本語"), ft.dropdown.Option(key="EN-US", text="英語 (アメリカ)"), ft.dropdown.Option(key="EN-GB", text="英語 (イギリス)")])

    # 翻訳実行ボタンのコールバック
    def translate_srt_clicked(e):
        nonlocal current_srt_subs, save_srt_button
        api_key = config.get("deepl_api_key")
        if not api_key:
            page.snack_bar = ft.SnackBar(ft.Text("DeepL APIキーが設定されていません。"), open=True); page.update(); return
        if current_srt_subs is None:
            page.snack_bar = ft.SnackBar(ft.Text("SRTファイルが選択・解析されていません。"), open=True); page.update(); return

        # ★★★ 文字数再チェック (念のため) ★★★
        total_chars = sum(len(sub.text) for sub in current_srt_subs)
        if total_chars > DEEPL_FREE_CHAR_LIMIT:
            page.snack_bar = ft.SnackBar(ft.Text(f"文字数超過 ({total_chars}/{DEEPL_FREE_CHAR_LIMIT}) のため翻訳できません。"), open=True)
            translate_button.disabled = True # ボタンを再度無効化
            page.update()
            return
        if total_chars == 0:
            page.snack_bar = ft.SnackBar(ft.Text(f"翻訳対象のテキストがありません。"), open=True)
            translate_button.disabled = True # ボタンを再度無効化
            page.update()
            return


        source_lang_key = source_lang_dropdown.value
        target_lang_key = target_lang_dropdown.value
        if not target_lang_key:
            page.snack_bar = ft.SnackBar(ft.Text("翻訳先の言語を選択してください。"), open=True); page.update(); return
        
        source_lang_for_api = source_lang_key if source_lang_key != "AUTO" else None
        translation_status_display.value = "翻訳中..."; save_srt_button.disabled = True; page.update()

        try:
            translator = deepl.Translator(api_key)
            texts_to_translate = [sub.text for sub in current_srt_subs]
            translated_results = translator.translate_text(texts_to_translate, source_lang=source_lang_for_api, target_lang=target_lang_key)
            
            for i, translated_text_obj in enumerate(translated_results):
                current_srt_subs[i].text = translated_text_obj.text
            
            translation_status_display.value = f"翻訳完了！ 字幕数: {len(current_srt_subs)}件。\n--- 最初の3件の翻訳後字幕 (確認用) ---"
            for i, sub in enumerate(current_srt_subs[:3]):
                translation_status_display.value += f"\n{i+1}: {sub.start} --> {sub.end}\n{sub.text[:30]}..."
            page.snack_bar = ft.SnackBar(ft.Text("翻訳が完了しました。保存ボタンで結果を保存できます。"), open=True)
            save_srt_button.disabled = False
        except Exception as err:
            error_message = f"翻訳エラー: {type(err).__name__} - {err}"
            if isinstance(err, deepl.QuotaExceededException): error_message = "エラー: DeepL APIの利用上限超過"
            elif isinstance(err, deepl.AuthenticationException): error_message = "エラー: DeepL APIキー認証失敗"
            translation_status_display.value = error_message
            page.snack_bar = ft.SnackBar(ft.Text(error_message.split(':')[0]), open=True)
            print(f"Translation error: {err}")
        page.update()

    # --- ページ全体のレイアウト ---
    page.add(
        ft.Column(
            [
                ft.Text("SRT Translator 設定", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("1. DeepL APIキー", size=16), api_key_field, save_api_key_button,
                ft.Text(f"設定ファイルパス: {CONFIG_PATH}", size=10, color=ft.Colors.GREY_500),
                ft.Divider(),
                ft.Text("SRTファイル翻訳処理", size=20, weight=ft.FontWeight.BOLD),
                ft.Text("2. SRTファイル選択", size=16), select_srt_button, selected_srt_path_display,
                char_count_display, # ★★★ 文字数表示をレイアウトに追加 ★★★
                ft.Text("3. 言語選択", size=16), ft.Row([source_lang_dropdown, target_lang_dropdown], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("4. 翻訳実行", size=16), translate_button,
                ft.Text("5. 翻訳結果を保存", size=16), save_srt_button,
                ft.Divider(),
                ft.Text("ステータス／結果プレビュー", size=16), translation_status_display,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, width=600, scroll=ft.ScrollMode.ADAPTIVE
        )
    )

# --- アプリケーションの起動 ---
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets", port=8080)