#!/bin/bash
# Запускает бота + веб-сервер для health check (чтобы Space не спал)

python -c "
from flask import Flask
import threading, os

app = Flask(__name__)

@app.route('/')
def health():
    return 'OK', 200

@app.route('/health')
def health_check():
    return 'OK', 200

def run_bot():
    os.system('python Bot.py')

t = threading.Thread(target=run_bot, daemon=True)
t.start()
app.run(host='0.0.0.0', port=7860)
"
