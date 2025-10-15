document.addEventListener('DOMContentLoaded', function() {
    const video = document.getElementById('video');
    const canvas = document.getElementById('canvas');
    const snap = document.getElementById('snap');
    const resultDiv = document.getElementById('result');

    // Camera access
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
        navigator.mediaDevices.getUserMedia({ video: true }).then(function(stream) {
            video.srcObject = stream;
            video.play();
        });
    }

    snap.addEventListener('click', function() {
        canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
        canvas.toBlob(function(blob) {
            let formData = new FormData();
            formData.append('image', blob, 'capture.jpg');
            fetch('/upload', {
                method: 'POST',
                body: formData
            })
            .then(res => res.json())
            .then(data => {
                if (data.error) {
                    resultDiv.textContent = "Error: " + data.error;
                    resultDiv.style.color = "red";
                } else {
                    resultDiv.textContent = `Vehicle: ${data.number} | Status: ${data.status}`;
                    resultDiv.style.color = data.status === "Authorized" ? "green" : "red";
                }
                if (data.result && !data.result.is_authorized) {
                    document.getElementById('siren').play();
                }
            })
            .catch(() => {
                resultDiv.textContent = "Upload failed.";
                resultDiv.style.color = "red";
            });
        }, 'image/jpeg');
    });
});