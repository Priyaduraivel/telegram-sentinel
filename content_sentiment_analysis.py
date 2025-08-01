# content_sentiment_analysis.py
import os
import pickle
import mysql.connector
import cv2
import nltk
import speech_recognition as sr
from textblob import TextBlob
from dotenv import load_dotenv
from langdetect import detect
from googletrans import Translator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.naive_bayes import MultinomialNB
from nltk.sentiment.vader import SentimentIntensityAnalyzer
from skimage.feature import hog
from sklearn.svm import SVC
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty


# Load environment variables
load_dotenv()

# Download required NLTK data
nltk.download('vader_lexicon')

# Initialize Google Translator
translator = Translator()


# 📌 **Database Connection**
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Priya@123",
        database="telegram_monitoring"
    )


# 📌 **Load Pre-trained Spam Detection Model & Vectorizer**
def load_models():
    try:
        with open("spam_model.pkl", "rb") as f:
            model = pickle.load(f)
        with open("tfidf_vectorizer.pkl", "rb") as f:
            vectorizer = pickle.load(f)
        print("✅ Model and vectorizer loaded successfully.")
        return model, vectorizer
    except FileNotFoundError:
        print("⚠️ Model or vectorizer not found. Using fallback model.")
        return None, None


# Load models
model, vectorizer = load_models()

# 📌 **Fallback Model (If No Pre-trained Model Found)**
if model is None or vectorizer is None:
    print("Using fallback model and vectorizer.")
    # Fallback: Train a simple model and vectorizer
    texts = [
        "This is a spam message",
        "Hello, how are you?",
        "Limited offer! Buy now and save big",
        "Let's meet up tomorrow",
        "Special discount for you today"
    ]
    labels = [1, 0, 1, 0, 1]  # 1 = Spam, 0 = Not Spam
    vectorizer = TfidfVectorizer(stop_words='english')
    X = vectorizer.fit_transform(texts)
    model = MultinomialNB()
    model.fit(X, labels)


# 📌 **Store Misclassified Messages for Retraining**

