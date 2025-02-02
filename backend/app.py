import os
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from openai import OpenAI
from dotenv import load_dotenv
import re
import nltk

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

app = Flask(__name__)
CORS(app)

# We have a pre-existing assistant ID
ASSISTANT_ID = "asst_eHC0t0DO2XFrRWIKT8SC3fp6"  # <-- Update to your actual ID

@app.route("/")
def serve_index():
    return send_from_directory(app.static_folder, "index.html")

###################################
# 1) Create a new Thread
###################################
@app.route("/start_thread", methods=["POST"])
def start_thread():
    """
    Creates an ephemeral thread for the user.
    Returns: { "thread_id": "thrd_..." }
    """
    try:
        thread = client.beta.threads.create()
        return jsonify({"thread_id": thread.id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

###################################
# 2) Send user message & get assistant response
###################################

def make_it_normal(text: str) -> str:
    """
    A hacky approach to turn:
      "HelloHello!Yes,I'mhere.HowcanIassistyoutoday?"
    into:
      "Hello! Yes, I'm here. How can I assist you today?"
    """

    # 1) Insert spaces around punctuation like . , ! ? so we can tokenize effectively
    #    e.g., "HelloHello!Yes" => "HelloHello ! Yes"
    text = re.sub(r'([,.!?])([^\s])', r'\1 \2', text)  # Insert space after punctuation if missing
    text = re.sub(r'([^\s])([,.!?])', r'\1 \2', text)  # Insert space before punctuation if missing
    # => "HelloHello ! Yes , I'mhere . HowcanIassistyoutoday ?"

    # 2) Tokenize with nltk
    tokens = nltk.word_tokenize(text)
    # Example tokens: ["HelloHello", "!", "Yes", ",", "I", "'m", "here", ".", "HowcanIassistyoutoday", "?"]

    # 3) Fix repeated words like "HelloHello" => "Hello"
    def fix_repeated_word(tok: str) -> str:
        # e.g. if it matches a repeated pattern (HelloHello => group(1)=Hello)
        # This is a naive approach: it only detects EXACT repeated alpha substrings
        match = re.match(r'^([A-Za-z]+)\1$', tok)
        if match:
            return match.group(1)
        return tok

    fixed_tokens = [fix_repeated_word(t) for t in tokens]

    # 4) Handle known merges like "I'mhere" => ["I'm", "here"]
    #    and "HowcanIassistyoutoday" => ["How", "can", "I", "assist", "you", "today"]
    def split_known_merges(tok: str) -> list[str]:
        lower = tok.lower()
        if lower == "i'mhere":
            return ["I'm", "here"]
        if lower == "howcaniassistyoutoday":
            return ["How", "can", "I", "assist", "you", "today"]
        return [tok]

    final_tokens = []
    for t in fixed_tokens:
        final_tokens.extend(split_known_merges(t))

    # 5) Re-join tokens with a space
    #    => "HelloHello ! Yes , I 'm here . How can I assist you today ?"
    text = " ".join(final_tokens)

    # 6) Remove space before punctuation to get a more natural look
    #    => "HelloHello! Yes, I'm here. How can I assist you today?"
    text = re.sub(r'\s+([,.!?])', r'\1', text)

    # If "HelloHello" was still present, the repeated-word fix might not catch partial merges.
    # This is just an example of further custom logic.

    # 7) Convert double/triple spaces to single space
    text = re.sub(r'\s+', ' ', text).strip()

    return text

    return text
@app.route("/send_message", methods=["POST"])
def send_message():
    """
    Expects JSON:
      {
        "thread_id": "thrd_...",
        "message": "Hello assistant!"
      }
    1. Adds the user message to the thread.
    2. Runs the thread with the existing assistant, blocking until complete (no streaming).
    3. Returns the assistant's final message in JSON.
    """
    data = request.json
    thread_id = data.get("thread_id")
    user_message = data.get("message")

    if not thread_id or not user_message:
        return jsonify({"error": "Missing thread_id or message"}), 400

    try:
        # A) Add user message to the Thread
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=user_message
        )

        # B) Create a synchronous Run using create_and_poll (no streaming)
        run = client.beta.threads.runs.create_and_poll(
            thread_id=thread_id,
            assistant_id=ASSISTANT_ID
        )

        if run.status != "completed":
            return jsonify({"error": f"Run not completed. Status: {run.status}"}), 500

        # C) Once completed, fetch all messages in the thread
        messages = client.beta.threads.messages.list(thread_id=thread_id)

        # Find the last assistant message
        # (We assume the assistant's final response is the last message with role='assistant')
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        if not assistant_msgs:
            return jsonify({"error": "No assistant messages found."}), 500

        final_msg = assistant_msgs[-1].content

        return jsonify({"assistant_message": cleaned_msg}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    # For local dev only; Render sets PORT automatically
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port, debug=True)
