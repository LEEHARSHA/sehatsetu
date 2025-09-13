from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os, json, datetime

app = Flask(__name__)

# ===================== File Paths =====================
HISTORY_FILE = "chat_history.json"
USER_DATA_FILE = "user_data.json"
LOG_FILE = "chat_log.txt"

# ===================== Helper Functions =====================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def save_history(history):
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=4)

def load_user_data():
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {"profile": {}, "appointments": [], "emergency": [], "medications": []}
    return {"profile": {}, "appointments": [], "emergency": [], "medications": []}

def save_user_data(data):
    with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

# ===================== AI Setup =====================
API_KEY = os.getenv("GOOGLE_API_KEY")
if not API_KEY:
    raise ValueError("⚠️ GOOGLE_API_KEY is not set.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

chat = model.start_chat(history=[])

# ===================== Routes =====================
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    user_input = request.json.get("message", "")
    if not user_input.strip():
        return jsonify({"reply": "⚠️ Please enter a message."})

    try:
        response = chat.send_message(user_input)
        bot_text = getattr(response, "text", "") or getattr(response, "last", "")

        history = load_history()
        history.append({"user": user_input, "bot": bot_text})
        save_history(history)

        with open(LOG_FILE, "a", encoding="utf-8") as log:
            log.write(f"[{datetime.datetime.now()}]\nYou: {user_input}\nHealthBot: {bot_text}\n\n")

    except Exception as e:
        bot_text = f"Sorry, something went wrong: {e}"

    return jsonify({"reply": bot_text})

@app.route("/get_history", methods=["GET"])
def get_history():
    return jsonify(load_history())

@app.route("/edit_message/<int:index>", methods=["PUT"])
def edit_message(index):
    history = load_history()
    if 0 <= index < len(history):
        new_message = request.json.get("message", "")
        if not new_message.strip():
            return jsonify({"status": "error", "message": "Message cannot be empty"}), 400

        try:
            response = chat.send_message(new_message)
            bot_text = getattr(response, "text", "") or getattr(response, "last", "")
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500

        history[index] = {"user": new_message, "bot": bot_text}
        save_history(history)
        return jsonify({"status": "success", "reply": bot_text})
    return jsonify({"status": "error", "message": "Message not found"}), 404

@app.route("/delete_message/<int:index>", methods=["DELETE"])
def delete_message(index):
    history = load_history()
    if 0 <= index < len(history):
        history.pop(index)
        save_history(history)
        return jsonify({"status": "success"})
    return jsonify({"status": "error", "message": "Message not found"}), 404

@app.route("/clear_chat", methods=["DELETE"])
def clear_chat():
    save_history([])
    return jsonify({"status": "success", "message": "Chat cleared!"})

# ===================== Profile, Medications, Emergency =====================
@app.route("/get_user_data", methods=["GET"])
def get_user_data():
    return jsonify(load_user_data())

@app.route("/save_profile", methods=["POST"])
def save_profile():
    data = load_user_data()
    profile_data = request.json
    profile_data['custom_fields'] = profile_data.get('custom_fields', [])
    data["profile"] = profile_data
    save_user_data(data)
    return jsonify({"status": "success", "message": "Profile saved!", "data": profile_data})

@app.route("/save_medication", methods=["POST"])
def save_medication():
    data = load_user_data()
    medication = request.json
    if "medications" not in data:
        data["medications"] = []
    data["medications"].append(medication)
    save_user_data(data)
    return jsonify({"status": "success", "message": "Medication added!"})

@app.route("/delete_medication/<int:index>", methods=["DELETE"])
def delete_medication(index):
    data = load_user_data()
    if 0 <= index < len(data.get("medications", [])):
        data["medications"].pop(index)
        save_user_data(data)
        return jsonify({"status": "success", "message": "Medication deleted."})
    return jsonify({"status": "error", "message": "Medication not found."}), 404

@app.route("/save_emergency_contact", methods=["POST"])
def save_emergency_contact():
    data = load_user_data()
    contact = request.json
    if "emergency_contacts" not in data:
        data["emergency_contacts"] = []
    data["emergency_contacts"].append(contact)
    save_user_data(data)
    return jsonify({"status": "success", "message": "Emergency contact added!"})

@app.route("/delete_emergency_contact/<int:index>", methods=["DELETE"])
def delete_emergency_contact(index):
    data = load_user_data()
    if 0 <= index < len(data.get("emergency_contacts", [])):
        data["emergency_contacts"].pop(index)
        save_user_data(data)
        return jsonify({"status": "success", "message": "Emergency contact deleted."})
    return jsonify({"status": "error", "message": "Emergency contact not found."}), 404

# ===================== Run =====================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)