def store_misclassified_message(message_id, channel_name, content, spam_label, language=None):
    """Store misclassified messages in the retraining_data table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if language is None:
            language = "Unknown"
    try:
        cursor.execute("INSERT INTO telegram_monitoring.retraining_data (message_id, channel_name, content, spam_status, language)"
            "VALUES (%s, %s, %s, %s, %s)",
            (message_id, channel_name, content, spam_label, language))
        
        conn.commit()
        print(f"✅ Stored misclassified message (ID: {message_id}) in retraining_data")
    
    except Exception as e:
        print(f"⚠️ Error storing data: {e}")  # Debugging print
    
    finally:
        cursor.close()
        conn.close()


# 📌 **Retrain the Model with New Data**
def retrain_model():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT message, label FROM retraining_data")
        data = cursor.fetchall()

        if len(data) < 10:  # Minimum messages before retraining
            print("⚠️ Not enough data to retrain.")
            return

        texts, labels = zip(*data)

        # Retrain the model
        global vectorizer, model
        vectorizer = TfidfVectorizer(stop_words="english")
        X = vectorizer.fit_transform(texts)
        model = MultinomialNB()
        model.fit(X, labels)

        # Save updated model
        with open("spam_model.pkl", "wb") as f:
            pickle.dump(model, f)
        with open("tfidf_vectorizer.pkl", "wb") as f:
            pickle.dump(vectorizer, f)

        print("✅ Model retrained successfully.")

        # Clear retraining data
        cursor.execute("DELETE FROM retraining_data")
        conn.commit()
    except Exception as e:
        print(f"⚠️ Error retraining model: {e}")
    finally:
        cursor.close()
        conn.close()


# 📌 **Detect Language and Translate to English**
def process_message(content):
    try:
        detected_lang = detect(content)
        print(f"🌍 Detected language: {detected_lang}")

        # Translate if not English
        if detected_lang != "en":
            translated_content = translator.translate(content, src=detected_lang, dest="en").text
            print(f"🔄 Translated message: {translated_content}")
        else:
            translated_content = content

        # Detect Spam
        spam_result = detect_spam(translated_content)
        return spam_result
    except Exception as e:
        print(f"⚠️ Error processing message: {e}")
        return "Error"


# 📌 **Spam Detection Using Classifier**
def detect_spam(content):
    processed_content = content.lower()
    content_tfidf = vectorizer.transform([processed_content])
    prediction = model.predict(content_tfidf)
    return "Spam" if prediction[0] == 1 else "Not Spam"


# 📌 **Sentiment Analysis Using VADER**
def analyze_content(content):
    if not content:
        return {"sentiment": "Unknown", "polarity": 0.0}

    sid = SentimentIntensityAnalyzer()
    sentiment_score = sid.polarity_scores(content)

    if sentiment_score["compound"] > 0:
        sentiment = "Positive"
    elif sentiment_score["compound"] < 0:
        sentiment = "Negative"
    else:
        sentiment = "Neutral"

    return {"sentiment": sentiment, "polarity": sentiment_score["compound"]}


# 📌 **HOG Feature Extraction for Images**
def extract_hog_features(image_path):
    try:
        image = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if image is None:
            raise ValueError(f"Cannot read image: {image_path}")
        image = cv2.resize(image, (128, 64))
        features, _ = hog(image, orientations=9, pixels_per_cell=(8, 8), cells_per_block=(2, 2), visualize=True)
        return features
    except Exception as e:
        print(f"⚠️ Error processing image: {e}")
        return None


# 📌 **Spam Detection for Images**
def is_spam_image(image_path, model):
    features = extract_hog_features(image_path)
    if features is None:
        return False
    prediction = model.predict([features])
    return prediction[0] == 1  # True if spam


# 📌 **Process Incoming Messages from Telegram**
def process_incoming_message(message):
    file_type = message.get("file_type")  # Text, image, video, or audio
    content = message.get("text")  # Text message content

    if content:
        # Process Text
        sentiment_result = analyze_content(content)
        spam_result = process_message(content)
        print(f"📝 Text Message: {content}")
        print(f"📊 Sentiment: {sentiment_result['sentiment']}, Polarity: {sentiment_result['polarity']}")
        print(f"🚨 Spam Status: {spam_result}")

    elif file_type:
        # Process Multimedia
        if file_type == "image":
            result = analyze_image(message["content"])
            print(f"🖼️ Image Spam Status: {result}")
        elif file_type == "video":
            result = analyze_video(message["content"])
            print(f"🎥 Video Spam Status: {result}")
        elif file_type == "audio":
            sentiment_result, spam_result = analyze_audio(message["content"])
            print(f"🎙️ Audio Sentiment: {sentiment_result['sentiment']}, Spam Status: {spam_result}")
        else:
            print("⚠️ Unsupported file type")



def analyze_image(image_path):
    """Detect spam in an image."""
    model = load_image_model()  # Load the pre-trained model
    if is_spam_image(image_path, model):
        return "Spam"
    else:
        return "Not Spam"

def analyze_video(video_path):
    """Detect spam in a video by analyzing its frames."""
    try:
        video = cv2.VideoCapture(video_path)
        if not video.isOpened():
            raise ValueError(f"Cannot read video: {video_path}")
        while video.isOpened():
            ret, frame = video.read()
            if not ret:
                break
            if is_spam_image(frame, load_image_model()):
                return "Spam"
        return "Not Spam"
    except Exception as e:
        print(f"Error processing video: {e}")
        return "Not Spam"


def analyze_audio(audio_path):
    """Convert audio to text and then perform sentiment analysis/spam detection."""
    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(audio_path) as source:
            audio = recognizer.record(source)
        text = recognizer.recognize_google(audio)  # Convert speech to text
        sentiment_result = analyze_content(text)
        spam_result = detect_spam(text)
        return sentiment_result, spam_result
    except sr.UnknownValueError:
        print("Google Speech Recognition could not understand the audio.")
        return {"sentiment": "Unknown", "polarity": 0.0}, "Not Spam"
    except sr.RequestError:
        print("Could not request results from Google Speech Recognition.")
        return {"sentiment": "Unknown", "polarity": 0.0}, "Not Spam"

def load_image_model():
    """Load the pre-trained image classification model."""
    with open(os.getenv('SPAM_IMAGE_MODEL_PATH', 'spam_image_model.pkl'), 'rb') as f:
        model = pickle.load(f)
    return model

