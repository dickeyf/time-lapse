FROM python:3

RUN apt-get update
RUN apt-get install -y ffmpeg x264 libx264-dev
RUN pip install numpy opencv-contrib-python-headless opencv-python-headless paho-mqtt flask

ADD time-lapse.py /

CMD [ "python", "./time-lapse.py" ]
