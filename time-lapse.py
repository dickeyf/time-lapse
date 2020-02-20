import json
import base64
import os
import paho.mqtt.client as mqtt
import datetime
import time
import cv2
import numpy as np
from flask import Flask, send_file

# defaults to 1 hour backlog (At 5 frames/second)
buffer_limit = 1000000
time_lapse_buffer = []
store_location = "./test-store/"
app = Flask(__name__)

@app.route('/videos')
def get_video_list():
    files = [f for f in os.listdir(store_location) if os.path.isfile(os.path.join(store_location, f))]
    data = {
        "data": files
    }
    return json.dumps(data)


@app.route('/videos/<path:filename>')
def get_video(filename):
    return send_file(store_location + filename, as_attachment=True)


def insert_picture(picture):
    time_lapse_buffer.append(picture)
    # Trim the buffer FIFO way when we exceed our limit
    if len(buffer_limit) > buffer_limit:
        buffer_limit.pop(0)


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, rc):
    print("Connected with result code "+str(rc))

    # Subscribe to previews feed, this is what we store
    client.subscribe("dickeycloud/birdhouse/previews/v1/1")

    # Subscribe to motion detection events, this is what makes us dump a time-lapse mjpeg
    client.subscribe("dickeycloud/birdhouse/motion/v1/1")


def get_timelapse(startTimeSecs, endTimeSecs):
    timelapse = []
    for frame in time_lapse_buffer:
        if startTimeSecs <= frame["seconds"] <= endTimeSecs:
            timelapse.append(frame["picture"])
    return timelapse


def get_opencv_img_from_buffer(buffer, flags):
    bytes_as_np_array = np.frombuffer(buffer, dtype=np.uint8)
    return cv2.imdecode(bytes_as_np_array, flags)


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    # Handle preview streams here
    if msg.topic.startswith("dickeycloud/birdhouse/previews/v1/"):
        json_payload = msg.payload
        payload = json.loads(json_payload)
        payload["picture"] = base64.b64decode(payload["picture"])
        x = time.strptime(payload["timestamp"], '%Y-%m-%dT%H:%M:%S.%f+0000')
        payload["seconds"] = datetime.timedelta(days=x.tm_yday, hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds()
        insert_picture(payload)

    # Handle motion detected events here
    if msg.topic.startswith("dickeycloud/birdhouse/motion/v1/"):
        json_payload = msg.payload
        payload = json.loads(json_payload)
        start_time = payload["begin_timestamp"]
        end_time = payload["end_timestamp"]
        x = time.strptime(start_time, '%Y-%m-%dT%H:%M:%S.%f+0000')
        start_time_secs = datetime.timedelta(
            days=x.tm_yday, hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds()
        x = time.strptime(end_time, '%Y-%m-%dT%H:%M:%S.%f+0000')
        end_time_secs = datetime.timedelta(
            days=x.tm_yday, hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds()
        print("Fetching time-lapse frames from ", start_time_secs, " seconds to ", end_time_secs, "seconds.")
        time_lapse = get_timelapse(start_time_secs, end_time_secs)
        if len(time_lapse) > 0:
            frame_rate = len(time_lapse) / (1 + end_time_secs - start_time_secs)
            codec = cv2.VideoWriter_fourcc(*'mp4v')
            filename = str(start_time_secs) + "-" + str(end_time_secs) + ".mp4"
            mp4_path = mp4_store + "/" + filename
            h264_path = store_location + filename
            writer = cv2.VideoWriter(mp4_path, codec,
                                     frame_rate, (640, 480))
            for frame in time_lapse:
                writer.write(get_opencv_img_from_buffer(frame, cv2.IMREAD_COLOR))
            writer.release()

            os.system(f"ffmpeg -y -i {mp4_path} -vcodec libx264 {h264_path}")

            new_video_event = {
                "begin_timestamp": payload["begin_timestamp"],
                "end_timestamp": payload["end_timestamp"],
                "filename": filename
            }
            client.publish("dickeycloud/birdhouse/video/v1/1", json.dumps(new_video_event))

# Specifying the frame limit is optional
if "FRAME_LIMIT" in os.environ:
    buffer_limit = os.environ["FRAME_LIMIT"]

if "STORE" in os.environ:
    store_location = os.environ["STORE"]

mp4_store = os.path.join(store_location, "mp4")
os.mkdir(mp4_store)

# Collect the Solace PubSub+ connection parameters from the ENV vars
vmr_host = os.environ["VMR_HOST"]
mqtt_port = os.environ["MQTT_PORT"]
mqtt_username = os.environ["MQTT_USERNAME"]
mqtt_password = os.environ["MQTT_PASSWORD"]

# Establish connection with the Solace PubSub+ broker
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.username_pw_set(mqtt_username, mqtt_password)
client.connect(vmr_host, int(mqtt_port), 60)

# Blocking call that processes network traffic, dispatches callbacks and
# handles reconnecting.
# Other loop*() functions are available that give a threaded interface and a
# manual interface.
client.loop_start()

app.run(host='0.0.0.0')
