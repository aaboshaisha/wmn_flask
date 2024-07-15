from flask import (Blueprint, render_template, request, current_app, g, flash, redirect, url_for,
                   jsonify, session, render_template_string)
import io
from openai import OpenAI
from .assistants import *
import anthropic
import re
from myapp.auth import login_required
from myapp.usage import calculate_and_update_audio_length, calculate_and_update_word_count
from pydub import AudioSegment

assistants = {
    "patient_assistant": patient_assistant,
    "gp_assistant_1": gp_assistant_1,
    "gp_assistant_2": gp_assistant_2,
    "sbard_assistant": sbard_assistant,
    "custom_assistant": custom_assistant,
}


bp = Blueprint('notes', __name__, url_prefix='/notes')

@bp.route('/main', methods=['GET', 'POST'])
@login_required
def main():
    return render_template('notes/main.html')

import speech_recognition as sr
import tempfile
import os

# @bp.route('/transcribe', methods=['POST'])
# @login_required
# def transcribe():
#     openai_api_key = current_app.config.get('OPENAI_API_KEY')
#     if not openai_api_key:
#         return jsonify({"error": "OpenAI API key not found in app configuration"}), 500
#     openai_client = OpenAI(api_key=openai_api_key)
    
#     file = request.files['audio']
#     file_extension = file.filename.split('.')[-1].lower()
    
#     if file_extension == 'webm':
#         # WebM can be sent directly to OpenAI
#         buffer = io.BytesIO(file.read())
#         buffer.name = "audio.webm"
#     elif file_extension == 'mp4':
#         # Convert MP4 to WebM
#         audio = AudioSegment.from_file(io.BytesIO(file.read()), format="mp4")
#         buffer = io.BytesIO()
#         audio.export(buffer, format="webm")
#         buffer.name = "audio.webm"
#         buffer.seek(0)
#     else:
#         return jsonify({"error": "Unsupported file format"}), 400
    
#     calculate_and_update_audio_length(buffer)
    
#     transcription = openai_client.audio.transcriptions.create(model='whisper-1', file=buffer)
#     return {'output': transcription.text}

@bp.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    r = sr.Recognizer()
    if 'audio' not in request.files: return jsonify({'error': 'No audio file provided'}), 400
    audio_file = request.files['audio']
    
    with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as temp_audio:
        audio_file.save(temp_audio.name)
        temp_audio_path = temp_audio.name
    
    try:
        with sr.AudioFile(temp_audio_path) as source:
            audio_data = r.record(source)
        
        # Use Whisper API for transcription
            openai_api_key = current_app.config.get('OPENAI_API_KEY')
            if not openai_api_key: return jsonify({"error": "OpenAI API key not found in app configuration"}), 500
        text = r.recognize_whisper_api(audio_data, api_key=openai_api_key)
        return jsonify({'output': text})
    except sr.RequestError as e:
        return jsonify({'error': f'Could not request results from Whisper API; {str(e)}'}), 500
    finally:
        os.unlink(temp_audio_path)


@bp.route("/select_assistant", methods=['POST'])
@login_required
def select_assistant():
    """Stores selected assistant in session for later use."""
    selected_assistant = request.form.get('assistant', 'sbard_assistant')
    session['selected_assistant'] = selected_assistant
    
    if selected_assistant == 'custom_assistant':
        return render_template('/notes/custom_notes_partial.html')
    else:
        return render_template_string("""
        <div class="submit-container">
                <button id="send-transcription" 
                        class="action-button primary"
                        hx-post="/notes/handle_assistant" 
                        hx-target="#assistant-output"
                        hx-include="[name=transcription-output]"
                        hx-indicator="#spinner">
                    Submit
                </button>
                <img id="spinner" class="htmx-indicator" src="{{ url_for('static', filename='bars.svg') }}" alt="Loading...">
            </div>
        """)

def get_claude_completion(clinical_notes, assistant, client, model="claude-3-haiku-20240307"):
    message = client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0,
        system="You are an expert in writing medical notes. NEVER speak about context. Only include information if provided in input text. JUST PROVIDE THE OUTPUT",
        messages=[ { "role": "user", "content": [ { "type": "text", "text": assistant(clinical_notes), } ] } ])
    # update usage measure
    total_word_count = message.usage.input_tokens + message.usage.output_tokens
    calculate_and_update_word_count(total_word_count)
    return message.content[0].text


@bp.route('/handle_assistant', methods=['POST'])
@login_required
def handle_assistant():
    anthropic_api_key = current_app.config.get('ANTHROPIC_API_KEY')
    if not anthropic_api_key:
        return jsonify({"error": "Anthropic API key not found in app configuration"}), 500
    
    anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
    
    selected_assistant = session.get('selected_assistant')
    assistant = assistants[selected_assistant]

    if assistant == custom_assistant:
        note_sections = request.form.getlist('sections')
        writing_style = request.form.get('writing_style', '')
        assistant = assistant(SECTIONS_FORMATTED=note_sections, WRITING_STYLE=writing_style)
    
    message = request.form.get('transcription-output') 
    if not message:
        return jsonify({"error": "No transcription found"}), 400

    response = get_claude_completion(clinical_notes=message, assistant=assistant,client=anthropic_client)
    
    return render_template('notes/output_partial.html', output = response)
