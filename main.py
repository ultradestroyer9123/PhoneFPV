from flask import Flask, request, jsonify, render_template_string
import threading

app = Flask(__name__)

PORT = 1234

# ------------------------------------------------------------
# WebRTC signaling state
# ------------------------------------------------------------

signal_lock = threading.Lock()

offer = None
answer = None


# ------------------------------------------------------------
# Settings
# ------------------------------------------------------------

settings = {
    "quality": 70,   # 10-100
    "fps": 30        # 1-60
}

settings_lock = threading.Lock()


# ------------------------------------------------------------
# PHONE PAGE
# ------------------------------------------------------------

PHONE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PhoneFPV - Phone</title>

    <style>
        body {
            background: #111;
            color: white;
            font-family: Arial, sans-serif;
            text-align: center;
            margin: 0;
            padding: 20px;
        }

        video {
            width: 100%;
            max-width: 900px;
            border-radius: 10px;
            background: black;
        }

        #status {
            margin: 15px;
            font-size: 18px;
        }
    </style>
</head>

<body>

<h1>PhoneFPV</h1>

<div id="status">Requesting camera...</div>

<video id="preview" autoplay playsinline muted></video>

<script>

const statusText = document.getElementById("status");
const preview = document.getElementById("preview");

let pc;
let videoTrack;


// ------------------------------------------------------------
// Wait until ICE gathering is complete
// ------------------------------------------------------------

function waitForIceGatheringComplete(pc) {

    return new Promise(resolve => {

        if (pc.iceGatheringState === "complete") {
            resolve();
            return;
        }

        function checkState() {

            if (pc.iceGatheringState === "complete") {
                pc.removeEventListener(
                    "icegatheringstatechange",
                    checkState
                );

                resolve();
            }
        }

        pc.addEventListener(
            "icegatheringstatechange",
            checkState
        );
    });
}


// ------------------------------------------------------------
// Poll for computer's answer
// ------------------------------------------------------------

async function waitForAnswer() {

    while (true) {

        try {

            const response = await fetch("/signal/answer");

            const data = await response.json();

            if (data.answer) {

                await pc.setRemoteDescription(
                    new RTCSessionDescription(data.answer)
                );

                statusText.textContent = "Connected";

                return;
            }

        } catch (error) {

            console.error(error);
        }

        await new Promise(resolve =>
            setTimeout(resolve, 500)
        );
    }
}


// ------------------------------------------------------------
// Get current settings
// ------------------------------------------------------------

async function updateSettings() {

    try {

        const response = await fetch("/settings");

        const data = await response.json();

        if (!videoTrack || !pc) {
            return;
        }

        const sender = pc.getSenders().find(
            sender => sender.track === videoTrack
        );

        if (!sender) {
            return;
        }

        const parameters = sender.getParameters();

        if (!parameters.encodings ||
            parameters.encodings.length === 0) {

            parameters.encodings = [{}];
        }

        const encoding = parameters.encodings[0];

        // FPS slider directly controls maximum FPS.
        encoding.maxFramerate = data.fps;

        // Convert quality percentage into an approximate bitrate.
        //
        // 10%  ≈ 250 kbps
        // 70%  ≈ 4.6 Mbps
        // 100% ≈ 8 Mbps
        //
        // This is NOT JPEG quality anymore.
        const minBitrate = 250_000;
        const maxBitrate = 8_000_000;

        const quality = data.quality / 100;

        encoding.maxBitrate =
            minBitrate +
            (maxBitrate - minBitrate) * quality;

        await sender.setParameters(parameters);

    } catch (error) {

        console.error("Settings error:", error);
    }
}


// ------------------------------------------------------------
// Main WebRTC setup
// ------------------------------------------------------------

async function start() {

    try {

        statusText.textContent =
            "Requesting camera permission...";

        const stream =
            await navigator.mediaDevices.getUserMedia({

                video: {
                    facingMode: {
                        ideal: "environment"
                    },

                    width: {
                        ideal: 1280
                    },

                    height: {
                        ideal: 720
                    },

                    frameRate: {
                        ideal: 30,
                        max: 60
                    }
                },

                audio: false
            });

        preview.srcObject = stream;

        videoTrack = stream.getVideoTracks()[0];

        statusText.textContent =
            "Camera ready. Waiting for computer...";


        // ----------------------------------------------------
        // Create peer connection
        // ----------------------------------------------------

        pc = new RTCPeerConnection({
            iceServers: []
        });


        // Add camera track
        pc.addTrack(videoTrack, stream);


        pc.onconnectionstatechange = () => {

            console.log(
                "Connection:",
                pc.connectionState
            );

            if (pc.connectionState === "connected") {

                statusText.textContent =
                    "Connected to computer";

            } else if (
                pc.connectionState === "disconnected" ||
                pc.connectionState === "failed"
            ) {

                statusText.textContent =
                    "Connection lost";
            }
        };


        // ----------------------------------------------------
        // Create offer
        // ----------------------------------------------------

        const offerDescription =
            await pc.createOffer();

        await pc.setLocalDescription(
            offerDescription
        );


        // Wait until ICE candidates have been added
        await waitForIceGatheringComplete(pc);


        // Send complete SDP offer to Flask
        await fetch("/signal/offer", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                offer: pc.localDescription
            })
        });


        // Wait for computer
        await waitForAnswer();


        // Apply settings immediately
        await updateSettings();

    } catch (error) {

        console.error(error);

        statusText.textContent =
            "Camera/WebRTC error: " + error.message;
    }
}


