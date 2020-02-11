# Motion detection from https://software.intel.com/en-us/node/754940

import json
import base64
import os
import paho.mqtt.client as mqtt
import datetime
import time

# defaults to 1 hour backlog (At 5 frames/second)
buffer_limit = 1000000
time_lapse_buffer = []
store_location = "./test-store/"

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
        if frame["seconds"] >= startTimeSecs and frame["seconds"] <= endTimeSecs:
            timelapse.append(frame["picture"])
    return timelapse

# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    # Handle preview streams here
    if msg.topic.startswith("dickeycloud/birdhouse/previews/v1/"):
        json_payload = msg.payload
        payload = json.loads(json_payload)
        payload["picture"] = base64.b64decode(payload["picture"])
        x = time.strptime(payload["timestamp"], '%Y-%m-%dT%H:%M:%S.%f+0000')
        payload["seconds"] = datetime.timedelta(year=x.tm_year, days=x.tm_yday, hours=x.tm_hour, minutes=x.tm_min, seconds=x.tm_sec).total_seconds()
        insert_picture(payload)

    #Handle motion detected events here
    if msg.topic.startswith("dickeycloud/birdhouse/motion/v1/"):
        json_payload = msg.payload
        payload = json.loads(json_payload)
        startTime = payload["begin_timestamp"]
        endTime = payload["end_timestamp"]
        x = time.strptime(startTime, '%Y-%m-%dT%H:%M:%S.%f+0000')
        startTimeSecs = datetime.timedelta(year=x.tm_year,days=x.tm_yday,hours=x.tm_hour,minutes=x.tm_min,seconds=x.tm_sec).total_seconds()
        x = time.strptime(endTime, '%Y-%m-%dT%H:%M:%S.%f+0000')
        endTimeSecs = datetime.timedelta(year=x.tm_year,days=x.tm_yday,hours=x.tm_hour,minutes=x.tm_min,seconds=x.tm_sec).total_seconds()
        print("Fetching time-lapse frames from ", startTimeSecs, " seconds to ", endTimeSecs, "seconds.")
        timelapse = get_timelapse(startTimeSecs, endTimeSecs)
        newFile = open(store_location + str(startTimeSecs) + "-" + str(endTimeSecs) + ".mjpeg", "wb")
        for frame in timelapse:
            newFile.write(frame)
        newFile.close()


# Specifying the frame limit is optional
if "FRAME_LIMIT" in os.environ:
    buffer_limit = os.environ["FRAME_LIMIT"]

if "STORE" in os.environ:
    store_location = os.environ["STORE"]

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
client.loop_forever()
