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
        'no_warnings': False,
        'ignoreerrors': True,  # 忽略错误，继续下载
        'extract_flat': True,  # 只提取播放列表元数据
        'force_generic_extractor': False,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                # 先尝试获取播放列表信息
                result = ydl.extract_info(url, download=False)
                logger.info(f"获取到视频信息: {result.get('_type', 'video')}")
                
                # 判断是否为播放列表
                if result.get('_type') == 'playlist':
                    logger.info(f"检测到播放列表，共{len(result.get('entries', []))}个视频")
                    
                    successful_downloads = []
                    failed_downloads = []
                    
                    # 修改下载选项，用于实际下载视频
                    ydl_opts['extract_flat'] = False
                    
                    # 遍历播放列表中的每个视频
                    for entry in result.get('entries', []):
                        if not entry:
                            continue
                            
                        try:
                            video_url = entry.get('url', entry.get('webpage_url', None))
                            if not video_url:
                                failed_downloads.append("无法获取视频URL")
                                continue
                            
                            logger.info(f"开始下载视频: {video_url}")
                            
                            # 为每个视频创建新的下载器实例
                            with yt_dlp.YoutubeDL(ydl_opts) as video_ydl:
                                # 下载单个视频
                                info = video_ydl.extract_info(video_url, download=True)
                                if not info:
                                    failed_downloads.append(f"无法获取视频信息: {video_url}")
                                    continue
                                
                                filename = video_ydl.prepare_filename(info)
                                
                                if not os.path.exists(filename):
                                    failed_downloads.append(f"下载失败: {info.get('title', video_url)}")
                                    continue
                                
                                video_info = {
                                    'title': info.get('title', 'Unknown'),
                                    'url': video_url,
                                    'author': info.get('uploader', '未知'),
                                    'duration': info.get('duration', 0),
                                    'description': info.get('description', ''),
                                    'file_size': os.path.getsize(filename),
                                    'local_path': filename,
                                    'thumbnail_path': ''
                                }
                                
                                add_download(video_info, session['user_id'])
                                successful_downloads.append(info.get('title', video_url))
                                logger.info(f"成功下载视频: {info.get('title', video_url)}")
                                
                        except Exception as e:
                            logger.error(f"下载视频时出错: {str(e)}")
                            failed_downloads.append(f"下载出错: {str(e)}")
                            continue
                    
                    # 返回批量下载结果
                    return jsonify({
                        'status': 'completed',
                        'message': f'批量下载完成',
                        'successful': successful_downloads,
                        'failed': failed_downloads
                    })
                    
                else:  # 单个视频
                    # 修改下载选项用于单个视频
                    ydl_opts['extract_flat'] = False
                    with yt_dlp.YoutubeDL(ydl_opts) as video_ydl:
                        info = video_ydl.extract_info(url, download=True)
                        filename = video_ydl.prepare_filename(info)
                        
                        if not os.path.exists(filename):
                            raise Exception("文件下载失败")
                        
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
                        
                        add_download(video_info, session['user_id'])
                        
                        return send_file(
                            filename,
                            as_attachment=True,
                            download_name=os.path.basename(filename)
                        )
                    
            except Exception as e:
                logger.error(f"处理下载请求时出错: {str(e)}")
                raise

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
