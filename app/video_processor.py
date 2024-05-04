import os
import cv2
import base64
from app.summariser import get_summary
import streamlit as st
import time
from jinja2 import Environment, FileSystemLoader
import pdfkit

def clear_output_directory(directory_path):
    for item in os.listdir(directory_path):
        if item.endswith('.html'):
            os.remove(os.path.join(directory_path, item))
            
def create_and_show_html_main(html_file_path):
    if os.path.exists(html_file_path):
        with open(html_file_path, "r") as file:
            html_content = file.read()
        st.components.v1.html(html_content, height=800, scrolling=True)

        timestamp = int(time.time())
        download_key = f"download_{html_file_path}_{timestamp}"
        with open(html_file_path, "rb") as file:
            st.download_button(
                label="Download as HTML file",
                data=file,
                file_name=os.path.basename(html_file_path),
                mime="text/html",
                key=download_key
            )

        # Configure pdfkit with the wkhtmltopdf executable path inside the devcontainer
        config = pdfkit.configuration(wkhtmltopdf="/usr/bin/wkhtmltopdf")

        # Add PDF download button
        pdf_file_path = html_file_path.replace(".html", ".pdf")
        pdfkit.from_file(html_file_path, pdf_file_path, configuration=config)
        with open(pdf_file_path, "rb") as file:
            st.download_button(
                label="Download as PDF file",
                data=file,
                file_name=os.path.basename(pdf_file_path),
                mime="application/pdf",
                key=f"download_{pdf_file_path}_{timestamp}"
            )
    else:
        st.error("Failed to create HTML content.")

