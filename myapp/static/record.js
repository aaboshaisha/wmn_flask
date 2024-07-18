let recorder;
let isRecording = false;
let recordingStartTime;
let recordingTimer;
const recordButton = document.getElementById('record-button');
const status = document.getElementById('status');
const result = document.getElementById('transcription-output');

// Functions to show hints to user when recording for too long
const warningElement = document.getElementById('warning'); // Add this element to your HTML
let warningTimeout;

function startRecordingTimer() {
    recordingTimer = setInterval(() => {
        const duration = (Date.now() - recordingStartTime) / 1000;
        if (duration > 10) { showWarning(); } }, 1000);
}

function showWarning() {
    warningElement.textContent = 'Hint: Record in small chunks to get faster and better responses.';
    warningElement.classList.add('active');
    
    if (warningTimeout) { clearTimeout(warningTimeout); } // Clear any existing timeout
    
    // Set a new timeout to hide the warning after 5 seconds
    warningTimeout = setTimeout(() => { hideWarning(); }, 5000); 
}

function hideWarning() {
    warningElement.textContent = '';
    warningElement.classList.remove('active');
}

// end of warning functions

recordButton.addEventListener('click', toggleRecording);

function toggleRecording() {
    if (isRecording) { stopRecording(); } 
    else { startRecording(); }
}

function startRecording() {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(function (stream) {
            recorder = RecordRTC(stream, {
                type: 'audio',
                mimeType: 'audio/webm',
                sampleRate: 44100,
                desiredSampRate: 16000,
                recorderType: RecordRTC.StereoAudioRecorder,
                numberOfAudioChannels: 1
            });
            recorder.startRecording();
            isRecording = true;
            recordButton.textContent = 'Stop Recording';
            status.textContent = 'Recording...';
            recordingStartTime = Date.now();
            startRecordingTimer();
        });
}


function stopRecording() {
    clearInterval(recordingTimer);
    hideWarning();
    if (warningTimeout) { clearTimeout(warningTimeout); }
    
    recorder.stopRecording(function () {
        let blob = recorder.getBlob();
        uploadAudio(blob);
        isRecording = false;
        recordButton.textContent = 'Start Recording';
        status.textContent = 'Processing...';
    });
}


function uploadAudio(blob) {
    let formData = new FormData();
    formData.append('audio', blob, 'recording.wav');

    fetch('/notes/transcribe', {
        method: 'POST',
        body: formData
    })
        .then(response => response.json())
        .then(data => {
            if (data.output) {
                result.value += data.output + "\n";
            } else if (data.error) {
                result.textContent = 'Error: ' + data.error;
            }

            status.textContent = '';
        })
        .catch(error => {
            console.error('Error:', error);
            result.textContent = 'An error occurred during transcription.';
            status.textContent = '';
        });
}