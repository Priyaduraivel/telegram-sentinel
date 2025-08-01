#data preprocessing.py
import re
import nltk
import requests
import cv2
import pytesseract
import telegram
from io import BytesIO
from nltk.tokenize import word_tokenize
from langdetect import detect, DetectorFactory
from stop_words import get_stop_words
from PIL import Image
from bs4 import BeautifulSoup
from telegram.ext import Updater, MessageHandler, Filters

# Ensure consistent language detection
DetectorFactory.seed = 0

# Download required NLTK data
nltk.download('stopwords')
nltk.download('punkt')

# Set Tesseract OCR path (Change based on your system)
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# Function to clean and preprocess text
def detect_language(text):
    """Detect the language of the input text."""
    try:
        return detect(text)
    except Exception:
        return "en"

def clean_text(text):
    """Clean text by removing URLs, special characters, etc."""
    if not isinstance(text, str) or not text.strip():
        return ""
    text = re.sub(r"http\S+|www\S+|https\S+", '', text, flags=re.MULTILINE)
    text = re.sub(r"@\w+|#\w+", '', text)
    text = re.sub(r"[^\w\s]", '', text)
    text = re.sub(r"\d+", '', text)
    text = text.lower()
    return text

def preprocess_text(text):
    """Preprocess text by detecting language, tokenizing, and removing stopwords."""
    if not isinstance(text, str) or not text.strip():
        return ""
    lang = detect_language(text)
    cleaned_text = clean_text(text)
    tokens = word_tokenize(cleaned_text)
    try:
        stop_words = set(get_stop_words(lang))
        tokens = [word for word in tokens if word not in stop_words]
    except:
        pass
    return " ".join(tokens)

# Function to extract text from images
def extract_text_from_image(image):
    """Extract text from an image using OCR."""
    try:
        text = pytesseract.image_to_string(image)
        return preprocess_text(text)
    except Exception as e:
        print(f"Error extracting text from image: {e}")
        return ""

# Function to preprocess images
def preprocess_image(image):
    """Convert image to grayscale and resize."""
    try:
        gray_image = image.convert("L")  # Convert to grayscale
        resized_image = gray_image.resize((256, 256))  # Resize to fixed size
        return resized_image
    except Exception as e:
        print(f"Error preprocessing image: {e}")
        return None

# Function to fetch and extract text from URLs
def extract_text_from_url(url):
    """Fetch and extract text from a web page."""
    try:
        response = requests.get(url)
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text()
        return preprocess_text(text)
    except Exception as e:
        print(f"Error extracting text from URL: {e}")
        return ""

# Function to preprocess incoming messages from Telegram bot
def handle_message(update, context):
    """Handle text messages from users."""
    text = update.message.text
    processed_text = preprocess_text(text)
    update.message.reply_text(f"Processed Text: {processed_text}")

# Function to handle images
def handle_image(update, context):
    """Handle image messages from users."""
    photo_file = update.message.photo[-1].get_file()
    image_bytes = BytesIO(photo_file.download_as_bytearray())
    image = Image.open(image_bytes)

    extracted_text = extract_text_from_image(image)
    processed_image = preprocess_image(image)

    update.message.reply_text(f"Extracted Text from Image: {extracted_text}")

# Function to handle videos
def handle_video(update, context):
    """Handle video messages from users."""
    update.message.reply_text("Video processing is currently under development.")

# Function to handle URLs
def handle_url(update, context):
    """Handle URL messages from users."""
    url = update.message.text
    extracted_text = extract_text_from_url(url)
    update.message.reply_text(f"Extracted Text from URL: {extracted_text}")

# Main function to set up the bot
def main():
    """Start the bot."""
    TELEGRAM_BOT_TOKEN = "7802614687:AAFHZY2hDLDkFMOLbySO4-s00jnxstMRS8w"

    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))
    dp.add_handler(MessageHandler(Filters.photo, handle_image))
    dp.add_handler(MessageHandler(Filters.video, handle_video))
    dp.add_handler(MessageHandler(Filters.entity("url"), handle_url))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
