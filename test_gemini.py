# to test gemini

import os
import google.generativeai as genai

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

user_input = "What is the meaning of life?"
response = chat_session.send_message(user_input)

print(response.text)
