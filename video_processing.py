import os
import subprocess
from decimal import Decimal
import shutil
import queue

# 创建一个用于日志记录的队列
log_queue = queue.Queue()
completion_queue = queue.Queue()  # 用于通知主线程压缩完成
# 定义一个全局变量，用于标记是否停止处理视频
global_stop_processing = False
# 定义一个函数，用于检查FFmpeg和ffprobe是否安装
def check_ffmpeg_installed():
    """
    检查FFmpeg和ffprobe是否安装
    """
    try:
        result = subprocess.run(["ffmpeg", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        log_queue.put("FFmpeg 已安装")
        result = subprocess.run(["ffprobe", "-version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        log_queue.put("ffprobe 已安装")
        return True
    except subprocess.CalledProcessError as e:
        log_queue.put("FFmpeg 或 ffprobe 未安装")
        return False
# 定义一个函数，用于获取视频帧率
def get_frame_rate(video_path):
    """
    获取视频帧率
    """
    result = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate", "-of", "default=noprint_wrappers=1:nokey=1", video_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    frame_rate_expr = result.stdout.strip()
    log_queue.put("帧率获取结果:\n" + frame_rate_expr)
    try:
        num, denom = map(int, frame_rate_expr.split('/'))
        frame_rate = num / denom if denom != 0 else 0
        log_queue.put(f"帧率获取成功: {frame_rate} FPS")
        return int(frame_rate)
    except ValueError:
        log_queue.put("帧率解析失败")
        return 0

def convert_to_ffmpeg_format(time_str, frame_rate):
    """
    将时间转换为FFmpeg格式
    """
    time_str = time_str.replace('"', '')
    hh, mm, ss, ff = map(int, time_str.split(":"))
    ms = Decimal(ff) * 1000 / frame_rate if frame_rate != 0 else 0
    if ms >= 1000:
        extra_seconds = int(ms // 1000)
        ms -= extra_seconds * 1000
        ss += extra_seconds
        if ss >= 60:
            mm += ss // 60
            ss = ss % 60
            if mm >= 60:
                hh += mm // 60
                mm = mm % 60
    result = "{:02d}:{:02d}:{:02d}.{:03d}".format(hh, mm, ss, int(ms))
    log_queue.put(f"时间转换完成: {result}")
    return result

def compress_video_logic(video_path, compressed_dir, final_dir, output_name):
    """
    处理视频压缩逻辑
    """
    global global_stop_processing

    if not check_ffmpeg_installed():
        return

    os.makedirs(compressed_dir, exist_ok=True)
    os.makedirs(final_dir, exist_ok=True)

    if os.path.isdir(video_path):
        video_files = [os.path.join(video_path, f) for f in os.listdir(video_path) if f.endswith('.mp4')]
    else:
        video_files = [video_path]

    for full_path in video_files:
        if global_stop_processing:
            log_queue.put("已停止运行")
            global_stop_processing = False
            return
        filename = os.path.basename(full_path)
        if filename.endswith(".mp4") and not os.path.isdir(full_path):
            resolution_command = ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=s=x:p=0", full_path]
            resolution_result = subprocess.run(resolution_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            log_queue.put(f"视频分辨率获取结果:{resolution_result.stdout}")
            log_queue.put("-" * 40)
            # log_queue.put("开始压缩视频，请耐心等待")

            width, height = map(int, resolution_result.stdout.strip().split('x'))
            aspect_ratio = width / height
            if 0.55 <= aspect_ratio <= 0.56:
                scale = "960:1720"
            elif 0.42 <= aspect_ratio <= 0.43:
                scale = "720:1680"
            else:
                scale = "960:1720"
            output_path = os.path.join(final_dir, output_name)
            compress_command = ["ffmpeg", "-y", "-i", full_path, "-vcodec", "libx264", "-crf", "28", "-vf", f"scale={scale}", output_path]
            
            # Ensure the directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            process = subprocess.Popen(compress_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while True:
                output = process.stderr.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    log_queue.put(output.strip())
            process.wait()

    finalize_video(final_dir, compressed_dir, output_name)
    log_queue.put("视频已处理完毕")
    completion_queue.put(output_name)  # 通知主线程压缩完成

def finalize_video(final_dir, compressed_dir, output_name):
    """
    完成视频处理，将视频从压缩目录复制到最终目录并重命名
    """
    os.makedirs(final_dir, exist_ok=True)
    for filename in os.listdir(compressed_dir):
        full_path = os.path.join(compressed_dir, filename)
        if filename.endswith(".mp4") and not os.path.isdir(full_path):
            new_filename = filename.replace("processed_", "").replace("origin_", "")
            new_full_path = os.path.join(final_dir, new_filename)
            counter = 1
            original_new_full_path = new_full_path
            while os.path.exists(new_full_path):
                new_full_path = f"{os.path.splitext(original_new_full_path)[0]}_{counter}{os.path.splitext(original_new_full_path)[1]}"
                counter += 1
            shutil.copy2(full_path, new_full_path)
            log_queue.put(f"视频 {new_filename} 已复制到目标目录（重命名为 {os.path.basename(new_full_path)}）")

def get_video_info(video_path):
    """
    获取视频信息并输出到日志窗口
    """
    try:
        if not video_path:
            log_queue.put("视频文件路径为空")
            return
        
        if os.path.isdir(video_path):
            video_files = [os.path.join(video_path, f) for f in os.listdir(video_path) if f.endswith('.mp4')]
        else:
            video_files = [video_path]
        
        for video_file in video_files:
            command = f"ffprobe -i \"{video_file}\" 2>&1"
            result = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            output_lines = result.stdout.splitlines()
            
            file_size = os.path.getsize(video_file)
            if file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.2f} KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.2f} MB"
            else:
                size_str = f"{file_size / (1024 * 1024 * 1024):.2f} GB"

            duration_command = f"ffprobe -i \"{video_file}\" -show_entries format=duration -v quiet -of csv=\"p=0\""
            duration_result = subprocess.run(duration_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            duration_seconds = float(duration_result.stdout.strip())
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)

            log_output = "\n".join(line for line in output_lines if "handler_name    : VideoHandler" not in line and ("Video" in line or "Input" in line))
            log_output += f"\n文件大小: {size_str}"
            log_output += f"\n视频时长: {minutes} 分钟 {seconds} 秒"
            log_output += "\n" + "-"*40 + "\n"
            
            log_queue.put(f"视频文件：{video_file}")
            log_queue.put(log_output)
    except subprocess.CalledProcessError as e:
        log_queue.put("获取视频信息失败")
