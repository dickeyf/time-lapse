FROM python:3

RUN pip install numpy opencv-contrib-python-headless opencv-python-headless paho-mqtt flask

ADD time-lapse.py /

CMD [ "python", "./time-lapse.py" ]
