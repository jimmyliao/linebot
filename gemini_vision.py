import base64
import os
import mimetypes
import logging
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

def save_binary_file(file_name, data):
    """Saves binary data to a file in the 'static' directory."""
    try:
        # Create static/images directory if it doesn't exist
        image_dir = Path("static/images")
        image_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file in static/images directory
        file_path = image_dir / file_name
        with open(file_path, "wb") as f:
            f.write(data)
        logger.info(f"File saved to: {file_path}")
        return str(file_path)
    except Exception as e:
        logger.error(f"Error saving binary file {file_name}: {e}")
        return None

def generate_image_from_text(prompt: str):
    """Generates an image from a text prompt using Gemini streaming API."""
    try:
        # Load environment variables
        load_dotenv()
        gemini_api_key = os.environ.get("GEMINI_API_KEY")

        if not gemini_api_key:
            logger.error("GEMINI_API_KEY not found in environment variables.")
            return None, None

        # Initialize Gemini client using the requested format
        client = genai.Client(
            api_key=gemini_api_key
        )

        # Model name
        IMAGE_MODEL = "gemini-2.0-flash-exp-image-generation"

        logger.info(f"Generating image from prompt: {prompt}")
        
        # Prepare content for image generation with meme style
        meme_prompt = f"Create a funny meme image without any text: {prompt}. Make it humorous and visually engaging, but do not include any text or captions in the image itself."
        contents = [
            types.Content(
                role="user",
                parts=[
                    types.Part.from_text(text=meme_prompt),
                ]
            )
        ]

        # Configure response settings
        generate_content_config = types.GenerateContentConfig(
            response_modalities=["image", "text"],
            response_mime_type="text/plain",
        )

        # Generate image using streaming
        for chunk in client.models.generate_content_stream(
            model=IMAGE_MODEL,
            contents=contents,
            config=generate_content_config,
        ):
            # Log the entire chunk structure for debugging
            logger.debug(f"Received chunk: {chunk}")

            if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                logger.warning(f"Skipping chunk with missing data: {chunk}")
                continue

            # Check for inline_data first
            if chunk.candidates[0].content.parts[0].inline_data:
                inline_data = chunk.candidates[0].content.parts[0].inline_data
                
                # Generate filename with timestamp
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                file_name = f"generated_image_{timestamp}"
                file_extension = mimetypes.guess_extension(inline_data.mime_type) or ".png"  # Default to png if unknown
                relative_file_path = f"static/images/{file_name}{file_extension}"
                
                # Save the image
                absolute_file_path = save_binary_file(f"{file_name}{file_extension}", inline_data.data)
                
                if absolute_file_path:
                    logger.info(f"File of mime type {inline_data.mime_type} saved to: {absolute_file_path}")
                    return inline_data.mime_type, relative_file_path
                else:
                    logger.error("Failed to save the generated image file.")
                    return None, None
            
            elif chunk.text:
                logger.info(f"Generation progress/text response: {chunk.text}")
        
        # If loop completes without returning image data
        logger.error("No image data found in the streaming response.")
        return None, None

    except Exception as e:
        logger.error(f"Error generating image: {e}")
        return None, None

if __name__ == "__main__":
    # Example usage when running the script directly
    test_prompt = "A photo of a cat sitting on a windowsill looking out at a rainy cityscape."
    mime, data = generate_image_from_text(test_prompt)
    if mime and data:
        # Log file path when testing directly
        logger.info(f"Successfully generated image. Mime type: {mime}, File path: {data}") 
    else:
        logger.error("Failed to generate image.")
