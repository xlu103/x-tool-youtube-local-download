import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('downloads.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS downloads
        (id INTEGER PRIMARY KEY AUTOINCREMENT,
         title TEXT NOT NULL,
         url TEXT NOT NULL,
         author TEXT,
         duration INTEGER,
         description TEXT,
         file_size INTEGER,
         local_path TEXT,
         thumbnail_path TEXT,
         download_time TIMESTAMP NOT NULL)
    ''')
    conn.commit()
    conn.close()

def add_download(video_info):
    conn = sqlite3.connect('downloads.db')
    c = conn.cursor()
    c.execute('''
        INSERT INTO downloads 
        (title, url, author, duration, description, 
         file_size, local_path, thumbnail_path, download_time)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        video_info['title'],
        video_info['url'],
        video_info['author'],
        video_info['duration'],
        video_info['description'],
        video_info['file_size'],
        video_info['local_path'],
        video_info['thumbnail_path'],
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    ))
    conn.commit()
    conn.close()

def get_downloads():
    conn = sqlite3.connect('downloads.db')
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM downloads 
        ORDER BY download_time DESC
        LIMIT 10
    ''')
    downloads = [dict(row) for row in c.fetchall()]
    conn.close()
    return downloads 