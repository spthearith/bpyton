FROM python:3.9.5
WORKDIR /app
COPY . /app
COPY requirements.txt requirements.txt
RUN python -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
COPY . .
EXPOSE 3216
CMD ["python3", "/home/docker/app.py"]
