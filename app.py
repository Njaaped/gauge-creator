# app.py
import os
import json
import uuid
import threading
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename

# Import your existing logic
import backend_logic
import gauge_generator

# --- Flask App Setup ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'generated_videos'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# In-memory dictionary to track job status
job_status = {}

# --- Video Generation Worker (Now Simplified) ---
def generation_task(job_id, tcx_path, start_time_str, end_time_str):
    """
    Runs the video generation in a background thread by calling the 
    centralized backend orchestrator.
    """
    try:
        # Define a callback that updates the web job status dictionary
        def progress_callback(progress, message):
            job_status[job_id]['progress'] = progress
            job_status[job_id]['message'] = message

        job_status[job_id] = {'status': 'parsing', 'progress': 5, 'message': 'Parsing TCX data...'}
        tcx_metadata = backend_logic.parse_tcx_file(tcx_path)
        trackpoints = tcx_metadata['trackpoints']

        # Convert ISO strings from JS to datetime objects
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))

        output_filename = f"{job_id}.mp4"
        output_path = os.path.join(app.config['OUTPUT_FOLDER'], output_filename)

        # Single call to the new, centralized logic
        backend_logic.orchestrate_video_generation(
            trackpoints, start_time, end_time, output_path, progress_callback
        )
        
        job_status[job_id].update({'status': 'complete', 'filename': output_filename})
        
    except Exception as e:
        print(f"Error in job {job_id}: {e}")
        job_status[job_id] = {'status': 'error', 'message': str(e)}


# --- API Endpoints ---
@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handles TCX file upload, parses it, and returns data for plotting."""
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if file and file.filename.lower().endswith('.tcx'):
        try:
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)

            tcx_data = backend_logic.parse_tcx_file(filepath)
            
            plot_data = {
                'times': [tp['time'].isoformat() for tp in tcx_data['trackpoints']],
                'power': [tp['power'] for tp in tcx_data['trackpoints']],
                'filepath': filepath
            }
            return jsonify(plot_data)
        except Exception as e:
            return jsonify({'error': f'Failed to process TCX file: {e}'}), 500
    return jsonify({'error': 'Invalid file type'}), 400

@app.route('/generate', methods=['POST'])
def generate_video():
    """Starts the video generation process in a background thread."""
    data = request.json
    tcx_path = data.get('filepath')
    start_time_str = data.get('startTime')
    end_time_str = data.get('endTime')

    if not all([tcx_path, start_time_str, end_time_str]):
        return jsonify({'error': 'Missing required data'}), 400

    job_id = str(uuid.uuid4())
    job_status[job_id] = {'status': 'starting', 'progress': 0, 'message': 'Initializing...'}

    thread = threading.Thread(target=generation_task, args=(job_id, tcx_path, start_time_str, end_time_str))
    thread.start()

    return jsonify({'jobId': job_id})

@app.route('/status/<job_id>')
def get_status(job_id):
    """Returns the status of a generation job."""
    status = job_status.get(job_id, {'status': 'not_found'})
    return jsonify(status)

@app.route('/download/<filename>')
def download_file(filename):
    """Serves the generated video file for download."""
    return send_from_directory(app.config["OUTPUT_FOLDER"], filename, as_attachment=True)


if __name__ == '__main__':
    app.run(debug=True)
