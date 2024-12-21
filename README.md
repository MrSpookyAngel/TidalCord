# TidalCord  
**TidalCord** is a cross-platform Discord music bot built with Python 3.8+ using the [`discord.py`](https://github.com/Rapptz/discord.py) and [`tidalapi`](https://github.com/tamland/python-tidal) libraries. It streams music from the Tidal music service (requires a **Tidal Premium account**) by downloading songs to a cache and then streaming them to your Discord server.. The only key you need is a Discord Bot token!

---

## Features
- Stream high-quality music directly from Tidal to your Discord server.
- Auto-identify songs from YouTube links and map them to Tidal.
- Lightweight and easy to set up.

---

## Disclaimer
TidalCord is likely against the terms of service of Tidal and/or YouTube.
By using this software, you accept full responsibility for any potential issues, including account bans or other consequences.
The creator of this project is not responsible for any misuse or violations of third-party terms of service.

---

## Requirements  
1. [Python 3.8+](https://www.python.org/)
2. [FFmpeg](https://ffmpeg.org/download.html)

---

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/MrSpookyAngel/TidalCord
   cd TidalCord
   ```

2. Create and activate a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate   # On Linux/macOS
   venv\Scripts\activate      # On Windows
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Configure the environment:
   - Copy `example.env` to `.env`:
     ```bash
     cp example.env .env
     ```
   - Obtain a Discord Bot token from the [Discord Developer Portal](https://discord.com/developers/applications).
   - Update the `.env` file with your Discord Bot token.

5. Run the bot:
   ```bash
   python main.py
   ```

---

## First-Time Setup
When running the bot for the first time, you will be prompted to log into your Tidal account.

1. A code will be displayed in the terminal.
2. Visit the link provided in the terminal, log into your Tidal account, and enter the code.
3. Once authenticated, the bot will be able to begin streaming music.

---

## Notes
- A **Tidal Premium account** is required for streaming music.
- This project is a work in progress, and some features may be improved in future updates.

---

Feel free to suggest additional changes or improvements!

--- 
