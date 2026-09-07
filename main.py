from flask import Flask, redirect, render_template, request, jsonify, render_template_string
import threading
import os

os.chdir(os.path.dirname(os.path.abspath(__file__)))

app = Flask(__name__)

@app.before_request
def before_request():
    # Check if the connection is secure or behind a secure proxy
    if not request.is_secure:
        # Check standard proxy header if deployed on a cloud/proxy platform
        if request.headers.get('X-Forwarded-Proto', 'http') == 'http':
            url = request.url.replace('http://', 'https://', 1)
            return redirect(url, code=301)

PORT = 1234

# ------------------------------------------------------------
# WebRTC signaling state
# ------------------------------------------------------------

signal_lock = threading.Lock()

offer = None
answer = None
phone_battery = None

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

@app.route("/battery", methods=["GET", "POST"])
def battery():
    global phone_battery

    if request.method == "POST":
        data = request.get_json()
        phone_battery = data.get("battery")
        return {"ok": True}

    return {
        "battery": phone_battery
    }


# ============================================================
# CONTROLLER
# ============================================================

controller = {

    # Whether keyboard control is enabled
    "enabled": False,

    # Current movement direction
    "direction": "stop",

    # Analog throttle: 0-100
    "throttle": 0,

    # Steering Dual Rate: 0-100
    "steeringDualRate": 0,

    # Individual movement states
    "forward": 0,
    "backward": 0,
    "left": 0,
    "right": 0

}

controller_lock = threading.Lock()


# ------------------------------------------------------------
# CONTROLLER ROUTE
# ------------------------------------------------------------

@app.route("/controller", methods=["GET", "POST"])
def controller_route():

    # ========================================================
    # RECEIVE CONTROLLER DATA
    # ========================================================

    if request.method == "POST":

        data = request.get_json(
            silent=True
        )


        if not isinstance(data, dict):

            return jsonify({
                "success": False,
                "error": "Invalid controller data"
            }), 400


        with controller_lock:


            # ------------------------------------------------
            # Enabled
            # ------------------------------------------------

            if "enabled" in data:

                controller["enabled"] = bool(
                    data["enabled"]
                )


            # ------------------------------------------------
            # Direction
            # ------------------------------------------------

            valid_directions = {

                "stop",

                "forward",
                "backward",

                "left",
                "right",

                "forward-left",
                "forward-right",

                "backward-left",
                "backward-right"

            }


            if "direction" in data:

                direction = str(
                    data["direction"]
                )


                if direction in valid_directions:

                    controller["direction"] = \
                        direction


            # ------------------------------------------------
            # THROTTLE
            # ------------------------------------------------

            if "throttle" in data:

                try:

                    controller["throttle"] = max(
                        0,
                        min(
                            100,
                            int(data["throttle"])
                        )
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    pass


            # ------------------------------------------------
            # STEERING DUAL RATE
            # ------------------------------------------------

            if "steeringDualRate" in data:

                try:

                    controller[
                        "steeringDualRate"
                    ] = max(
                        0,
                        min(
                            100,
                            int(
                                data[
                                    "steeringDualRate"
                                ]
                            )
                        )
                    )

                except (
                    TypeError,
                    ValueError
                ):

                    pass


            # ------------------------------------------------
            # MOVEMENT STATES
            # ------------------------------------------------

            movement_keys = [

                "forward",
                "backward",
                "left",
                "right"

            ]


            for key in movement_keys:

                if key in data:

                    controller[key] = (
                        1
                        if bool(data[key])
                        else 0
                    )


            # ------------------------------------------------
            # If disabled, force movement to STOP
            # ------------------------------------------------

            if not controller["enabled"]:

                controller["direction"] = \
                    "stop"

                controller["forward"] = 0
                controller["backward"] = 0
                controller["left"] = 0
                controller["right"] = 0


            # ------------------------------------------------
            # Make a copy
            # ------------------------------------------------

            current_controller = dict(
                controller
            )


        # ----------------------------------------------------
        # PRINT CONTROLLER DATA
        # ----------------------------------------------------
        #
        # This lets you see exactly what the computer
        # is sending in your terminal.
        #
        # You can remove this print later if desired.
        #

        print(
            "Controller:",
            current_controller
        )


        # ----------------------------------------------------
        # RETURN SUCCESS
        # ----------------------------------------------------

        return jsonify({

            "success": True,

            "controller":
                current_controller

        })


    # ========================================================
    # GET CURRENT CONTROLLER STATE
    # ========================================================

    with controller_lock:

        return jsonify(
            dict(controller)
        )



@app.route("/phone")
def phone():
    return render_template("phone.html")


@app.route("/computer")
def computer():
    return render_template("computer.html")


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
