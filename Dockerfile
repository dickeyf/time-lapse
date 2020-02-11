FROM python:3

RUN pip install numpy opencv-contrib-python-headless opencv-python-headless paho-mqtt

ADD time-lapse.py /

CMD [ "python", "./motion-detect.py" ]
