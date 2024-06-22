FROM python:3.9.5
WORKDIR /app
COPY . /app
RUN apt-get update \
  && apt-get -y install netcat gcc sqlite3 libsqlite3-dev nano \
  && apt-get clean
COPY requirements.txt requirements.txt
RUN python -m pip install --upgrade pip
RUN pip3 install -r requirements.txt
COPY . .
EXPOSE 3216
CMD ["python3", "main.py"]
