# PSN Offers Telegram Bot

A Telegram bot that automatically collects and posts the latest offers from the PlayStation Store (PSN) to your Telegram channel.

---

## Features

- Web Scraping PSN: Automatically fetches all current game offers and stores them in a database.  
- Telegram Posting: Reads the database and sends well-formatted messages with game details including:
  - Game name  
  - Price  
  - Link to the offer  
  - Image of the game  
- Admin Panel: Full control over the bot, including:
  - Scheduling post times  
  - Scheduling scraping and database updates  
  - Clearing the database  
  - Triggering immediate scraping and updates  
  - Pausing/resuming data scraping or Telegram posting independently  

---

## How It Works

1. The bot scrapes the PSN website for offers.  
2. The data is saved in a local or remote database.  
3. The Telegram posting module reads the database and publishes formatted messages to a channel.  
4. The admin panel allows real-time control over all operations.


---

1. Set up a Python virtual environment and install dependencies:
   Copy code

```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r installed_packages.txt
```
2. Configure the bot settings (API keys, channel ID, database connection).

3. Run the bot and the Telegram poster module.


---

## Notes
1. Make sure the database and Telegram bot credentials are configured correctly.
2. The bot allows complete real-time control through the admin panel.
3. Ideal for automating PSN offer notifications in a Telegram channel.
