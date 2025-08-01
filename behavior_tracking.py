# behavior_tracking.py
from telethon import TelegramClient
from telethon.tl.types import PeerChannel
from telethon.errors import SessionPasswordNeededError
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta

def get_db_connection():
    try:
        conn = mysql.connector.connect(
            host="localhost",
            user="root",
            password="Priya@123",
            database="telegram_monitoring"
        )
        if conn.is_connected():
            return conn
    except Error as e:
        print(f"⚠️ Error connecting to database: {e}")
        return None

def log_user_activity(user_id, action_type, message_content=None, target_channel_id=None):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to log user activity: No connection to database.")
        return
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO user_activity (user_id, action_type, message_content, target_channel_id) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, action_type, message_content, target_channel_id)
        )
        conn.commit()
    except Error as e:
        print(f"⚠️ Error logging user activity: {e}")
        conn.rollback()  # Rollback if any error occurs
    finally:
        cursor.close()
        conn.close()


async def check_mass_forwarding(user_id, message_content, phone_number):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to check mass forwarding: No connection to database.")
        return False
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM user_activity WHERE user_id = %s AND message_content = %s "
            "AND action_type = 'sent' AND timestamp > NOW() - INTERVAL 1 HOUR",
            (user_id, message_content)
        )
        count = cursor.fetchone()[0]
        if count > 5:
            message = "🚨 Mass forwarding detected!"
            print(message)
            alert_user(user_id, message, phone_number)
            return True
        return False
    except Error as e:
        print(f"⚠️ Error checking mass forwarding: {e}")
    finally:
        cursor.close()
        conn.close()
    return False


def check_bot_like_behavior(user_id, phone_number):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to check bot-like behavior: No connection to database.")
        return False
    cursor = conn.cursor()
    
    try:
        cursor.execute(
            "SELECT COUNT(*) FROM user_activity WHERE user_id = %s AND action_type = 'sent' "
            "AND timestamp > NOW() - INTERVAL 5 MINUTE",
            (user_id,)
        )
        message_count = cursor.fetchone()[0]
        if message_count > 10:
            message = "🚨 Bot-like behavior detected!"
            print(message)
            alert_user(user_id, message, phone_number)
            return True
        return False
    except Error as e:
        print(f"⚠️ Error detecting bot-like behavior: {e}")
    finally:
        cursor.close()
        conn.close()


def alert_user(user_id, message):
    print(f"🚨 Alert for User {user_id}: {message}")

async def monitor_activities(client):
    async for message in client.iter_messages('your_channel_name'):
        user_id = message.sender_id
        message_content = message.text
        target_channel_id = message.to_id.channel_id if isinstance(message.to_id, PeerChannel) else None
        
        log_user_activity(user_id, 'sent', message_content, target_channel_id)
        
        if check_mass_forwarding(user_id, message_content):
            alert_user(user_id, "Mass forwarding detected!")
        
        if check_bot_like_behavior(user_id):
            alert_user(user_id, "Bot-like behavior detected!")


def check_message_frequency(user_id):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to check message frequency: No connection to database.")
        return
    cursor = conn.cursor()
    
    time_threshold = datetime.now() - timedelta(seconds=10)
    cursor.execute("SELECT timestamp FROM user_activity WHERE user_id = %s AND timestamp >= %s", (user_id, time_threshold))
    
    messages = cursor.fetchall()
    
    if len(messages) > 5:
        print(f"User {user_id} is sending too many messages!")
    cursor.close()
    conn.close()

def store_forwarded_message(user_id, forwarded_message_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO forwarded_messages (user_id, forwarded_message_id) VALUES (%s, %s)",
            (user_id, forwarded_message_id)
        )
        conn.commit()
        print(f"✅ Stored forwarded message from User {user_id} → Message ID: {forwarded_message_id}")
    except Exception as e:
        print(f"⚠️ Error storing forwarded message: {e}")
    finally:
        cursor.close()
        conn.close()


def track_forwarded_messages(user_id, forwarded_message_id):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to track forwarded message: No connection to database.")
        return
    cursor = conn.cursor()
    query = "SELECT COUNT(*) FROM forwarded_messages WHERE user_id = %s AND forwarded_message_id = %s"
    cursor.execute(query, (user_id, forwarded_message_id))
    
    result = cursor.fetchone()
    if result[0] > 3:
        print(f"User {user_id} is mass forwarding the same message!")
    cursor.close()
    conn.close()

def check_bot_behavior(user_id):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to check bot behavior: No connection to database.")
        return
    cursor = conn.cursor()
    query = "SELECT message_content, COUNT(*) FROM user_activity WHERE user_id = %s GROUP BY message_content"
    cursor.execute(query, (user_id,))
    
    messages = cursor.fetchall()
    
    for message, count in messages:
        if count > 10:
            print(f"User {user_id} is sending repetitive messages: '{message}'")
    
    cursor.close()
    conn.close()

async def process_user_message(user_id, message_content, forwarded_message_id=None):
    check_message_frequency(user_id)
    log_user_activity(user_id, 'sent', message_content, None)
    
    if forwarded_message_id:
        store_forwarded_message(user_id, forwarded_message_id)
        track_forwarded_messages(user_id, forwarded_message_id)
    
    await check_bot_behavior(user_id)

def store_misclassified_message(message_id, channel_name, content, spam_label, language=None):
    conn = get_db_connection()
    if conn is None:
        print("❌ Failed to store misclassified message: No connection to database.")
        return
    cursor = conn.cursor()
    if language is None:
        language = "Unknown"
    
    try:
        cursor.execute("INSERT INTO telegram_monitoring.retraining_data (message_id, channel_name, content, spam_status, language) "
                       "VALUES (%s, %s, %s, %s, %s)",
                       (message_id, channel_name, content, spam_label, language))
        conn.commit()
        print(f"✅ Stored misclassified message (ID: {message_id}) in retraining_data")
    except Error as e:
        print(f"⚠️ Error storing data: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def store_retraining_data(message_id, channel_name, content, spam_status, language=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    if language is None:
        language = "Unknown"

    try:
        cursor.execute(
            "INSERT INTO retraining_data (message_id, channel_name, content, spam_status, language) "
            "VALUES (%s, %s, %s, %s, %s)",
            (message_id, channel_name, content, spam_status, language)
        )
        conn.commit()
        print(f"✅ Stored retraining data for Message ID: {message_id} → Spam: {spam_status}")
    except Exception as e:
        print(f"⚠️ Error storing retraining data: {e}")
    finally:
        cursor.close()
        conn.close()
def store_alert(user_id, phone_number, alert_message, priority):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO alerts (user_id, phone_number, alert_message, priority) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, phone_number, alert_message, priority)
        )
        conn.commit()
        print(f"🚨 Stored Alert for User {user_id} | Priority: {priority}")
    except Exception as e:
        print(f"⚠️ Error storing alert: {e}")
    finally:
        cursor.close()
        conn.close()
def store_bot_behavior(user_id, detection_type, message_count):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO bot_behavior (user_id, detection_type, message_count) "
            "VALUES (%s, %s, %s)",
            (user_id, detection_type, message_count)
        )
        conn.commit()
        print(f"🤖 Stored bot behavior for User {user_id} → Type: {detection_type} | Count: {message_count}")
    except Exception as e:
        print(f"⚠️ Error storing bot behavior: {e}")
    finally:
        cursor.close()
        conn.close()