// ------------------------------------------------------------
// Check settings every 500 ms.
//
// This is ONLY one tiny request every half-second.
// It is NOT one request per video frame.
// ------------------------------------------------------------

setInterval(updateSettings, 500);

start();

</script>

</body>
</html>
"""


# ------------------------------------------------------------
# COMPUTER PAGE
# ------------------------------------------------------------

COMPUTER_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>PhoneFPV - Computer</title>

    <style>

        body {
            background: #111;
            color: white;
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }

        h1 {
            text-align: center;
        }

        #viewer {
            width: 100%;
            height: 65vh;

            display: flex;
            align-items: center;
            justify-content: center;

            overflow: hidden;

            background: #000;
            border-radius: 10px;

            position: relative;

            cursor: grab;
        }

        #viewer.dragging {
            cursor: grabbing;
        }

        video {
            width: 640px;
            max-width: none;

            background: black;
            border-radius: 5px;

            transform-origin: center center;

            user-select: none;
            -webkit-user-drag: none;

            position: absolute;
        }

        .controls {
            max-width: 700px;
            margin: 25px auto;
            background: #222;
            padding: 20px;
            border-radius: 10px;
        }

        .control {
            margin-bottom: 25px;
        }

        .label {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
        }

        input[type="range"] {
            width: 100%;
        }

        button {
            width: 100%;
            padding: 10px;
            border: none;
            border-radius: 6px;
            background: #444;
            color: white;
            font-size: 16px;
            cursor: pointer;
        }

        button:hover {
            background: #555;
        }

        #status {
            text-align: center;
            margin: 15px;
            font-size: 18px;
        }

    </style>
</head>

<body>

<h1>PhoneFPV</h1>

<div id="status">
    Waiting for phone...
</div>


<div id="viewer">

    <video
        id="video"
        autoplay
        playsinline
        muted>
    </video>

</div>


<div class="controls">

    <!-- QUALITY -->

    <div class="control">

        <div class="label">
            <span>Quality</span>
            <span id="qualityValue">70%</span>
        </div>

        <input
            id="quality"
            type="range"
            min="10"
            max="100"
            value="70"
        >

    </div>


    <!-- FPS -->

    <div class="control">

        <div class="label">
            <span>FPS</span>
            <span id="fpsValue">30 FPS</span>
        </div>

        <input
            id="fps"
            type="range"
            min="1"
            max="60"
            value="30"
        >

    </div>


    <!-- ROTATION -->

    <div class="control">

        <div class="label">
            <span>Rotation</span>
            <span id="rotationValue">0°</span>
        </div>

        <select id="rotation">
            <option value="0">0°</option>
            <option value="90">90°</option>
            <option value="180">180°</option>
            <option value="270">270°</option>
        </select>

    </div>


    <!-- SCALE -->

    <div class="control">

        <div class="label">
            <span>Scale</span>
            <span id="scaleValue">100%</span>
        </div>

        <input
            id="scale"
            type="range"
            min="25"
            max="200"
            value="100"
        >

    </div>


    <button id="reset">
        Reset Position / Rotation / Scale
    </button>

</div>


<script>

const viewer =
    document.getElementById("viewer");

const video =
    document.getElementById("video");

const statusText =
    document.getElementById("status");


// ------------------------------------------------------------
// Quality / FPS
// ------------------------------------------------------------

const quality =
    document.getElementById("quality");

const fps =
    document.getElementById("fps");

const qualityValue =
    document.getElementById("qualityValue");

const fpsValue =
    document.getElementById("fpsValue");


// ------------------------------------------------------------
// Video transform controls
// ------------------------------------------------------------

const rotation =
    document.getElementById("rotation");

const scale =
    document.getElementById("scale");

const rotationValue =
    document.getElementById("rotationValue");

const scaleValue =
    document.getElementById("scaleValue");

const resetButton =
    document.getElementById("reset");


let videoRotation = 0;
let videoScale = 1;

let videoX = 0;
let videoY = 0;


// ------------------------------------------------------------
// Apply transform
// ------------------------------------------------------------

function updateTransform() {

    video.style.transform =
        `translate(${videoX}px, ${videoY}px)
         rotate(${videoRotation}deg)
         scale(${videoScale})`;
}


// ------------------------------------------------------------
// Rotation
// ------------------------------------------------------------

rotation.addEventListener("input", () => {

    videoRotation =
        parseInt(rotation.value);

    rotationValue.textContent =
        videoRotation + "°";

    updateTransform();
});


// ------------------------------------------------------------
// Scale
// ------------------------------------------------------------

scale.addEventListener("input", () => {

    videoScale =
        parseInt(scale.value) / 100;

    scaleValue.textContent =
        scale.value + "%";

    updateTransform();
});


// ------------------------------------------------------------
// Reset
// ------------------------------------------------------------

resetButton.addEventListener("click", () => {

    videoRotation = 0;
    videoScale = 1;

    videoX = 0;
    videoY = 0;

    rotation.value = 0;
    scale.value = 100;

    rotationValue.textContent = "0°";
    scaleValue.textContent = "100%";

    updateTransform();
});


// Double click also resets
video.addEventListener("dblclick", () => {

    resetButton.click();

});


// ------------------------------------------------------------
// Dragging
// ------------------------------------------------------------

let dragging = false;

let dragStartX = 0;
let dragStartY = 0;

let originalX = 0;
let originalY = 0;


viewer.addEventListener("mousedown", (event) => {

    dragging = true;

    viewer.classList.add("dragging");

    dragStartX = event.clientX;
    dragStartY = event.clientY;

    originalX = videoX;
    originalY = videoY;

});


window.addEventListener("mousemove", (event) => {

    if (!dragging) {
        return;
    }

    const deltaX =
        event.clientX - dragStartX;

    const deltaY =
        event.clientY - dragStartY;

    videoX =
        originalX + deltaX;

    videoY =
        originalY + deltaY;

    updateTransform();

});


window.addEventListener("mouseup", () => {

    dragging = false;

    viewer.classList.remove("dragging");

});


// ------------------------------------------------------------
// Touch dragging
// ------------------------------------------------------------

viewer.addEventListener(
    "touchstart",
    (event) => {

        if (event.touches.length !== 1) {
            return;
        }

        const touch =
            event.touches[0];

        dragging = true;

        dragStartX = touch.clientX;
        dragStartY = touch.clientY;

        originalX = videoX;
        originalY = videoY;

    },
    { passive: true }
);


viewer.addEventListener(
    "touchmove",
    (event) => {

        if (!dragging ||
            event.touches.length !== 1) {

            return;
        }

        const touch =
            event.touches[0];

        videoX =
            originalX +
            (touch.clientX - dragStartX);

        videoY =
            originalY +
            (touch.clientY - dragStartY);

        updateTransform();

    },
    { passive: true }
);


viewer.addEventListener(
    "touchend",
    () => {

        dragging = false;

    }
);


// ------------------------------------------------------------
// WebRTC
// ------------------------------------------------------------

let pc = null;


// ------------------------------------------------------------
// Wait for ICE gathering
// ------------------------------------------------------------

function waitForIceGatheringComplete(pc) {

    return new Promise(resolve => {

        if (pc.iceGatheringState === "complete") {
            resolve();
            return;
        }

        function checkState() {

            if (pc.iceGatheringState === "complete") {

                pc.removeEventListener(
                    "icegatheringstatechange",
                    checkState
                );

                resolve();
            }
        }

        pc.addEventListener(
            "icegatheringstatechange",
            checkState
        );
    });
}


// ------------------------------------------------------------
// Get phone offer
// ------------------------------------------------------------

async function waitForOffer() {

    while (true) {

        try {

            const response =
                await fetch("/signal/offer");

            const data =
                await response.json();

            if (data.offer) {
                return data.offer;
            }

        } catch (error) {

            console.error(error);

        }

        await new Promise(resolve =>
            setTimeout(resolve, 500)
        );
    }
}


// ------------------------------------------------------------
// Send settings
// ------------------------------------------------------------

async function sendSettings() {

    const data = {

        quality:
            parseInt(quality.value),

        fps:
            parseInt(fps.value)

    };

    try {

        await fetch("/settings", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify(data)

        });

    } catch (error) {

        console.error(
            "Could not send settings:",
            error
        );

    }
}


// ------------------------------------------------------------
// Quality slider
// ------------------------------------------------------------

quality.addEventListener("input", () => {

    qualityValue.textContent =
        quality.value + "%";

    sendSettings();

});


// ------------------------------------------------------------
// FPS slider
// ------------------------------------------------------------

fps.addEventListener("input", () => {

    fpsValue.textContent =
        fps.value + " FPS";

    sendSettings();

});


// ------------------------------------------------------------
// Start WebRTC
// ------------------------------------------------------------

async function start() {

    try {

        statusText.textContent =
            "Waiting for phone...";


        pc =
            new RTCPeerConnection({
                iceServers: []
            });


        // ----------------------------------------------------
        // Receive video
        // ----------------------------------------------------

        pc.ontrack = event => {

            if (
                event.streams &&
                event.streams[0]
            ) {

                video.srcObject =
                    event.streams[0];

                statusText.textContent =
                    "Connected";

            }

        };


        // ----------------------------------------------------
        // Connection status
        // ----------------------------------------------------

        pc.onconnectionstatechange = () => {

            console.log(
                "Connection:",
                pc.connectionState
            );


            if (
                pc.connectionState ===
                "connected"
            ) {

                statusText.textContent =
                    "Connected";


            } else if (
                pc.connectionState ===
                "disconnected" ||

                pc.connectionState ===
                "failed"
            ) {

                statusText.textContent =
                    "Connection lost";

            }

        };


        // ----------------------------------------------------
        // Get phone offer
        // ----------------------------------------------------

        const offer =
            await waitForOffer();


        await pc.setRemoteDescription(
            new RTCSessionDescription(offer)
        );


        // ----------------------------------------------------
        // Create answer
        // ----------------------------------------------------

        const answerDescription =
            await pc.createAnswer();


        await pc.setLocalDescription(
            answerDescription
        );


        // ----------------------------------------------------
        // Wait for ICE
        // ----------------------------------------------------

        await waitForIceGatheringComplete(pc);


        // ----------------------------------------------------
        // Send answer
        // ----------------------------------------------------

        await fetch("/signal/answer", {

            method: "POST",

            headers: {
                "Content-Type": "application/json"
            },

            body: JSON.stringify({
                answer: pc.localDescription
            })

        });


        // Initial settings
        await sendSettings();


    } catch (error) {

        console.error(error);

        statusText.textContent =
            "WebRTC error: " +
            error.message;

    }

}


start();

</script>

</body>
</html>
"""


