import sys

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent,
    ImageMessage
)

import os
import google.generativeai as genai
import base64
import requests
from io import BytesIO

# load env variables
from dotenv import load_dotenv
load_dotenv()

access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
secret = os.environ["LINE_CHANNEL_SECRET"]
environment = os.environ.get("ENVIRONMENT", "local")
gemini_api_key = os.environ["GEMINI_API_KEY"]
webhook_host = "0.0.0.0"
webhook_port = 8080

# print env
print(f"Environment: {environment}")

genai.configure(api_key=gemini_api_key)

# Create the model
generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 40,
    "max_output_tokens": 8192,
    "response_mime_type": "text/plain",
}

# Text model for chat
text_model = genai.GenerativeModel(
    model_name="gemini-2.0-flash-exp",
    generation_config=generation_config,
)

# Vision model for image processing
vision_model = genai.GenerativeModel(
    model_name="gemini-2.5-pro-preview-03-25",
    generation_config=generation_config,
)

chat_session = text_model.start_chat(
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


# Function to get text response
def get_text_response(user_input):
    response = chat_session.send_message(user_input)
    return response.text

# Function to process image and get summary
def get_image_summary(image_url):
    try:
        # Download the image from LINE's server
        content = line_bot_api.get_message_content(image_url)
        image_data = BytesIO()
        for chunk in content.iter_content():
            image_data.write(chunk)
        image_data.seek(0)
        
        # Convert to base64 for Gemini
        image_base64 = base64.b64encode(image_data.read()).decode('utf-8')
        
        # Create prompt for image analysis
        prompt = "請以繁體中文描述這張圖片的內容。提供詳細的描述，包括圖片中的主要物體、人物、場景和任何值得注意的細節。"
        
        # Get response from Gemini vision model
        response = vision_model.generate_content(
            [
                prompt,
                {"mime_type": "image/jpeg", "data": image_base64}
            ]
        )
        
        return response.text
    except Exception as e:
        print(f"Error processing image: {e}")
        return "抱歉，我無法處理這張圖片。請再試一次或上傳其他圖片。"


# initialize the Flask app
app = Flask(__name__)


line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(secret)


@app.route("/health")
def health():
    return ("OK", 200)


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
def handle_text_message(event):
    user_input = event.message.text
    response = get_text_response(user_input)
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=response)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    # Get the message ID of the image
    message_id = event.message.id
    
    # Get image summary from Gemini
    summary = get_image_summary(message_id)
    
    # Reply with the summary
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=summary)
    )

# SYSTEM PROMPT should prepare to answer with Traditional Chinese
SYSTEM_PROMPT = "請以繁體中文回應"


@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=SYSTEM_PROMPT))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
