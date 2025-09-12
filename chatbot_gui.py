import tkinter as tk
import google.generativeai as genai

genai.configure(api_key="AIzaSyApGfglwT0LOAOBLN4CQOaDqmtgDlLKn-k")
model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat()

def send_message():
    user_msg = entry.get()
    chatbox.insert(tk.END, f"You: {user_msg}\n")
    entry.delete(0, tk.END)
    
    try:
        response = chat.send_message(user_msg)
        bot_text = getattr(response, "text", "") or getattr(response, "last", "")
    except:
        bot_text = "Sorry, something went wrong."
    chatbox.insert(tk.END, f"HealthBot: {bot_text}\n")

root = tk.Tk()
root.title("HealthBot")

chatbox = tk.Text(root, width=60, height=20)
chatbox.pack()

entry = tk.Entry(root, width=50)
entry.pack(side=tk.LEFT)

send_button = tk.Button(root, text="Send", command=send_message)
send_button.pack(side=tk.LEFT)

root.mainloop()
