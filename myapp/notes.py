from flask import (Blueprint, render_template, request, current_app, g, flash, redirect, url_for,
                   jsonify, session, render_template_string)
from .assistants import *
import anthropic
from myapp.auth import login_required
from myapp.usage import calculate_and_update_audio_length, calculate_and_update_word_count
import speech_recognition as sr
import tempfile
import os

assistants = {
    "patient_assistant": patient_assistant,
    "gp_assistant_1": gp_assistant_1,
    "gp_assistant_2": gp_assistant_2,
    "sbard_assistant": sbard_assistant,
    "custom_assistant": custom_assistant,
    "create_your_own_assistant": create_your_own_assistant,
}


bp = Blueprint('notes', __name__, url_prefix='/notes')

@bp.route('/main', methods=['GET', 'POST'])
@login_required
def main():
    return render_template('notes/main.html')


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
        calculate_and_update_audio_length(temp_audio_path)
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
        return render_template('/notes/assistant_submit_button.html')
    
@bp.route("/select_mode")
@login_required
def select_mode():
    mode = request.args.get('mode')
    if mode == 'templates': return render_template('/notes/template_dropdown_partial.html')
    elif mode == 'custom': return render_template('/notes/create_your_own_partial.html')

def get_claude_completion(clinical_notes, assistant, client, model="claude-3-haiku-20240307"):
    message = client.messages.create(
        model=model,
        max_tokens=1000,
        temperature=0,
        system="You are a clinician who is expert in writing medical notes. Write in active voice. NEVER speak about context. Only include information if provided in input text. JUST PROVIDE THE OUTPUT",
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
    
    if 'create_your_own_assistant' in request.form: # if create-your-own-asssistant
        assistant_key = request.form['create_your_own_assistant']
        occupation = request.form.get('occupation')
        note_sections = request.form.get('sections')
        writing_style = request.form.get('writing_style')
        assistant_fn = assistants[assistant_key]
        assistant = assistant_fn(OCCUPATION=occupation, SECTIONS_FORMATTED=note_sections, WRITING_STYLE=writing_style)
        

    else: # if using template dorpdown menu
        selected_assistant = session.get('selected_assistant')
        assistant = assistants[selected_assistant]

        if assistant == custom_assistant:
            note_sections = request.form.getlist('sections')
            writing_style = request.form.get('writing_style', '')
            assistant = assistant(SECTIONS_FORMATTED=note_sections, WRITING_STYLE=writing_style)
    
    print(assistant)
    message = request.form.get('transcription-output') 
    if not message:
        return jsonify({"error": "No transcription found"}), 400

    response = get_claude_completion(clinical_notes=message, assistant=assistant,client=anthropic_client)
    
    return render_template('notes/output_partial.html', output = response)
