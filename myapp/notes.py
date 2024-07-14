from flask import (Blueprint, render_template, request, current_app, g, flash, redirect, url_for,
                   jsonify, session, render_template_string)
import io
from openai import OpenAI
from .assistants import *
import anthropic
import re
from myapp.auth import login_required
from myapp.usage import calculate_and_update_audio_length, calculate_and_update_word_count

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
    # if g.user['subscription_status'] == 'exceeded':
    #     flash('You have exceeded your usage limit. Please update your subscription to continue.', 'warning')
    #     return redirect(url_for('payment.customer_portal'))
    return render_template('notes/main.html')


@bp.route('/transcribe', methods=['POST'])
@login_required
def transcribe():
    openai_api_key = current_app.config.get('OPENAI_API_KEY')
    if not openai_api_key:
        return jsonify({"error": "OpenAI API key not found in app configuration"}), 500
    openai_client = OpenAI(api_key=openai_api_key)
    
    file = request.files['audio'] # get the audio file from request object
    buffer = io.BytesIO(file.read()) # read it and put in a format that openai can use
    buffer.name = "audio.webm"
    # update usage
    calculate_and_update_audio_length(buffer)
    
    transcription = openai_client.audio.transcriptions.create(model='whisper-1',file=buffer)
    return {'output': transcription.text}


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
