CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    spam_label TINYINT(1) DEFAULT 0  -- 1 = Spam, 0 = Not Spam
);


SELECT id, user_id, COALESCE(message, '') AS message, spam_label FROM messages;