# ------------------------------------------------------------
# ROUTES
# ------------------------------------------------------------

@app.route("/")
def index():
    return """
    <h1>PhoneFPV</h1>
    <ul>
        <li><a href="/phone">Phone</a></li>
        <li><a href="/computer">Computer</a></li>
    </ul>
    """


@app.route("/phone")
def phone():
    return render_template_string(PHONE_HTML)


@app.route("/computer")
def computer():
    return render_template_string(COMPUTER_HTML)


# ------------------------------------------------------------
# WEBRTC SIGNALING
# ------------------------------------------------------------

@app.route("/signal/offer", methods=["GET", "POST"])
def signal_offer():

    global offer, answer

    if request.method == "POST":

        data = request.get_json()

        with signal_lock:

            offer = data["offer"]

            # New phone connection means old answer is invalid.
            answer = None

        return jsonify({
            "success": True
        })

    with signal_lock:

        return jsonify({
            "offer": offer
        })


@app.route("/signal/answer", methods=["GET", "POST"])
def signal_answer():

    global answer

    if request.method == "POST":

        data = request.get_json()

        with signal_lock:

            answer = data["answer"]

        return jsonify({
            "success": True
        })

    with signal_lock:

        return jsonify({
            "answer": answer
        })


# ------------------------------------------------------------
# SETTINGS
# ------------------------------------------------------------

