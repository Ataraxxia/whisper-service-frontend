This repository is a supplement to the youtube video explaning this solution:
https://www.youtube.com/watch?v=xpLMTh8xoj8

Requires python version from 3.8 to 3.11 but that may possibly change.

A quickstart code:
```
sudo apt install redis-server 

git pull https://github.com/Ataraxxia/whisper-service-frontend.git
python3 -m venv whisper-service-fronted-venv
source whisper-service-frontend-venv/bin/activate
pip install -r whisper-service-frontend/requirements.txt

cd whisper-service-frontend
celery -A app.celery worker --loglevel=info && python3 app.py
```
