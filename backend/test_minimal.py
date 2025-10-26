print("1. Starting imports...")

from flask import Flask
print("2. Flask imported")

from flask_cors import CORS
print("3. CORS imported")

from dotenv import load_dotenv
print("4. dotenv imported")

import os
load_dotenv()
print("5. .env loaded")

# First import the agent (before configuring genai)
from agents import RecordsWranglerAgent
print("6. Agents imported")

# Then configure genai (this will configure the model for the agent)
import google.generativeai as genai
genai.configure(api_key=os.getenv('GEMINI_API_KEY'))
print("7. Genai configured")

app = Flask(__name__)
CORS(app)
print("9. Flask app created")

@app.route('/health')
def health():
    return {"status": "ok"}

print("10. Route defined")

if __name__ == '__main__':
    print("11. Starting Flask...")
    app.run(debug=True, port=5000)