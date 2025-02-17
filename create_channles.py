import os
import json
import requests
import logging
import time
from requests.exceptions import RequestException

# ログ設定
logging.basicConfig(level=logging.INFO)

# Slack API用のトークンとエンドポイント
SLACK_TOKEN = "xoxb-XXXXXXXXXXXX-XXXXXXXXXXXX-XXXXXXXXXXXXXXXX"
SLACK_API_URL = "https://slack.com/api/"


def get_existing_channels():
    """
    Slack上の既存チャンネル一覧を取得する。
    API呼び出し時のエラーやHTTPエラーもハンドリング。
    """
    url = SLACK_API_URL + "conversations.list"
    headers = {"Authorization": f"Bearer {SLACK_TOKEN}"}
    params = {
        "exclude_archived": "true",
        "types": "public_channel,private_channel"
    }

    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()  # HTTPエラーの検出
        data = response.json()

        if not data.get("ok"):
            error_msg = data.get("error", "Unknown error")
            needed_permissions = data.get("needed", "Unknown permissions")
            logging.error(f"conversations.list APIエラー: {error_msg}", )
            logging.error(f"needed_permissions: {needed_permissions}")
            return []
        return data.get("channels", [])

    except RequestException as e:
        logging.error("conversations.list リクエスト例外: %s", str(e))
        return []


def create_channel(channel_name, description, is_private, invite_users_list):
    """
    指定された名前のチャンネルを作成し、その後説明（トピック）を設定する。
    エラー発生時は詳細をログ出力し、False を返す。
    """
    url = SLACK_API_URL + "conversations.create"
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json; charset=utf-8"
    }
    payload = {
        "name": channel_name,
        "is_private": is_private  # JSONの is_private フィールドを使用
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            error_msg = data.get("error", "Unknown error")
            needed_permissions = data.get("needed", "Unknown permissions")
            logging.error(f"conversations.create APIエラー（'{channel_name}'）： {error_msg}")
            logging.error(f"needed_permissions（'{channel_name}'）： {needed_permissions}")
            logging.error(f"data'{channel_name}'）： {data}")
            return False

        channel_id = data["channel"]["id"]

        # 作成後にチャンネルの説明（トピック）を設定
        topic_url = SLACK_API_URL + "conversations.setPurpose"
        topic_payload = {
            "channel": channel_id,
            "purpose": description
        }
        topic_response = requests.post(topic_url, headers=headers, json=topic_payload)
        topic_response.raise_for_status()
        topic_data = topic_response.json()

        if not topic_data.get("ok"):
            topic_error = topic_data.get("error", "Unknown error")
            logging.error(f"conversations.setPurpose APIエラー（'{channel_name}'）： {topic_error}")
            logging.error("*" * 50)
            return False

        logging.info(f"チャンネル '{channel_name}' が正常に作成され、説明が設定されました。")
        invite_users_to_channel(channel_id, invite_users_list)
        return True

    except RequestException as e:
        logging.error(f"チャンネル '{channel_name}' 作成中のリクエスト例外: {str(e)}")
        return False


def invite_users_to_channel(channel_id, user_ids):
    """
    指定されたチャンネルにユーザーを招待する。
    エラー発生時は詳細をログ出力し、False を返す。
    """
    url = SLACK_API_URL + "conversations.invite"
    payload = {
        "channel": channel_id,
        "users": ",".join(user_ids)
    }
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json;charset=utf-8"
    }

    response = requests.post(url, json=payload, headers=headers)

    try:
        response.raise_for_status()  # HTTPエラーが発生した場合は例外を発生させる
        result = response.json()
        if not result.get("ok", False):
            raise Exception(f"Slack API Error: {result.get('error')}")
        return result

    except Exception as e:
        # エラー時はそのまま例外をスローします
        raise Exception(f"招待処理中にエラーが発生しました: {e}")


def main():
    # スクリプトと同じディレクトリ内の channels.json ファイルのパスを生成
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_channels_file_path = os.path.join(script_dir, "channels.json")
    json_invite_users_file_path = os.path.join(script_dir, "init_invite_users.json")

    # JSONファイルからチャンネルリストを読み込み（エラーハンドリング付き）
    try:
        with open(json_channels_file_path, "r", encoding="utf-8") as f:
            channels_list = json.load(f)
        with open(json_invite_users_file_path, "r", encoding="utf-8") as f:
            invite_users_list = json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logging.error("channels.json 読み込みエラー: %s", str(e))
        return

    # 既存チャンネル一覧を取得
    existing_channels = get_existing_channels()
    existing_channel_names = {channel["name"] for channel in existing_channels}

    # JSON内の各チャンネル名と既存チャンネルの重複チェック
    for channel in channels_list:
        if channel["name"] in existing_channel_names:
            logging.error("重複するチャンネルが見つかりました: '%s'。処理を中断します。", channel["name"])
            logging.error("*" * 50)
            return

    # 重複がなければチャンネル作成を実施
    for channel in channels_list:
        name = channel.get("name")
        description = channel.get("description", "")
        is_private = channel.get("is_private", False)  # デフォルトは False
        success = create_channel(name, description, is_private, invite_users_list['users'])

        if not success:
            logging.error(f"チャンネル '{name}' の作成に失敗したため、以降の処理を中断します。")
            return

        # レートリミット対策のため少し待機（必要に応じて調整）
        time.sleep(1)


if __name__ == '__main__':
    main()
