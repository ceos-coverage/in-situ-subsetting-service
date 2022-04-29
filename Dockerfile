FROM python:3.9.0-slim-buster

RUN pip3 install --upgrade pip
RUN pip3 install bottle gunicorn requests

RUN mkdir -p /home/in-situ-subsetter/data
RUN mkdir -p /home/in-situ-subsetter/swagger
COPY ./*.py /home/in-situ-subsetter/
COPY ./swagger/* /home/in-situ-subsetter/swagger/
COPY ./swagger.yaml /home/in-situ-subsetter/
COPY ./swagger-ui.version /home/in-situ-subsetter/
COPY ./index.html /home/in-situ-subsetter/

WORKDIR /home/in-situ-subsetter

EXPOSE 8104
CMD ["python", "./server.py"]