@app.route("/settings", methods=["GET", "POST"])
def settings_route():

    if request.method == "POST":

        data = request.get_json()

        with settings_lock:

            if "quality" in data:

                settings["quality"] = max(
                    10,
                    min(100, int(data["quality"]))
                )

            if "fps" in data:

                settings["fps"] = max(
                    1,
                    min(60, int(data["fps"]))
                )

        return jsonify({
            "success": True
        })


    with settings_lock:

        return jsonify(settings)


# ------------------------------------------------------------
# RESET
# ------------------------------------------------------------

@app.route("/reset", methods=["POST"])
def reset():

    global offer, answer

    with signal_lock:

        offer = None
        answer = None

    return jsonify({
        "success": True
    })


# ------------------------------------------------------------
# START SERVER
# ------------------------------------------------------------

if __name__ == "__main__":

    print()
    print("===================================")
    print("          PhoneFPV")
    print("===================================")
    print()
    print(f"Port: {PORT}")
    print()
    print("Computer:")
    print(f"  https://<YOUR-MAC-IP>:{PORT}/computer")
    print()
    print("Phone:")
    print(f"  https://<YOUR-MAC-IP>:{PORT}/phone")
    print()
    print("===================================")
    print()

    app.run(
        host="0.0.0.0",
        port=PORT,
        threaded=True,
        ssl_context="adhoc"
    )
