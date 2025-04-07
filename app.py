import sys
import warnings
import threading
import time
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress deprecation warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)

from flask import Flask, request, abort, send_from_directory
# Import LINE Bot SDK
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage, FollowEvent,
    ImageMessage, ImageSendMessage
)

import os
import google.generativeai as genai
import base64
import mimetypes
from pathlib import Path
from io import BytesIO
import requests
import json
import random

from gemini_vision import generate_image_from_text as generate_image_from_vision_module

# load env variables
from dotenv import load_dotenv
load_dotenv()

access_token = os.environ["LINE_CHANNEL_ACCESS_TOKEN"]
secret = os.environ["LINE_CHANNEL_SECRET"]
environment = os.environ.get("ENVIRONMENT", "local")
gemini_api_key = os.environ["GEMINI_API_KEY"]
giphy_api_key = os.environ.get("GIPHY_API_KEY", "None")
webhook_host = "0.0.0.0"
webhook_port = 8080

# Get base public URL from environment variable
NGROK_URL = os.environ.get("NGROK_URL")
if not NGROK_URL:
    if environment == "local":
         logger.warning("NGROK_URL environment variable not set. Image URLs will likely fail.")
         # Set a placeholder for local testing, but this won't work for LINE
         NGROK_URL = f"http://{webhook_host}:{webhook_port}"
    else:
        logger.error("NGROK_URL environment variable is REQUIRED in production/deployment.")
        # In a real deployment, you might want to raise an error or exit
        NGROK_URL = "" # Set to empty to cause downstream errors if not set

logger.info(f"Using base URL for images: {NGROK_URL}")

# Log environment
logger.info(f"Environment: {environment}")

# Configure Gemini
genai.configure(api_key=gemini_api_key)

# Create models
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
                "Hello! How can I help you today?\\n",
            ],
        },
    ]
)


# Function to get text response
def get_text_response(user_input):
    response = chat_session.send_message(user_input)
    return response.text

# Function to process image and get summary
def get_image_summary(message_id):
    try:
        # Download the image from LINE's server using v1 API for simplicity
        message_content = line_bot_api.get_message_content(message_id)
        image_data = BytesIO()
        for chunk in message_content.iter_content():
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
        logger.error(f"Error processing image: {e}")
        return "抱歉，我無法處理這張圖片。請再試一次或上傳其他圖片。"


# initialize the Flask app
app = Flask(__name__)

# Initialize APIs
line_bot_api = LineBotApi(access_token)
handler = WebhookHandler(secret)

# Add a route to serve generated images
@app.route('/images/<filename>')
def serve_image(filename):
    return send_from_directory('images', filename)

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

# Function to process text message in a separate thread
def process_text_message_async(user_id, user_input):
    # Process the text message
    response = get_text_response(user_input)
    
    # Send the actual response
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text=response)
    )

# Function to process image generation in a separate thread
def process_image_generation_async(user_id, prompt):
    # Generate image from the prompt using the imported function
    mime_type, relative_file_path = generate_image_from_vision_module(prompt)
    
    if mime_type and relative_file_path:
        # Construct the PUBLIC HTTPS URL for the image
        if not NGROK_URL:
            logger.error("NGROK_URL is not configured. Cannot send image.")
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text="伺服器設定錯誤，無法傳送圖片URL。")
            )
            return
            
        # Ensure NGROK_URL ends with a single slash if not empty
        base_url = NGROK_URL.rstrip('/') if NGROK_URL else ''
        image_public_url = f"{base_url}/{relative_file_path}"
        logger.info(f"Generated image public URL: {image_public_url}")
        
        # Send both the image and its URL
        try:
            # Send messages in a batch to maintain order
            line_bot_api.push_message(
                user_id,
                [
                    ImageSendMessage(
                        original_content_url=image_public_url,
                        preview_image_url=image_public_url
                    ),
                    TextSendMessage(text=f"圖片網址：{image_public_url}")
                ]
            )
        except Exception as e:
            logger.error(f"Error sending image with URL {image_public_url}: {e}")
            # If sending fails, send just the URL
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text=f"已生成圖片，但無法直接顯示。您可以透過以下網址查看：\n{image_public_url}")
            )
    else:
        # Send error message if image generation failed
        line_bot_api.push_message(
            user_id,
            TextSendMessage(text="抱歉，無法生成圖片。請再試一次或使用不同的描述。")
        )

def get_random_meme():
    try:
        url = f"https://api.giphy.com/v1/gifs/random?api_key={giphy_api_key}&tag=meme&rating=g"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            gif_url = data["data"]["images"]["original"]["url"]
            return gif_url
        else:
            logger.error(f"GIPHY API error: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"Error getting meme from GIPHY: {e}")
        return None

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    user_input = event.message.text
    user_id = event.source.user_id
    
    # Check if the message is a request to generate an image or get a meme
    if user_input.startswith("/image ") or user_input.startswith("圖片 ") or user_input.startswith("生成圖片 "):
        # Extract the prompt for image generation
        if user_input.startswith("/image "):
            prompt = user_input[7:]
        elif user_input.startswith("圖片 "):
            prompt = user_input[3:]
        else:  # 生成圖片
            prompt = user_input[5:]
        
        # Send immediate response
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請稍候，正在生成圖片...")
        )
        
        # Process image generation in a separate thread
        threading.Thread(target=process_image_generation_async, args=(user_id, prompt)).start()
    elif user_input.startswith("/meme"):
        # Send immediate response
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請稍候，正在尋找有趣的迷因...")
        )
        
        # Get random meme
        gif_url = get_random_meme()
        if gif_url:
            try:
                line_bot_api.push_message(
                    user_id,
                    ImageSendMessage(
                        original_content_url=gif_url,
                        preview_image_url=gif_url
                    )
                )
            except Exception as e:
                logger.error(f"Error sending meme: {e}")
                line_bot_api.push_message(
                    user_id,
                    TextSendMessage(text=f"抱歉，無法顯示迷因。您可以透過以下網址查看：\n{gif_url}")
                )
        else:
            line_bot_api.push_message(
                user_id,
                TextSendMessage(text="抱歉，無法取得迷因。請稍後再試。")
            )
    else:
        # Send immediate response
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="請稍候，正在生成回應...")
        )
        
        # Process text message in a separate thread
        threading.Thread(target=process_text_message_async, args=(user_id, user_input)).start()

# Function to process image analysis in a separate thread
def process_image_analysis_async(user_id, message_id):
    # Get image summary from Gemini
    summary = get_image_summary(message_id)
    
    # Send the summary
    line_bot_api.push_message(
        user_id,
        TextSendMessage(text=summary)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    # Get the message ID of the image
    message_id = event.message.id
    user_id = event.source.user_id
    
    # Send immediate response
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="請稍候，正在分析圖片...")
    )
    
    # Process image analysis in a separate thread
    threading.Thread(target=process_image_analysis_async, args=(user_id, message_id)).start()

# SYSTEM PROMPT should prepare to answer with Traditional Chinese
SYSTEM_PROMPT = "請以繁體中文回應"

# Function to handle follow event
@handler.add(FollowEvent)
def handle_follow(event):
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=SYSTEM_PROMPT)
    )

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting LINE Bot application on port {port}")
    app.run(host="0.0.0.0", port=port)
