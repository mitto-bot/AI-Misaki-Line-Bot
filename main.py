import os
import requests
from flask import Flask, request, abort

from linebot.v3.webhook import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
DIFY_API_KEY = os.environ.get("DIFY_API_KEY")
DIFY_API_URL = os.environ.get(
    "DIFY_API_URL",
    "https://api.dify.ai/v1/chat-messages"
)

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/", methods=["GET"])
def health_check():
    return "AIミサキLINEボットが稼働中です！"


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text
    user_id = event.source.user_id

    reply_text = ask_dify(user_text, user_id)

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)],
            )
        )


def ask_dify(user_text, user_id):
    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "inputs": {},
        "query": user_text,
        "response_mode": "blocking",
        "conversation_id": "",
        "user": user_id,
    }

    try:
        response = requests.post(
            DIFY_API_URL,
            headers=headers,
            json=payload,
            timeout=30,
        )

        print("========== DIFY DEBUG ==========")
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("================================")

        response.raise_for_status()

        data = response.json()
        return data.get(
            "answer",
            "すみません、うまく回答を作れませんでした。"
        )

    except Exception as e:
        print("Dify error:", e)
        return "すみません、現在AI美咲の回答システムに接続できません。少し時間をおいてもう一度お試しください。"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
