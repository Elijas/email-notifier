# Create a duplicate of this file with name "configVals.py" for setting config in a local machine

# --- CONNECTION ---
POP3_SERVER = "pop3.example.com"
IMAP_SERVER = "imap.example.com"
EMAIL_USER = "username"
EMAIL_PASSWORD = "password"
IFTTT_WEBHOOK_URLS = "https://maker.ifttt.com/trigger/.....|https://maker.ifttt.com/trigger/....."
IFTTT_WEBHOOK_ADMIN_URLS = "https://maker.ifttt.com/trigger/.....|https://maker.ifttt.com/trigger/....."

# --- SETUP ---
IMPORTANT_EMAIL_SENDERS = "important.sender@example.com|another.sender@example.com"
IMPORTANT_EMAIL_SUBJECTS = "urgent|hurry|fast"  # Checks if subject contains these as sub-text, case-insensitive

# --- SETTINGS ---
EMAIL_SEARCH_DEPTH = "100"  # No. of max newest emails to check, before stopping
IFTTT_NOTIFICATIONS_LIMIT = "5"  # No. of max notifications sent, before stopping
SEND_TEST_NOTIFICATION = '0'  # 1 or 0
