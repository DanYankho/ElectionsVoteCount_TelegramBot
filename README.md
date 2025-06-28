# 🗳️ Telegram Vote Count Bot with OCR

A Telegram bot that collects vote count reports from users by allowing them to submit images of tally sheets. The bot extracts vote numbers using OCR, lets users manually select their region and district, and submits the results to a Google Sheets backend via a Web App URL.

---

## 🚀 Features

- 📸 **OCR from image uploads**  
  Extracts vote counts from uploaded photos using the [OCR.Space API](https://ocr.space/OCRAPI).
  
- 🗺️ **Interactive location selection**  
  Region and district selection via inline buttons.

- 👤 **Candidate mode selection**  
  Choose to submit votes for **one candidate** or **all 4**:
  - Lazarus Chakwera
  - Peter Mutharika
  - Atupele Muluzi
  - William Kamkwamba Kabambe

- 📤 **Data submission**  
  Submits extracted vote data to a [Google Apps Script Web App](https://script.google.com) that logs entries into Google Sheets.

---

## 🧰 Technologies Used

- Python 3.x
- `python-telegram-bot` (v13)
- `requests`
- OCR.Space API
- Google Apps Script (for data storage)

---

## 📦 Setup Instructions

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/vote-count-bot.git
cd vote-count-bot
