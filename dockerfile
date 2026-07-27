FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Set environment variable (can be overridden at runtime)
ENV BOT_TOKEN="YOUR_BOT_TOKEN_HERE"

# Health check endpoint (will run alongside the bot)
EXPOSE 8080

# Run the bot (polling mode)
CMD ["python", "bot.py"]
