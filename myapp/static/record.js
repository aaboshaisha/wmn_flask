const record = document.getElementById('record-button');
const output = document.getElementById('transcription-output');

const onMediaSuccess = function (stream) {
    const options = { mimeType: 'audio/webm;codecs=opus' }; // new line
    const mediaRecorder = new MediaRecorder(stream, options); // new line
    // const mediaRecorder = new MediaRecorder(stream);
    record.onclick = function () {
        if (mediaRecorder.state == 'recording') {
            mediaRecorder.stop(); record.style.background = ""; record.style.color = "";
        } else {
            mediaRecorder.start(); record.style.background = "red"; record.style.color = "black";
        }
    }
    let chunks = [];
    mediaRecorder.ondataavailable = function (e) { chunks.push(e.data); }
    mediaRecorder.onstop = function () {
        // let blob = new Blob(chunks, { type: "audio/webm" });
        let blob = new Blob(chunks, { type: "audio/webm;codecs=opus" }); // new line
        chunks = [];
        let formData = new FormData();
        formData.append("audio", blob, "audio.webm");
        fetch("/notes/transcribe", { method: "POST", body: formData })
            .then((response) => response.json())
            .then((data) => { output.value += data.output + "\n"; })
            .catch((error) => { console.error('Error:', error); });
    }
}

const onMediaFailure = function (err) { alert(err); }

if (navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(onMediaSuccess)
        .catch(onMediaFailure);
} else {
    alert("getUserMedia is not supported on your browser.");
}