from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from flask import send_file
import os
import uuid
import requests
import math
from celery import Celery

# Flask app setup
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'results'
app.config['SECRET_KEY'] = 'your_secret_key'
socketio = SocketIO(app)

# Celery setup
app.config['CELERY_BROKER_URL'] = 'redis://localhost:6379/0'
app.config['CELERY_RESULT_BACKEND'] = 'redis://localhost:6379/0'

app.config['REST_ENDPOINT']='http://127.0.0.1:8000/transcribe'

celery = Celery(app.name, broker=app.config['CELERY_BROKER_URL'])
celery.conf.update(app.config)

# Ensure upload folder exists
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

# Ensure output folder exists
if not os.path.exists(app.config['OUTPUT_FOLDER']):
    os.makedirs(app.config['OUTPUT_FOLDER'])

# Helper function for SRT subtitles
def format_time(seconds):
    hours = math.floor(seconds / 3600)
    seconds %= 3600
    minutes = math.floor(seconds / 60)
    seconds %= 60
    milliseconds = round((seconds - math.floor(seconds)) * 1000)
    seconds = math.floor(seconds)
    formatted_time = f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"

    return formatted_time

# Celery task to simulate backend processing
@celery.task(bind=True)
def process_audio(self, file_path):
    with open(file_path, 'rb') as f:
        response = requests.post(app.config['REST_ENDPOINT'], files={'file': f})

    # Sending request
    if response.status_code == 200:
        transcription = response.json()
    else:
        return "Error in transcription service"

    # Extract whole text
    ttext = transcription['text']

    # Get segments
    segments = transcription['segments']

    # generate SRT
    srt_arr = []
    for index, segment in enumerate(segments):
        startt = format_time(segment['start'])
        endt = format_time(segment['end'])

        srt_arr.append('{}'.format(str(index+1)))
        srt_arr.append('{} --> {}'.format(startt,endt))
        srt_arr.append('{}'.format(segment['text']))
        srt_arr.append('')

    srt = "\n".join(srt_arr)


    # Save the files
    uid = str(uuid.uuid4())
    fsrt = uid + '.srt'
    ftxt = uid + '.txt'
    srt_path = os.path.join(app.config['OUTPUT_FOLDER'], fsrt)
    txt_path = os.path.join(app.config['OUTPUT_FOLDER'], ftxt)

    with open(srt_path, 'wb') as f:
        f.write(srt.encode())

    with open(txt_path, 'wb') as f:
        f.write(ttext.encode())

    # return JSON
    r = {'txt_url': '{}/{}'.format(app.config['OUTPUT_FOLDER'],ftxt), 'srt_url': '{}/{}'.format(app.config['OUTPUT_FOLDER'],fsrt), 'txt': ttext}
    return r


# Route to upload audio file
@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
        if file:
            # Save the file
            filename = str(uuid.uuid4()) + os.path.splitext(file.filename)[1]
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            # Start Celery task
            task = process_audio.apply_async(args=[file_path])
            return jsonify({"task_id": task.id}), 202
    return render_template('index.html')

# Route to download files
@app.route('/results/<filename>', methods=['GET'])
def download_result(filename):
    if filename != '':
        file_path = '{}/{}'.format(app.config['OUTPUT_FOLDER'], filename)
        return send_file(file_path, as_attachment=True)

# Route to check task status
@app.route('/status/<task_id>')
def task_status(task_id):
    task = process_audio.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {"state": task.state, "status": "Pending..."}
    elif task.state != 'FAILURE':
        response = {"state": task.state, "status": task.info}
    else:
        response = {"state": task.state, "status": str(task.info)}
    return jsonify(response)

# SocketIO event to notify client
@socketio.on('connect')
def handle_connect():
    emit('message', {'data': 'Connected'})

if __name__ == '__main__':
    socketio.run(app, debug=True, host="0.0.0.0")

