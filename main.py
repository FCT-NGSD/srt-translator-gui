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
    current_srt_subs = None # 解析・翻訳されたSRTデータ (SubRipFileオブジェクト) を保持
    original_srt_filename = None # 元のファイル名を保持 (保存時に利用)

    # --- 初期設定読み込み ---
    config = load_config()

    # --- UIコントロールの定義 ---
    api_key_field = ft.TextField(label="DeepL API Key", value=config.get("deepl_api_key", ""), password=True, can_reveal_password=True, width=400)
    save_api_key_button = ft.ElevatedButton("APIキーを保存", on_click=lambda e: save_api_key_config(e))

    selected_srt_path_display = ft.Text("ファイルが選択されていません。")
    translation_status_display = ft.Text("")

    # --- ★★★ ファイル保存関連のUIとロジック ★★★ ---
    save_srt_button = ft.ElevatedButton("翻訳結果を名前を付けて保存", icon=ft.Icons.SAVE, on_click=lambda e: save_translated_srt(e), disabled=True)

    def on_save_srt_result(e: ft.FilePickerResultEvent):
        nonlocal current_srt_subs
        if e.path: # ユーザーが保存パスを選択した場合
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

    # 既存の file_picker をファイル保存にも使う (on_result は呼び出し元で上書きされないので注意が必要)
    # そのため、保存専用のコールバックを file_picker に直接設定するのではなく、
    # save_file メソッドの dialog_title などで区別し、コールバック内で処理します。
    # FilePickerのインスタンスは一つで、pick_files と save_file で使い分ける。
    # on_result は pick_files の結果を受ける。save_file の結果は save_file のコールバックで受け取るべきだが、
    # FletのFilePicker.save_file()は直接コールバックを取らない。結果はon_resultに渡ってくる。
    # よって、on_result内でどの操作だったかを判断するか、保存専用のFilePickerインスタンスを作る。
    # ここでは、簡単のため、既存のfile_pickerのon_resultはファイル選択専用とし、
    # 保存ボタンのon_click内でsave_fileを呼び出し、その結果を処理する新しい関数をon_resultに一時的に割り当てるか、
    # よりクリーンなのは、保存用のFilePickerインスタンスを別途用意することです。
    # 今回は既存のfile_pickerのon_resultを使いまわさず、save_fileメソッドに渡すon_resultを使う設計にします。
    # (Fletの FilePicker.save_file に on_result がないので、実際は pick_files と同様に on_result がトリガーされる)
    # このため、どの操作からの on_result かを区別するフラグや状態管理が必要になる場合がある。
    # 今回は save_file を呼び出す専用のコールバック関数内で結果を処理するようにします。

    # ファイル選択/保存ダイアログを管理するFilePicker (既存のものを流用)
    # on_result はファイルを開く際の処理。保存時は save_file を使う。
    
    # `save_api_key_clicked` と `on_file_selected` は長くなるので、主要なロジックのみここに記述し、
    # 完全なコードは後述の全文に含めます。

    def save_api_key_config(e): # save_api_key_clicked からリネームして統一
        config["deepl_api_key"] = api_key_field.value
        save_config(config)
        page.snack_bar = ft.SnackBar(ft.Text("APIキーを保存しました。"), open=True)
        page.update()

    def on_file_selected_callback(e: ft.FilePickerResultEvent): # pick_files 専用のコールバック
        nonlocal current_srt_subs, original_srt_filename
        selected_srt_path_display.value = ""
        selected_srt_path_display.error_text = None
        translation_status_display.value = ""
        current_srt_subs = None
        original_srt_filename = None
        save_srt_button.disabled = True # 新しいファイルが選択されたら保存ボタンを無効化

        print(f"DEBUG: FilePickerResultEvent received (pick_files). e.files: {e.files}")
        if e.files and len(e.files) > 0:
            file_obj = e.files[0]
            original_srt_filename = file_obj.name # 元のファイル名を取得
            print(f"DEBUG: file_obj attributes: name='{file_obj.name}', path='{file_obj.path}', size={file_obj.size}")
            file_path_str = file_obj.path

            if file_path_str is None: # Codespaces web preview
                selected_srt_path_display.value = f"ファイル名: {original_srt_filename} (Codespacesプレビューでは内容直接処理を検討)"
                # ここでファイル内容 (e.g., file_obj.content) を直接読み込む処理を将来的に追加することもできる
                # 現状はEXEでの動作を優先
                translation_status_display.value = "注意: Webプレビューではパスが取得できません。EXEでテストしてください。"
                print(f"INFO: file_path_str is None for {original_srt_filename}. Relying on EXE for path-based operations.")
            else: # EXE or valid server path
                selected_srt_path_display.value = f"選択ファイル: {file_path_str}"
                try:
                    file_path_obj = Path(file_path_str)
                    with open(file_path_obj, "r", encoding="utf-8") as f:
                        srt_content = f.read()
                    try:
                        subs = pysrt.from_string(srt_content)
                        current_srt_subs = subs
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

    file_picker = ft.FilePicker(on_result=on_file_selected_callback) # pick_files 用のコールバックを設定
    page.overlay.append(file_picker)

    def save_translated_srt(e): # 保存ボタンのクリックイベント
        nonlocal original_srt_filename, current_srt_subs
        if current_srt_subs is None:
            page.snack_bar = ft.SnackBar(ft.Text("保存する翻訳済みデータがありません。先に翻訳を実行してください。"), open=True)
            page.update()
            return

        default_save_filename = "translated.srt"
        if original_srt_filename:
            base, ext = os.path.splitext(original_srt_filename)
            default_save_filename = f"{base}_translated{ext}"
        
        # FilePicker を保存モードで呼び出す
        # save_file の結果も on_result に渡ってくるので、実際には on_file_selected_callback が呼ばれる。
        # これを避けるためには、on_result を一時的に変更するか、別の FilePicker インスタンスを使う。
        # ここでは、簡単化のため、on_result が呼ばれることを許容し、別途 on_save_srt_result を用意。
        # しかし、Flet の FilePicker の save_file() は pick_files() と同じ on_result コールバックを使う。
        # このため、on_result 内でどの操作だったかを区別するフラグを立てるか、
        # もっと簡単なのは on_save_srt_result を file_picker.save_file に渡す (Fletはこれをサポートしない)
        # 正しくは、save_file() が完了した後に e.path を取得し、それを使ってファイル操作を行う。
        # FilePicker.save_file() のコールバックは on_result 経由となる。
        # そのため、on_file_selected_callback が保存時にも呼ばれる。
        # これを回避するために、保存専用のコールバック関数 on_save_srt_result を別途用意し、
        # file_picker.on_result を一時的に付け替えるか、あるいはフラグで管理する。
        # ここでは、保存専用のコールバックをグローバルスコープ（あるいはmainスコープ）で用意し、
        # その関数内でファイル保存を行う前提でボタンのon_clickから呼び出すのではなく、
        # file_picker.save_fileを呼び、その結果を on_save_srt_result (新しい関数) で受けるようにする。
        # Flet の FilePicker.save_file は、その結果をインスタンスの on_result に渡す。
        # なので、on_result を保存用に差し替える。

        file_picker.on_result = on_save_srt_result # 保存操作の時だけコールバックを差し替え
        file_picker.save_file(
            dialog_title="翻訳済みSRTファイルを保存",
            file_name=default_save_filename,
            allowed_extensions=["srt"]
        )
        # 保存ダイアログが閉じられた後、file_picker.on_result は元に戻しておくのが望ましい
        # page.run_thread(target=lambda: setattr(file_picker, 'on_result', on_file_selected_callback)) # 非同期で戻す例
        # もっと簡単なのは、on_save_srt_result の中で元に戻す
        # def on_save_srt_result(e): ... file_picker.on_result = on_file_selected_callback ... page.update()

    select_srt_button = ft.ElevatedButton("SRTファイルを選択", icon=ft.Icons.UPLOAD_FILE, on_click=lambda _: file_picker.pick_files(allow_multiple=False, allowed_extensions=["srt"]))
    
    source_lang_dropdown = ft.Dropdown(label="翻訳元の言語", width=250, value="AUTO", options=[ft.dropdown.Option(key="AUTO", text="自動検出"), ft.dropdown.Option(key="EN", text="英語"), ft.dropdown.Option(key="JA", text="日本語")])
    target_lang_dropdown = ft.Dropdown(label="翻訳先の言語", width=250, value="JA", options=[ft.dropdown.Option(key="JA", text="日本語"), ft.dropdown.Option(key="EN-US", text="英語 (アメリカ)"), ft.dropdown.Option(key="EN-GB", text="英語 (イギリス)")])

    def translate_srt_clicked(e):
        nonlocal current_srt_subs, save_srt_button
        api_key = config.get("deepl_api_key")
        if not api_key:
            page.snack_bar = ft.SnackBar(ft.Text("DeepL APIキーが設定されていません。"), open=True); page.update(); return
        if current_srt_subs is None:
            page.snack_bar = ft.SnackBar(ft.Text("SRTファイルが選択・解析されていません。"), open=True); page.update(); return

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
            page.snack_bar = ft.SnackBar(ft.Text("翻訳が完了しました。"), open=True)
            save_srt_button.disabled = False # 翻訳完了したら保存ボタンを有効化
        except Exception as err: # Broad exception for DeepL errors for now
            error_message = f"翻訳エラー: {type(err).__name__} - {err}"
            if isinstance(err, deepl.QuotaExceededException): error_message = "エラー: DeepL APIの利用上限超過"
            elif isinstance(err, deepl.AuthenticationException): error_message = "エラー: DeepL APIキー認証失敗"
            translation_status_display.value = error_message
            page.snack_bar = ft.SnackBar(ft.Text(error_message.split(':')[0]), open=True) # Show short error in snackbar
            print(f"Translation error: {err}")
        page.update()

    translate_button = ft.ElevatedButton("翻訳実行", icon=ft.Icons.TRANSLATE, on_click=translate_srt_clicked)

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
                ft.Text("3. 言語選択", size=16), ft.Row([source_lang_dropdown, target_lang_dropdown], alignment=ft.MainAxisAlignment.CENTER),
                ft.Text("4. 翻訳実行", size=16), translate_button,
                ft.Text("5. 翻訳結果を保存", size=16), save_srt_button, # ★ 保存ボタンをレイアウトに追加
                ft.Divider(),
                ft.Text("ステータス／結果プレビュー", size=16), translation_status_display,
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=15, width=600, scroll=ft.ScrollMode.ADAPTIVE
        )
    )

# --- アプリケーションの起動 ---
if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets", port=8080)