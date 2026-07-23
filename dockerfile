FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

CMD ["python", "bot.py"]
