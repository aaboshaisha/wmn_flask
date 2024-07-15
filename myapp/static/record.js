
let recorder;
let isRecording = false;
const recordButton = document.getElementById('record-button');
const status = document.getElementById('status');
const result = document.getElementById('transcription-output');

recordButton.addEventListener('click', toggleRecording);

function toggleRecording() {
    if (isRecording) {
        stopRecording();
    } else {
        startRecording();
    }
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
        });
}

function stopRecording() {
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