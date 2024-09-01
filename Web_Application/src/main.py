from flask import Flask, jsonify, request, render_template, redirect, url_for
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from models import get_user, check_password, hash_password
import paho.mqtt.client as mqtt
from pymongo import MongoClient
from datetime import datetime
import json
import threading
import time
from helper_functions import get_hourly_viewing_data

app = Flask(__name__)
app.secret_key = '45ef7755sq3cqsc888zeaf23jusoa!'  # To be stored outside the source file after intial installation of the system

# Load database credentials from db_cred
def load_db_cred():
    with open('db_cred') as f:
        return json.load(f)

# Load configuration from config
def load_config():
    with open('config') as f:
        return json.load(f)

config = load_config()
db_cred = load_db_cred()

# MongoDB Atlas Configuration
MONGO_USER = db_cred["user"]
MONGO_PASS = db_cred["password"]
MONGO_CLUSTER = config["mongo_0"]["cluster"]
MONGO_DB_0 = config["mongo_0"]["database"]
MONGO_DB_1 = config["mongo_1"]["database"]

# MongoDB Atlas connection URI
mongo_client_0 = MongoClient(f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_CLUSTER}.zhw4z.mongodb.net/?retryWrites=true&w=majority&appName={MONGO_DB_0}", tls=True, tlsAllowInvalidCertificates=True)
mongo_client_1 = MongoClient(f"mongodb+srv://{MONGO_USER}:{MONGO_PASS}@{MONGO_CLUSTER}.zhw4z.mongodb.net/?retryWrites=true&w=majority&appName={MONGO_DB_0}", tls=True, tlsAllowInvalidCertificates=True)

db_0 = mongo_client_0[MONGO_DB_0]
db_1 = mongo_client_0[MONGO_DB_1]

visitor_collection_0 = db_0["visitor_data"]
visitor_collection_1 = db_1["visitor_data"]
viewing_collection_1 = db_1["viewing_data"]

# MQTT Configuration
MQTT_BROKER = config["mqtt"]["broker"]
MQTT_PORT = config["mqtt"]["port"]
MQTT_TOPIC_PRESENCE_PREV = config["mqtt"]["topics"]["presence_prev"]
MQTT_TOPIC_PRESENCE_CURR = config["mqtt"]["topics"]["presence_curr"]
MQTT_TOPIC_ROOM = config["mqtt"]["topics"]["room"]

# Global variables for visitor count
room_visitors = {
    "0": 0,
    "1": 0
}

# MQTT Callback Functions
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    client.subscribe(MQTT_TOPIC_PRESENCE_CURR)
    client.subscribe(MQTT_TOPIC_PRESENCE_PREV)
    client.subscribe(MQTT_TOPIC_ROOM)

def on_disconnect(client, userdata, flags, rc):
    print(f"Disconnected with result code {rc}")
    reconnect(client)

def on_message(client, userdata, msg):
    print(f"Message received: {msg.payload.decode()}")
    if msg.topic == MQTT_TOPIC_PRESENCE_CURR:
        handle_room_message(msg.payload.decode())
    elif msg.topic == MQTT_TOPIC_ROOM:
        handle_exhibit_message(msg.payload.decode())

def handle_exhibit_message(payload):
    data = json.loads(payload)
    if not isinstance(data, dict):
        print("Invalid data received")
        return

    room_id = data.get("r_id")
    exhibit_id = data.get("id")
    detected = data.get("detected")
    timestamp = datetime.now()

    if detected:
        viewing_collection_1.insert_one({
            "exhibit_id": exhibit_id,
            "timestamp": timestamp
        })
        print(f"Presence detected in front of painting {exhibit_id} in room {room_id} at {timestamp}")

