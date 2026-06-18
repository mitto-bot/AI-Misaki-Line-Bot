import os
import json
import threading
import traceback
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

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "").strip()
DIFY_API_KEY = os.environ.get("DIFY_API_KEY", "").strip()
DIFY_API_URL = os.environ.get(
    "DIFY_API_URL",
    "https://api.dify.ai/v1/chat-messages"
).strip()

print("========== ENV CHECK ==========")
print("LINE_TOKEN_LEN:", len(LINE_CHANNEL_ACCESS_TOKEN))
print("LINE_SECRET_LEN:", len(LINE_CHANNEL_SECRET))
print("DIFY_KEY_LEN:", len(DIFY_API_KEY))
print("DIFY_API_URL:", DIFY_API_URL)
print("===============================")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


@app.route("/", methods=["GET"])
def health_check():
    return "AIミサキLINEボットが稼働中です！", 200


@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    print("========== LINE WEBHOOK RECEIVED ==========")
    print("Body:", body)
    print("Signature exists:", bool(signature))
    print("===========================================")

    try:
        handler.parser.parse(body, signature)
    except InvalidSignatureError:
        print("LINE signature error: InvalidSignatureError")
        abort(400)
    except Exception as e:
        print("LINE parse error:", e)
        print(traceback.format_exc())
        abort(400)

    threading.Thread(
        target=handle_webhook_background,
        args=(body, signature),
        daemon=True
    ).start()

    return "OK", 200


def handle_webhook_background(body, signature):
    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Webhook background error:", e)
        print(traceback.format_exc())


@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = event.message.text
    user_id = event.source.user_id

    print("========== LINE MESSAGE ==========")
    print("User ID:", user_id)
    print("Message:", user_text)
    print("==================================")

    reply_text = ask_dify(user_text, user_id)

    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=reply_text)],
                )
            )
        print("LINE reply success")
    except Exception as e:
        print("LINE reply error:", e)
        print(traceback.format_exc())


def ask_dify(user_text, user_id):
    if not DIFY_API_KEY:
        print("Dify error: DIFY_API_KEY is empty")
        return "すみません、現在AI美咲のDify APIキーが設定されていません。管理者に確認してください。"

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

    print("========== DIFY REQUEST ==========")
    print("DIFY_API_URL:", DIFY_API_URL)
    print("Payload:", json.dumps(payload, ensure_ascii=False))
    print("==================================")

    try:
        response = requests.post(
            DIFY_API_URL,
            headers=headers,
            json=payload,
            timeout=25,
        )

        print("========== DIFY RESPONSE ==========")
        print("Status:", response.status_code)
        print("Response:", response.text)
        print("===================================")

        response.raise_for_status()
        data = response.json()

        answer = data.get("answer")
        if answer:
            return answer

        return "すみません、AI美咲から回答本文を取得できませんでした。"

    except Exception as e:
        print("Dify error:", e)
        print(traceback.format_exc())
        return "すみません、現在AI美咲の回答システムに接続できません。少し時間をおいてもう一度お試しください。"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
