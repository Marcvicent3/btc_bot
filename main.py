from bot import app
from flask import Flask
import threading

# Crea un pequeño servidor web
web_app = Flask('')

@web_app.route('/')
def home():
    return "Bot de BTC activo ✅"

def run_web():
    web_app.run(host='0.0.0.0', port=3000)

# Lanza Flask en un hilo aparte
threading.Thread(target=run_web).start()

if __name__ == "__main__":
    # Arranca el bot (polling) y mantiene el loop abierto
    app.run_polling()
