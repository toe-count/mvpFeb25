import os
import json
import time
from openai import OpenAI
from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from pathlib import Path
from response_event_handler import ResponseEventHandler  # Handles AI assistant responses

# Load environment variables
load_dotenv()

api_key = os.getenv('OPENAI_API_KEY')
client = OpenAI(api_key=api_key)
assistant_id = "asst_eHC0t0DO2XFrRWIKT8SC3fp6"

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=[
    "http://localhost:5500"
])


@app.route("/")
def serve_index():
    # Serve index.html from the 'static' folder
    return send_from_directory(app.static_folder, "index.html")

@app.route('/hello')
def hello():
    return {"message": "Hello from your Flask app for chatting with an AI Assistant!"}

@app.route('/')
def home():
    return jsonify({"status": "API is running"}), 200

@app.route('/start_thread', methods=['POST'])
def start_thread_endpoint():
    print("We touched the endpoint")
    try:
        thread = client.beta.threads.create()
        return jsonify({'thread_id': thread.id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/set_assistant_id', methods=['POST'])
def set_assistant_id():
    global assistant_id 
    assistant_id = request.json.get('assistant_id')
    if not assistant_id:
        return jsonify({"error": "Assistant ID is required"}), 400
    app.logger.info(f"Switching to assistant with ID: {assistant_id}")
    return jsonify({"message": f"Switched to assistant with ID: {assistant_id}"}), 200

@app.route('/send_message', methods=['POST'])
def send_message_endpoint():
    data = request.json
    thread_id = data.get('thread_id')
    message = data.get('message')
    
    if not thread_id or not message:
        return jsonify({"error": "Missing thread_id or message"}), 400

    app.logger.info(f"Received message: {message}")

    def run_assistant_query(thread_id, query):
        try:
            runs = client.beta.threads.runs.list(thread_id=thread_id)
            active_runs = [run for run in runs if run.status in ['in_progress', 'requires_action']]
            for active_run in active_runs:
                client.beta.threads.runs.terminate(thread_id=thread_id, run_id=active_run.id)

            client.beta.threads.messages.create(thread_id=thread_id, role="user", content=query)
            
            event_handler = ResponseEventHandler()
            with client.beta.threads.runs.stream(
                thread_id=thread_id, assistant_id=assistant_id, event_handler=event_handler
            ) as stream:
                stream.until_done()
            
            return event_handler
        except Exception as e:
            app.logger.error(f"Error running assistant query: {str(e)}")
            return None

    def event_stream():
        event_handler = run_assistant_query(thread_id, message)
        if not event_handler:
            yield f"event: error\ndata: Error processing request\n\n"
            return
        for token in event_handler.response_text:
            yield f"event: message\ndata: {token}\n\n"
        yield "event: end\ndata: Stream closed\n\n"

    return Response(stream_with_context(event_stream()), content_type='text/event-stream',
                    headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

if __name__ == "__main__":
    # Note: Render sets PORT environment variable to 10000 or 3000, but we’ll just use 8000 locally
    app.run(host='0.0.0.0', port=8000)
