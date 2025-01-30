document.addEventListener("DOMContentLoaded", () => { 
  const canvas = document.getElementById("canvas");  
  const ctx = canvas.getContext("2d");

  // Set canvas dimensions
  canvas.width = 640;
  canvas.height = 480;

  // Start the video stream and draw it directly on the canvas
  navigator.mediaDevices
    .getUserMedia({ video: true })
    .then((stream) => {
      const video = document.createElement("video"); // Create a hidden video element to capture frames
      video.srcObject = stream;
      video.play();

      // Draw video frames onto the canvas
      const drawVideoFrame = () => {
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        requestAnimationFrame(drawVideoFrame); // Keep updating the canvas
      };
      drawVideoFrame();
    })
    .catch((err) => console.error("Error accessing webcam:", err));

  // Fetch attendance log from backend
  const fetchAttendanceLog = () => {
    fetch("/get-attendance")
      .then((response) => response.json())
      .then((data) => {
        const tbody = document.getElementById("attendance-tbody");
        tbody.innerHTML = ""; // Clear previous data
        data.attendance.forEach((log) => {
          const row = document.createElement("tr");
          row.innerHTML = `
            <td>${log.time}</td>
            <td>${log.name}</td>
            <td>Present</td>
          `;
          tbody.appendChild(row);
        });
      })
      .catch((err) => console.error("Error fetching attendance log:", err));
  };

  // Send captured frame to backend for face recognition
  const sendFrameForRecognition = (frame) => {
    fetch("/process-image", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ image: frame }),
    })
      .then((response) => response.json())
      .then((data) => {
        // Clear the canvas and redraw video frame
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(canvas, 0, 0, canvas.width, canvas.height);

        // Draw rectangles and labels for recognized faces
        data.recognized_faces.forEach((face) => {
          const { top, right, bottom, left, name } = face;

          // Draw a red rectangle around the face
          ctx.strokeStyle = "red";
          ctx.lineWidth = 2;
          ctx.strokeRect(left, top, right - left, bottom - top);

          // Draw the name below the face
          ctx.fillStyle = "red";
          ctx.font = "16px Arial";
          ctx.fillText(name, left, bottom + 20); // Place the text below the face
        });

        // Show toast notification when new attendance is recorded
        if (data.new_attendance) {
          const toast = document.createElement('div');
          toast.className = 'toast-notification';
          toast.textContent = `New attendance recorded for: ${data.recognized_faces[0].name}`;
          document.body.appendChild(toast);

          // Remove the toast after animation completes
          setTimeout(() => {
            toast.remove();
          }, 3000);

          fetchAttendanceLog();
        }
      })
      .catch((err) => console.error("Error processing image:", err));
  };

  // Process video frames at intervals
  setInterval(() => {
    const frame = canvas.toDataURL("image/png"); // Capture canvas frame as image
    sendFrameForRecognition(frame);
  }, 1000); // Process frame every 1 second

  // Initial fetch of attendance log
  fetchAttendanceLog();
});

document.getElementById("exportData").addEventListener("click", () => {
  fetch("/export-attendance")
    .then(response => {
      if (response.ok) {
        return response.blob();
      } else {
        throw new Error("Failed to export data");
      }
    })
    .then(blob => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "attendance.csv";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
    })
    .catch(err => console.error(err));
});