def handle_room_message(payload):
    data = json.loads(payload)
    if not isinstance(data, dict):
        print("Invalid data received")
        return
    room_id = data.get("id")
    action = data.get("detected")
    timestamp = datetime.now()

    if action:
        room_visitors[str(room_id)] =  room_visitors[str(room_id)] + 1
    if room_id != "0":
        room_visitors[str(room_id-1)] = max(0, room_visitors[str(room_id-1)] - 1)

        visitor_collection_0.insert_one({
            "id": room_id - 1,
            "visitor_count": room_visitors[str(room_id-1)],
            "timestamp": timestamp
        })

    visitor_collection_1.insert_one({
        "id": room_id,
        "visitor_count": room_visitors[str(room_id)],
        "timestamp": timestamp
    })
    print(f"New entry in room {room_id} at {timestamp}")

def reconnect(client):
    FIRST_RECONNECT_DELAY = 1
    RECONNECT_RATE = 2
    MAX_RECONNECT_COUNT = 12
    MAX_RECONNECT_DELAY = 60

    reconnect_count, reconnect_delay = 0, FIRST_RECONNECT_DELAY
    while reconnect_count < MAX_RECONNECT_COUNT:
        print(f"Reconnecting in {reconnect_delay} seconds...")
        time.sleep(reconnect_delay)

        try:
            client.reconnect()
            print("Reconnected successfully!")
            return
        except Exception as err:
            print(f"{err}. Reconnect failed. Retrying...")

        reconnect_delay *= RECONNECT_RATE
        reconnect_delay = min(reconnect_delay, MAX_RECONNECT_DELAY)
        reconnect_count += 1
    print(f"Reconnect failed after {reconnect_count} attempts. Exiting...")

def start_mqtt():
    mqtt_client = mqtt.Client()
    mqtt_client.on_connect = on_connect
    mqtt_client.on_disconnect = on_disconnect
    mqtt_client.on_message = on_message

    mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt_client.loop_start()
    
    return mqtt_client

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return get_user(user_id)

# Define Flask routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if check_password(username, password):
            user = get_user(username)
            login_user(user)
            return redirect(url_for('index'))
        else:
            return "Invalid username or password", 401

    return render_template('login.html')

@app.route('/logout', methods=['GET'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        
        if not check_password(current_user.id, current_password):
            return "Current password is incorrect", 401
        
        with open('credentials.json') as f:
            credentials = json.load(f)
        
        if current_user.id in credentials["users"]:
            credentials["users"][current_user.id]["password"] = hash_password(new_password)
            
            with open('credentials.json', 'w') as f:
                json.dump(credentials, f, indent=4)
            
            return redirect(url_for('index'))
        else:
            return "User not found", 404

    return render_template('change_password.html')

@app.route('/', methods=['GET'])
@login_required
def index():
    return render_template('index.html')

@app.route('/viewing_data', methods=['GET'])
@login_required
def get_viewing_data():
    total_viewing_percentage = get_hourly_viewing_data(viewing_collection_1)
    return jsonify(total_viewing_percentage)

@app.route('/visitor_data', methods=['GET'])
@login_required
def get_visitor_data():
    pipeline = [
        {
            "$group": {
                "_id": {
                    "year": { "$year": "$timestamp" },
                    "month": { "$month": "$timestamp" },
                    "day": { "$dayOfMonth": "$timestamp" },
                    "hour": { "$hour": "$timestamp" },
                    "room_id": "$id"
                },
                "total_visitor_count": { "$sum": "$visitor_count" }
            }
        },
        {
            "$sort": { "_id.year": 1, "_id.month": 1, "_id.day": 1, "_id.hour": 1 }
        }
    ]

    data = list(visitor_collection_1.aggregate(pipeline))
    return jsonify(data)
    

if __name__ == '__main__':
    # Start MQTT Client in a separate thread
    mqtt_thread = threading.Thread(target=start_mqtt)
    mqtt_thread.daemon = True
    mqtt_thread.start()

    # Run the Flask Web App
    app.run(host='0.0.0.0', port=5000)