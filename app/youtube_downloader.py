import os
import re
from yt_dlp import YoutubeDL
import streamlit as st
import time


def extract_video_id(url):
    if 'v=' in url:
        return url.split('v=')[1].split('&')[0]
    elif 'youtu.be/' in url:
        return url.split('youtu.be/')[1].split('?')[0]
    else:
        return url

def strip_ansi_escape_sequences(text):
    # This regular expression matches all ANSI escape sequences in a string
    ansi_escape = re.compile(r'(?:\x1b\[|\x9b)[0-?]*[ -/]*[@-~]')
    return ansi_escape.sub('', text)

def update_progress(d):
    if d['status'] == 'downloading':
        # Extract numerical part of the progress percentage, stripping ANSI escape sequences
        progress_percent = strip_ansi_escape_sequences(d['_percent_str'])
        progress_float = float(progress_percent.replace('%', '')) / 100
        # Update progress bar in Streamlit UI
        st.session_state.progress_bar.progress(progress_float)

def sanitize_filename(title):
    # Remove or replace characters that are not allowed in filenames
    title = re.sub(r'[\\/*?:"<>|]', '_', title) # Replacing invalid characters with underscore
    title = re.sub(r'[^\x00-\x7F]+', '', title) # Removing non-ascii characters
    return title.strip() # Removing leading/trailing whitespace

# Add the new function to generate video path
def get_video_path_from_url(url):
    with YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
        sanitized_title = sanitize_filename(info['title'])
        video_path = os.path.abspath(f"downloads/{sanitized_title}.mp4")
        return video_path

def download_youtube_video(url):
    if 'progress_bar' not in st.session_state:
        st.session_state['progress_bar'] = st.progress(0)

    with YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
        if 'title' in info and isinstance(info['title'], str):
            sanitized_title = sanitize_filename(info['title'])
            video_path = os.path.abspath(f"downloads/{sanitized_title}.mp4")

            if not os.path.exists(video_path):
                ydl_opts = {
                    'format': 'bestvideo[height<=480][ext=mp4]/bestvideo[ext=mp4]/best',
                    'outtmpl': video_path,
                    'progress_hooks': [update_progress],
                    'quiet': True
                }
                with YoutubeDL(ydl_opts) as ydl_download:
                    ydl_download.download([url])
            else:
                print("Video already downloaded.")
        else:
            print("Error: 'title' not found or not a string in info.")
            return None

    if 'progress_bar' in st.session_state:
        st.session_state.progress_bar.empty()
        del st.session_state['progress_bar']

    return video_path

def get_video_metadata(url):
    """Get metadata for a YouTube video."""
    print("Getting video metadata...")

    with YoutubeDL() as ydl:
        info = ydl.extract_info(url, download=False)
        metadata = {
            'title': info['title'],
            'author': info.get('uploader', 'Unknown'),
            'description': info.get('description', 'No description available'),
        }
    return metadata
