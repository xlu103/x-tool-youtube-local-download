from flask import Flask, render_template, request, jsonify, send_file, session
import yt_dlp
import os
from database import init_db, add_download, get_downloads
import humanize
import logging
import uuid

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'downloads'
# 设置一个密钥用于加密session数据
app.secret_key = 'your-secret-key-here'  # 在生产环境中使用更安全的密钥


@app.before_request
def before_request():
    # 如果用户没有session_id,创建一个新的
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())


@app.route("/")
def home():
    downloads = get_downloads(session['user_id'])
    for download in downloads:
        try:
            if download['file_size']:
                download['filesize_human'] = humanize.naturalsize(
                    download['file_size'])
            else:
                download['filesize_human'] = '未知'
                
            if download['duration']:
                download['duration_human'] = humanize.naturaldelta(
                    download['duration'])
            else:
                download['duration_human'] = '未知'
                
            # 确保文件仍然存在
            if not os.path.exists(download['local_path']):
                download['status'] = '文件已删除'
            else:
                download['status'] = '可下载'
                
        except Exception as e:
            logger.error(f"处理下载记录时出错: {str(e)}")
            download['filesize_human'] = '未知'
            download['duration_human'] = '未知'
            download['status'] = '记录错误'
            
    return render_template("index.html", downloads=downloads)


@app.route("/download", methods=["POST"])
def download():
    url = request.form["url"]
    
    ydl_opts = {
        'format': 'best',
        'outtmpl': os.path.join(app.config['UPLOAD_FOLDER'], '%(title)s.%(ext)s'),
        'quiet': False,
        'no_warnings': False
    }

    try:
        # 先获取视频信息,不下载
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            filename = ydl.prepare_filename(info)
            logger.debug(f"准备下载文件: {filename}")
            
            # 检查文件是否已存在
            if os.path.exists(filename):
                logger.info(f"文件已存在,直接返回: {filename}")
                try:
                    return send_file(
                        filename,
                        as_attachment=True,
                        download_name=os.path.basename(filename)
                    )
                except Exception as e:
                    logger.error(f"发送已存在文件时出错: {str(e)}")
                    raise
            
            # 文件不存在,开始下载
            logger.info("开始下载新文件")
            info = ydl.extract_info(url, download=True)
            
            # 确保文件已经下载完成
            if not os.path.exists(filename):
                logger.error(f"文件下载后未找到: {filename}")
                raise Exception("文件下载失败")
            
            logger.info(f"文件下载完成: {filename}")
            
            video_info = {
                'title': info['title'],
                'url': url,
                'author': info.get('uploader', '未知'),
                'duration': info.get('duration', 0),
                'description': info.get('description', ''),
                'file_size': os.path.getsize(filename),
                'local_path': filename,
                'thumbnail_path': ''
            }
            
            # 保存下载记录,添加session_id
            try:
                add_download(video_info, session['user_id'])
                logger.info("下载记录已保存到数据库")
            except Exception as e:
                logger.error(f"保存下载记录时出错: {str(e)}")
            
            return send_file(
                filename,
                as_attachment=True,
                download_name=os.path.basename(filename)
            )

    except Exception as e:
        logger.error(f"下载过程中出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'下载出错: {str(e)}'
        }), 500


if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    init_db()
    app.run(debug=True)
