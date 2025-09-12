from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os

app = Flask(__name__)

# NOTE: For a production environment, it is highly recommended to use environment variables
# instead of hardcoding API keys for security.
API_KEY = "AIzaSyApGfglwT0LOAOBLN4CQOaDqmtgDlLKn-k"

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat()

@app.route("/")
def home():
    """Serves the main HTML page for the chatbot interface."""
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    """
    Handles user messages and sends them to the HealthBot model.
    Returns the bot's response as a JSON object.
    """
    user_input = request.json.get("message")
    
    # Check for empty input to prevent unnecessary API calls
    if not user_input or user_input.strip() == "":
        return jsonify({"reply": "Please enter a message to chat."})

    try:
        # Send the user's message to the chat model.
        response = chat.send_message(user_input)
        
        # Extract the text from the response.
        bot_text = getattr(response, "text", "")
        
        # If no text is found, try to get the last message.
        if not bot_text:
            bot_text = getattr(response, "last", "")
        
    except Exception as e:
        print(f"An error occurred: {e}")
        bot_text = "Sorry, something went wrong. Please try again later."
    
    return jsonify({"reply": bot_text})
