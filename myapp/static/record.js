let recognition;
let isRecording = false;
const recordButton = document.getElementById('record-button');
const status = document.getElementById('status');
const result = document.getElementById('transcription-output');

recordButton.addEventListener('click', toggleRecording);
result.addEventListener('input', updateTranscription);

let finalTranscript = '';
let interimTranscript = '';

function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
}

function startRecording() {
    recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
    recognition.lang = 'en-US';
    recognition.interimResults = true;
    recognition.continuous = true;
    recognition.maxAlternatives = 1;

    recognition.onresult = function(event) {
        interimTranscript = '';
        for (let i = event.resultIndex; i < event.results.length; ++i) {
            if (event.results[i].isFinal) {
                finalTranscript += event.results[i][0].transcript + ' ';
            } else {
                interimTranscript += event.results[i][0].transcript;
            }
        }
        
        updateDisplay();
    };

    recognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        status.textContent = 'Error: ' + event.error;
    };

    recognition.onend = function() {
        if (isRecording) {
            recognition.start();
        } else {
            recordButton.textContent = 'Start Recording';
            status.textContent = '';
        }
    };

    recognition.start();
    isRecording = true;
    recordButton.textContent = 'Stop Recording';
    status.textContent = 'Recording...';
}

function stopRecording() {
    if (recognition) {
        isRecording = false;
        recognition.stop();
    }
}

function updateTranscription() {
    const currentText = result.value;
    const lastSpaceIndex = currentText.lastIndexOf(' ');
    
    if (lastSpaceIndex !== -1) {
        finalTranscript = currentText.substring(0, lastSpaceIndex + 1);
        interimTranscript = currentText.substring(lastSpaceIndex + 1);
    } else {
        finalTranscript = '';
        interimTranscript = currentText;
    }
}

function updateDisplay() {
    result.value = finalTranscript + interimTranscript;
    result.scrollTop = result.scrollHeight;
}


function clearTranscription() {
    finalTranscript = '';
    interimTranscript = '';
    result.value = '';
    if (recognition) {
        recognition.abort();
    }
    isRecording = false;
    recordButton.textContent = 'Start Recording';
    status.textContent = '';
}

const clearButton = document.getElementById('clear-button');
clearButton.addEventListener('click', clearTranscription);