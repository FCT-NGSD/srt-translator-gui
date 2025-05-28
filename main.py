import os
import json
import flet as ft # type: ignore
from pathlib import Path

# Define a user-specific directory for configuration
APP_NAME = "SRTTranslator"

# Determine the appropriate config directory based on OS
if os.name == "nt":  # Windows
    CONFIG_DIR = Path(os.getenv("APPDATA", Path.home() / "AppData" / "Roaming")) / APP_NAME
else:  # macOS, Linux
    CONFIG_DIR = Path.home() / ".config" / APP_NAME

# Ensure the configuration directory exists
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_PATH = CONFIG_DIR / "config.json"

def load_config():
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            # Config file is corrupt, return default
            return {"deepl_api_key": ""}
    return {"deepl_api_key": ""}

def save_config(config):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)

def main(page: ft.Page):
    page.title = "SRT Translator"
    page.vertical_alignment = ft.MainAxisAlignment.CENTER
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER

    config = load_config()

    api_key_field = ft.TextField(
        label="DeepL API Key",
        value=config.get("deepl_api_key", ""),
        password=True,
        can_reveal_password=True, # Allow password visibility toggle
        width=400
    )

    save_button = ft.ElevatedButton(text="APIキーを保存 (Save API Key)")

    def save_clicked(e):
        config["deepl_api_key"] = api_key_field.value
        save_config(config)
        page.snack_bar = ft.SnackBar(
            ft.Text("APIキーを保存しました。"),
            open=True
        )
        page.update()

    save_button.on_click = save_clicked

    page.add(
        ft.Column(
            [
                ft.Text("SRT Translator 設定", size=24, weight=ft.FontWeight.BOLD),
                ft.Text("DeepL APIキーを入力してください。", size=16),
                api_key_field,
                save_button,
                ft.Text(f"設定ファイルパス: {CONFIG_PATH}", size=10, color=ft.Colors.GREY_500)
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            spacing=20
        )
    )

# This is important for PyInstaller
if __name__ == "__main__":
    # Try a different port, e.g., 8080, if 8000 is in use
    ft.app(target=main, assets_dir="assets", port=8080)