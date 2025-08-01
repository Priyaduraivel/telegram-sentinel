import os
import mysql.connector
from telethon.sync import TelegramClient
from telethon.tl.functions.messages import GetDialogsRequest
from telethon.tl.types import InputPeerEmpty
from dotenv import load_dotenv
import asyncio
from telethon.tl.functions.messages import SendMessageRequest
from content_sentiment_analysis import analyze_content, process_message
from behavior_tracking import check_mass_forwarding , check_bot_like_behavior, store_forwarded_message, store_retraining_data, store_alert, store_bot_behavior
from telethon.errors import SessionPasswordNeededError 

# Load environment variables
load_dotenv()

api_id = '27517049'
api_hash = '8402687efa78d1fbe62a46d03ec9b07b'
bot_token = '7802614687:AAFHZY2hDLDkFMOLbySO4-s00jnxstMRS8w'
bot_username = 'Sential123_bot'
session_directory = 'sessions'
os.makedirs(session_directory, exist_ok=True)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="Priya@123",
        database="telegram_monitoring"
    )

def store_message_in_db(user_id, message, spam_status, language=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if language is None:
        language = "Unknown"
    
    try:
        cursor.execute(
            "INSERT INTO messages (message_content, spam_status, language) "
            "VALUES (%s, %s, %s)",  
            (message, spam_status, language)
        )
        conn.commit()
        print(f"Stored Message ID: {user_id} with Spam Status: {spam_status}")
    except Exception as e:
        print(f"Error storing message in database: {e}")
    finally:
        cursor.close()
        conn.close()

def log_user_activity(user_id, action_type, message_content=None, target_channel_id=None):
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO user_activity (user_id, action_type, message_content, target_channel_id) "
            "VALUES (%s, %s, %s, %s)",
            (user_id, action_type, message_content, target_channel_id)
        )
        conn.commit()
        print(f"✅ Logged user activity for {action_type}")  
    except Exception as e:
        print(f"⚠️ Error logging user activity: {e}")
    finally:
        cursor.close()
        conn.close()

async def alert_user(user_id, message, phone_number, priority):
    try:
        alert_message = f"[{priority}] {message}"

        # Fetch the client for the respective phone number
        if phone_number in user_mobile_number_map:
            client = user_mobile_number_map[phone_number]
            await client.send_message(phone_number, f"🚨 Alert: {alert_message}")
            print(f"🚨 Sent alert to mobile {phone_number}: {alert_message}")
        else:
            print(f"⚠️ No client found for phone number {phone_number}, unable to send alert.")

        # Send alert to the bot
        if client:
            try:
                bot = await client.get_entity(bot_username)
                if bot:
                    await client.send_message(bot, f"🚨 Alert for User {user_id} ({phone_number}): {alert_message}")
                    print(f"🚨 Sent alert to bot: {alert_message}")
                else:
                    print(f"⚠️ Failed to find bot entity for {bot_username}")
            except Exception as e:
                print(f"⚠️ Error fetching bot entity: {e}")
        else:
            print(f"⚠️ No client found for phone number {phone_number}")
            
    except Exception as e:
        print(f"⚠️ Error sending alert: {e}")


async def check_bot_like_behavior(user_id, phone_number):
    conn = get_db_connection()
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

            # Use await instead of asyncio.run()
            await alert_user(user_id, message, phone_number, "HIGH PRIORITY")  

            return True
        return False

    except Exception as e:
        print(f"⚠️ Error detecting bot-like behavior: {e}")
    finally:
        cursor.close()
        conn.close()


# Store user sessions
user_mobile_number_map = {}

async def authenticate_user(phone_number):
    session_name = os.path.join(session_directory, f"user_session_{phone_number}")
    client = TelegramClient(session_name, api_id, api_hash)
    
    try:
        await client.start(phone_number)
        me = await client.get_me()
        print(f"✅ Logged in as: {me.first_name} (@{me.username if me.username else 'No Username'})")
        
        user_mobile_number_map[phone_number] = client
        
        return client
    except Exception as e:
        print(f"Error during authentication: {e}")
        return None

async def fetch_public_channel_messages(client, phone_number):
    try:
        print("Fetching all public channels and groups...")
        dialogs = await client(GetDialogsRequest(
            offset_date=None,
            offset_id=0,
            offset_peer=InputPeerEmpty(),
            limit=200,
            hash=0
        ))

        if not dialogs.chats:
            print("No channels or groups found!")

        for chat in dialogs.chats:
            print(f"Processing messages from: {chat.title}")

            async for message in client.iter_messages(chat, limit=10):
                content = message.text if message.text else f"Media message (ID {message.id})"

                # **Sentiment Analysis**
                content_analysis_result = analyze_content(content)
                spam_status = "Spam" if content_analysis_result['sentiment'] == "Negative" else "Not Spam"

                # **Behavioral Tracking**
                try:
                    mass_forwarded = check_mass_forwarding(message.sender_id, content, phone_number)
                    print(f"🚀 Mass Forwarding Detected: {mass_forwarded}")
                except Exception as e:
                    print(f"⚠️ Error in check_mass_forwarding: {e}")
                    mass_forwarded = False
                bot_like_behavior = await check_bot_like_behavior(message.sender_id, phone_number)
                
                bot = await client.get_entity(bot_username)
                if bot:
                    alert_message = f"🚨 **Message Alert!** 🚨\n\n"
                    alert_message += f"📌 **Channel:** {chat.title}\n"
                    alert_message += f"🔎 **Spam Status:** {spam_status}\n"
                    alert_message += f"👤 **User ID:** {message.sender_id}\n"

                    # Show message content only if it's spam
                    if spam_status == "Spam":
                        alert_message += f"📩 **Message Content:** {content}\n"

                    # Show message content only if bot-like behavior is detected
                    if bot_like_behavior:
                        alert_message += f"⚠️ **Bot-Like Behavior:** Yes\n"
                        alert_message += f"📩 **Message Content:** {content}\n"

                    await client.send_message(bot, alert_message)
                    print(f"✅ Sent to bot → Channel: {chat.title}, Spam: {spam_status}")

                else:
                    print(f"⚠️ Failed to find bot entity for {bot_username}")

               

                store_message_in_db(message.id, content, spam_status)
                log_user_activity(message.sender_id, 'sent', content, chat.id)
                store_forwarded_message(message.sender_id, message.id)
                store_retraining_data(message.id, chat.title, content, spam_status)
                store_alert(message.sender_id, phone_number, "Spam detected in your message!", "HIGH")
                store_bot_behavior(message.sender_id, "spam", 1)
                

    except Exception as e:
        print(f"Error fetching messages: {e}")

async def main():
    clients = []

    while True:
        phone_number = input("📞 Enter your phone number (or type 'exit' to stop): ").strip()
        if phone_number.lower() == 'exit':
            print("🚪 Exiting program...")
            return
        
        client = await authenticate_user(phone_number)
        if client:
            clients.append(client)
        else:
            print(f"❌ Failed to authenticate {phone_number}, try again.")
        if clients:
            tasks = [fetch_public_channel_messages(client, phone_number) for client in clients]
            await asyncio.gather(*tasks)
        else:
            print("⚠️ No authenticated clients. Exiting.")

if __name__ == "__main__":
    try:
        asyncio.run(main())  # Works if no active event loop
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())  # Runs properly in existing loops

