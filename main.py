import os
import json
import flet as ft

CONFIG_PATH = "config.json"

def load_config():
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r") as f:
            return json.load(f)
    return {"deepl_api_key": ""}

def save_config(config):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f)

def main(page: ft.Page):
    page.title = "SRT Translator"
    config = load_config()

    api_key_field = ft.TextField(label="DeepL API Key", value=config.get("deepl_api_key", ""), password=True)
    save_button = ft.ElevatedButton(text="Save API Key")

    def save_clicked(e):
        config["deepl_api_key"] = api_key_field.value
        save_config(config)
        page.snack_bar = ft.SnackBar(ft.Text("APIキーを保存しました"))
        page.snack_bar.open = True
        page.update()

    save_button.on_click = save_clicked
    page.add(api_key_field, save_button)

ft.app(target=main)
