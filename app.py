import sys

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent
)

import os
import google.generativeai as genai

# load env variables
from dotenv import load_dotenv
load_dotenv()

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

# Create the model
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
)

chat_session = model.start_chat(
    history=[
        {
            "role": "user",
            "parts": [
                "Hello",
            ],
        },
        {
            "role": "model",
            "parts": [
                "Hello! How can I help you today?\n",
            ],
        },
    ]
)


# wrap above code in a function
def get_response(user_input):
    response = chat_session.send_message(user_input)
    return response.text


# initialize the Flask app
app = Flask(__name__)

access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
secret = os.environ["LINE_CHANNEL_SECRET"]

line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(secret)

if 'google.colab' in sys.modules or 'cloud' not in os.environ.get("ENVIRONMENT", ""):
    from pyngrok import ngrok
    from pyngrok.conf import PyngrokConfig
    NGROK_TOKEN = os.environ.get("NGROK_TOKEN")

    try:
        webhook_url = ngrok.connect(
            addr="127.0.0.1:5000",
            pyngrok_config=PyngrokConfig(start_new_session=True),
            authtoken=NGROK_TOKEN
        )
        print("Ngrok Tunnel URL:", webhook_url)
    except Exception as e:
        print("Error while connecting with ngrok:", e)


@app.route("/", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text
    response = get_response(user_input)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )


SYSTEM_PROMPT = "Hello, I'm Gemini!"


@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=SYSTEM_PROMPT))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
