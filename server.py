from flask import Flask, request, jsonify, render_template, send_from_directory, g
import threading
import os
import logging
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
from video_processing import compress_video_logic, get_video_info, log_queue, global_stop_processing, completion_queue

app = Flask(__name__, template_folder='templates')

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s', handlers=[logging.FileHandler("server.log"), logging.StreamHandler()])

app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['PROCESSED_FOLDER'] = 'processed'
app.config['FINAL_FOLDER'] = 'final'

@app.before_request
def before_request():
    g.start_time = datetime.now()

@app.after_request
def after_request(response):
    if hasattr(g, 'start_time'):
        duration = datetime.now() - g.start_time
        duration_ms = duration.total_seconds() * 1000  # 转换为毫秒
        logging.info(f"Request: {request.method} {request.path} - Duration: {duration_ms:.2f} ms - From: {request.remote_addr}")
    return response

@app.route('/')
def index():
    try:
        return render_template('index.html')
    except Exception as e:
        return str(e), 500

@app.route('/compress_video_logic', methods=['POST'])
def compress_video():
    if 'videoFile' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['videoFile']
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(video_file.filename))
    video_file.save(video_path)

    compressed_dir = app.config['PROCESSED_FOLDER']
    final_dir = app.config['FINAL_FOLDER']
    output_name = f"processed_{secure_filename(video_file.filename)}"
    output_path = os.path.join(final_dir, output_name)

    threading.Thread(target=compress_video_logic, args=(video_path, compressed_dir, final_dir, output_name)).start()
    return jsonify({"message": "Video compression started - 正在压缩视频，请耐心等待:"}), 200

@app.route('/get_video_info', methods=['POST'])
def get_video_info_endpoint():
    if 'videoFile' not in request.files:
        return jsonify({"error": "No video file provided"}), 400

    video_file = request.files['videoFile']
    video_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(video_file.filename))
    video_file.save(video_path)

    threading.Thread(target=get_video_info, args=(video_path,)).start()
    return jsonify({"message": "Video info retrieval started - 正在获取视频信息，请耐心等待:"}), 200

@app.route('/logs', methods=['GET'])
def get_logs():
    logs = []
    while not log_queue.empty():
        logs.append(log_queue.get())
    return jsonify({"logs": logs}), 200

@app.route('/completion', methods=['GET'])
def get_completion():
    completed_files = []
    while not completion_queue.empty():
        completed_files.append(completion_queue.get())
    return jsonify({"completed_files": completed_files}), 200

@app.route('/stop_processing', methods=['POST'])
def stop_processing():
    global global_stop_processing
    global_stop_processing = True
    return jsonify({"message": "Processing stopped"}), 200

@app.route('/static/<path:path>')
def send_static(path):
    return send_from_directory('static', path)

@app.route('/get_processed_files', methods=['GET'])
def get_processed_files():
    files = []
    for root, dirs, filenames in os.walk(app.config['FINAL_FOLDER']):
        for filename in filenames:
            if filename.endswith(".mp4"):
                file_path = os.path.join(root, filename)
                files.append({
                    "name": filename,
                    "url": f"/download/{filename}"
                })
    return jsonify({"files": files}), 200

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(app.config['FINAL_FOLDER'], filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404

    return send_from_directory(app.config['FINAL_FOLDER'], filename, as_attachment=True)

def delete_old_files():
    """
    定期删除超过7天的视频文件
    """
    now = datetime.now()
    cutoff_time = now - timedelta(days=7)

    for folder in [app.config['UPLOAD_FOLDER'], app.config['PROCESSED_FOLDER'], app.config['FINAL_FOLDER']]:
        for root, dirs, files in os.walk(folder):
            for filename in files:
                file_path = os.path.join(root, filename)
                if os.path.getmtime(file_path) < cutoff_time.timestamp():
                    os.remove(file_path)
                    logging.info(f"Deleted old file: {file_path}")

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['PROCESSED_FOLDER'], exist_ok=True)
    os.makedirs(app.config['FINAL_FOLDER'], exist_ok=True)
    
    # # 定期清理任务
    # from apscheduler.schedulers.background import BackgroundScheduler
    # scheduler = BackgroundScheduler()
    # scheduler.add_job(delete_old_files, 'interval', days=1)
    # scheduler.start()

    app.run(debug=True, host='0.0.0.0', port=5500)
