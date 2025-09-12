import google.generativeai as genai
from colorama import init, Fore, Style

init(autoreset=True)

genai.configure(api_key="AIzaSyApGfglwT0LOAOBLN4CQOaDqmtgDlLKn-k")
model = genai.GenerativeModel("gemini-1.5-flash")
chat = model.start_chat(history=[])

print(Fore.GREEN + "HealthBot: Hello! I'm here to talk about health and wellness. (Type 'exit' to quit)")

log_file = open("chat_log.txt", "a", encoding="utf-8")

while True:
    try:
        user_input = input(Fore.CYAN + "You: " + Style.RESET_ALL)
        if user_input.lower() in ["exit", "quit", "bye", "good bye", "see you later"]:
            print(Fore.GREEN + "HealthBot: Take care! Stay healthy!")
            log_file.write("User exited the chat.\n\n")
            break

        response = chat.send_message(user_input)
        bot_text = response.text.strip()
        print(Fore.GREEN + "HealthBot:", bot_text)

        log_file.write(f"You: {user_input}\nHealthBot: {bot_text}\n\n")

    except Exception as e:
        print(Fore.RED + "HealthBot: Sorry, something went wrong. Please try again.")
        log_file.write(f"Error: {str(e)}\n")

log_file.close()