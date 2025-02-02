import os
import json
import time
from functools import lru_cache
from openai import OpenAI
from flask import Flask, request, jsonify, Response, stream_with_context, make_response
from flask_cors import CORS
from dotenv import load_dotenv
from pathlib import Path
from firebase_admin import firestore, auth
from datetime import datetime, timedelta, timezone
from response_event_handler import ResponseEventHandler
import stripe
load_dotenv() # get env variables from .env file

api_key = os.getenv('OPENAI_API_KEY').replace("'", "")
client = OpenAI(api_key=api_key)
assistant_id = "asst_dlHW5pVVkce0IWgKZzz77tTm"

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=[
    "http://localhost:5173" # or any other frontend URL
])
@app.route('/start_thread', methods=['POST'])
def start_thread_endpoint():
    def create_thread():
        thread = client.beta.threads.create()
        return thread.id
    thread_id = create_thread()
    return jsonify({'thread_id': thread_id})

@app.route('/set_assistant_id', methods=['POST'])
def set_assistant_id():
    global assistant_id 
    assistant_id = request.json.get('assistant_id')
    if not assistant_id:
        return jsonify({"error": "Assistant ID is required"}), 400
    # Logic to handle setting the assistant_id goes here
    print(f"Switching to assistant with ID: {assistant_id}")
    return jsonify({"message": f"Switched to assistant with ID: {assistant_id}"}), 200

@app.route('/send_message', methods=['GET'])
def send_message_endpoint():
    # Extract thread_id and message from query parameters (GET request)
    thread_id = request.args.get('thread_id')
    message = request.args.get('message')
    print("Message from frontend: ", message)
    def run_assistant_query(thread_id, query):
        runs = client.beta.threads.runs.list(thread_id=thread_id)
        active_runs = [run for run in runs if run.status in ['in_progress', 'requires_action']]
        if active_runs:
            for active_run in active_runs:
                client.beta.threads.runs.terminate(
                    thread_id=thread_id,
                    run_id=active_run.id
                )
        client.beta.threads.messages.create(
            thread_id=thread_id,
            role="user",
            content=query,
        )
        event_handler = ResponseEventHandler()
        with client.beta.threads.runs.stream(
            thread_id=thread_id,
            assistant_id=assistant_id,
            event_handler=event_handler
        ) as stream:
            stream.until_done()
        return event_handler
    # Stream the assistant response as it's generated
    def event_stream():
        event_handler = run_assistant_query(thread_id, message)
        skip_first_token = True  # Flag to skip the first token
        for token in event_handler.response_text:
            if skip_first_token:
                skip_first_token = False  # Skip the first token
                continue  # Move to the next token without yielding
            # Stream each subsequent token immediately
            yield f"data: {token}\n\n"
        # End the stream with an 'end' event
        yield "event: end\ndata: Stream closed\n\n"
    # Return a streaming response using stream_with_context
    return Response(stream_with_context(event_stream()), content_type='text/event-stream')