def create_html_file(screenshot_paths, transcript_entries, metadata, organized_transcript, summary, url, output_dir):
    print("Creating HTML content...")

    # Load the HTML template
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    env = Environment(loader=FileSystemLoader(template_dir))
    template = env.get_template('summary_template.html')

    # Generate a filename that's filesystem-safe
    filename = "".join(c if c.isalnum() or c.isspace() else "_" for c in metadata["title"]) + ".html"
    output_path = os.path.join(output_dir, filename)

    # Prepare the data for the template
    screenshots = []
    for screenshot_path, entry in zip(screenshot_paths, transcript_entries):
        if os.path.exists(screenshot_path):
            with open(screenshot_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode()
                cleaned_text = entry['text'].replace('\n', ' ')
                timestamp_seconds = int(entry['start'] * 1000) // 1000
                hours, remainder = divmod(entry['start'], 3600)
                minutes, seconds = divmod(remainder, 60)
                timestamp_str = f"{int(hours)}h{int(minutes)}m{int(seconds)}s"
                total_seconds = int(entry['start'])
                youtube_link_at_time = f"{url}&t={total_seconds}s"
                screenshots.append({
                    'image': encoded_image,
                    'text': cleaned_text,
                    'start': entry['start'],
                    'end': entry['end'],
                    'youtube_link': youtube_link_at_time,
                    'timestamp': timestamp_str
                })

    # Render the HTML template with the data
    html_content = template.render(
        title=metadata['title'],
        author=metadata['author'],
        description=metadata['description'],
        url=url,
        summary=summary,
        organized_transcript=organized_transcript,
        screenshots=screenshots
    )

    # Write the HTML content to a file
    with open(output_path, "w") as file:
        file.write(html_content)
    print(f"HTML file successfully written to {output_path}")

    return output_path

def ms_to_hms(ms):
    """Convert milliseconds to hh:mm:ss format."""
    seconds = int(ms / 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def check_video_file_exists(video_path):
    if not os.path.exists(video_path):
        st.error(f"Video file does not exist at {video_path}")
        return False
    else:
        print("Video file exists")
        return True

def create_output_directory(output_path):
    if not os.path.exists(output_path):
        os.makedirs(output_path)
        print(f"Created output directory at {output_path}")

def open_video_file(video_path):
    print(f"Attempting to open video file at {video_path}")
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print(f"Failed to open video file at {video_path}")
        st.error(f"Failed to open video file at {video_path}")
        return None
    else:
        st.success("Video file opened successfully")
        return cap

def process_video_segments(cap, transcript, segment_duration, target_width, output_dir, url):
    screenshot_paths = []
    combined_transcript_entries = []
    current_time = 0

    while current_time < transcript[-1]['start'] + transcript[-1]['duration']:
        segment_end_time = current_time + segment_duration

        relevant_entries = [entry for entry in transcript if current_time <= entry['start'] < segment_end_time]

        if relevant_entries:
            start_time = relevant_entries[0]['start']
            end_time = min(relevant_entries[-1]['start'] + relevant_entries[-1]['duration'], segment_end_time)
            midpoint = (start_time + end_time) / 2
            midpoint_ms = midpoint * 1000  # Convert to milliseconds
            midpoint_hms = ms_to_hms(midpoint_ms)  # Convert to hh:mm:ss format
            timestamp_seconds = int(midpoint_ms // 1000)
            hours, remainder = divmod(midpoint, 3600)
            minutes, seconds = divmod(remainder, 60)
            timestamp_str = f"{int(hours)}h{int(minutes)}m{int(seconds)}s"  
            total_seconds = int(midpoint)

            youtube_link_at_time = f"{url}&t={total_seconds}s"
                                                   
            cap.set(cv2.CAP_PROP_POS_MSEC, midpoint * 1000)
            print(f"Set video to {midpoint} milliseconds")
            ret, frame = cap.read()

            if ret:
                print("Frame read successfully")
                height, width, _ = frame.shape
                aspect_ratio = float(width) / float(height)
                target_height = int(target_width / aspect_ratio)
                resized_frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)

                screenshot_path = os.path.join(output_dir, f'screenshot_{midpoint:.2f}.png')
                cv2.imwrite(screenshot_path, resized_frame)
                screenshot_paths.append(screenshot_path)
                print(f"Screenshot saved at {screenshot_path}")

                # Display the screenshot in the app
                st.image(screenshot_path)
                st.markdown(f"Screenshot at {midpoint_hms} - <a href='{youtube_link_at_time}' target='_blank'>Watch on YouTube at this point</a>", unsafe_allow_html=True)
            else:
                st.error(f"Failed to read frame at time {current_time}ms in a video of duration {transcript[-1]['start'] + transcript[-1]['duration']}ms")

            # Display the text segment
            text = " ".join(entry['text'] for entry in relevant_entries)
            combined_entry = {'start': start_time, 'end': end_time, 'text': text}
            combined_transcript_entries.append(combined_entry)
            st.markdown(f"**{segment_duration} second transcript segment:** {text}", unsafe_allow_html=True)

        current_time += segment_duration

    return screenshot_paths, combined_transcript_entries

def ms_to_hms(ms):
    """Convert milliseconds to hh:mm:ss format."""
    seconds = int(ms / 1000)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"

def generate_summary(transcript_text, metadata, model_choice, api_key, generate_transcript, model_provider):
    organized_transcript, summary = get_summary(transcript_text, metadata, model_choice, api_key, generate_transcript, model_provider)
    print("Transcript and summary generation completed.")
    return organized_transcript, summary

def create_html_file_wrapper(screenshot_paths, combined_transcript_entries, metadata, organized_transcript, summary, url, output_dir):
    html_file_path = create_html_file(screenshot_paths, combined_transcript_entries, metadata, organized_transcript, summary, url, output_dir)
    if html_file_path:
        print(f"HTML file created at: {html_file_path}")
        create_and_show_html_main(html_file_path)
    else:
        print("Failed to create HTML file.")
    return html_file_path

def delete_video_file(video_path):
    if os.path.exists(video_path):
        try:
            os.remove(video_path)
            print(f"Deleted video file at {video_path}")
        except Exception as e:
            print(f"Error deleting video file: {e}")

def delete_screenshot_files(screenshot_paths):
    for screenshot_path in screenshot_paths:
        try:
            os.remove(screenshot_path)
            print(f"Deleted screenshot file at {screenshot_path}")
        except Exception as e:
            print(f"Error deleting screenshot file: {e}")

def combine_screenshots_and_transcript(video_path, transcript, metadata, model_choice, url, get_summary, create_and_show_html, api_key, segment_length, generate_transcript, model_provider):   

    if not check_video_file_exists(video_path):
        return

    output_dir = "output"
    create_output_directory(output_dir)

    cap = open_video_file(video_path)
    if cap is None:
        return

    screenshot_paths, combined_transcript_entries = process_video_segments(cap, transcript, segment_length, 800, output_dir, url)
    cap.release()

    transcript_text = " ".join(entry["text"] for entry in combined_transcript_entries)
    organized_transcript, summary = generate_summary(transcript_text, metadata, model_choice, api_key, generate_transcript, model_provider)

    html_file_path = create_html_file_wrapper(screenshot_paths, combined_transcript_entries, metadata, organized_transcript, summary, url, output_dir)

    delete_video_file(video_path)
    delete_screenshot_files(screenshot_paths)

    return html_file_path

