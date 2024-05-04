import streamlit as st
import os
import streamlit.components.v1 as components
from app.youtube_downloader import download_youtube_video, get_video_metadata, extract_video_id
from app.transcript_processor import get_transcript
from app.video_processor import combine_screenshots_and_transcript, create_and_show_html_main, clear_output_directory
from app.summariser import get_summary, summarize_web_page
import time

st.set_page_config(page_title="ReadTube", page_icon="📚", layout="centered")

html_file_path_global = ""

def main():
    global html_file_path_global
    st.title('📚 ReadTube')
    st.markdown("<h2>Read YouTube instead! 😂</h2>", unsafe_allow_html=True)

    with st.sidebar:
        st.markdown("### 📚 About ReadTube")
        st.markdown("""
        ReadTube is an app that takes screenshots of a YouTube video at regular intervals and places the text of what was said around that point. It helps you read through the content of a video quickly.

        The app uses the selected model provider (OpenAI or Anthropic) to generate a summary of the video and optionally if you decide, adds the entire transcript organised into readable paragraphs and with sub-headings the AI model chosen adds in logical places.

        How it works:

        1. 🤖 Select the model provider (OpenAI or Anthropic) you want to use for generating the summary and organising the transcript.

        2. 🔑 Enter your API key for the selected model provider. The app will only show the input box for the relevant API key based on your selection.

        3. 📸 Choose the interval at which you want the app to take screenshots of the YouTube video (e.g., every 30 seconds, 60 seconds, etc.).

        4. 📖 Decide whether you want the app to organise the video transcript into readable paragraphs. This is optional and takes some time for videos longer than 5 minutes.

        5. 🔗 Paste the YouTube video link you want to summarise into the input box.

        6. 📗 Click the "Read it!" button to start the process.

        The app will then:

        - Download the YouTube video.
        - Fetch the video metadata (title, author, description).
        - Fetch the video transcript.
        - Take screenshots of the video at the specified interval.
        - Display the screenshots and the corresponding transcript segments in the app.
        - Send the transcript to the selected model provider (OpenAI or Anthropic) for generating a summary and organising the full transcript into readable paragraphs (if the option is selected).
        - Generate a summary of the video using the selected model provider.
        - Create an HTML file with the video summary, full organised transcript (if selected), screenshots, and corresponding transcript segments.
        - Display the generated HTML file in the app, allowing you to read through the video content.
        - Let's you download the generated content as an HTML file or PDF.

        The app also displays the estimated cost of using the selected model provider for generating the summary and organising the transcript (if selected).

        Additionally, there are example YouTube videos you can try out, as well as an example of what ReadTube can generate.
        """)
        st.markdown("---")
        st.markdown("Made by [billster45](https://github.com/billster45)")

    st.markdown('#### 1. 🤖 Select model provider')
    model_provider = st.radio("Model provider", ["openai", "anthropic"], horizontal=True, label_visibility='collapsed')

    if model_provider == "openai":
        st.markdown('#### 2. 🔑 Enter your OpenAI API key')
        openai_api_key = st.text_input("[Get your key from OpenAI](https://platform.openai.com/account/api-keys) : ", placeholder="sk-****************************************", type="password")
        anthropic_api_key = ""
    elif model_provider == "anthropic":
        st.markdown('#### 2. 🔑 Enter your Anthropic API key')
        anthropic_api_key = st.text_input("[Get your key from Anthropic Website](https://console.anthropic.com/settings/keys) : ", placeholder="sk-****************************************", type="password")
        openai_api_key = ""

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("#### 3. 📸 Screenshot YouTube video every X seconds?")
        segment_length = st.selectbox("Screenshot interval", 
                                      [10, 15, 20, 25, 30, 35, 40, 45, 50, 60, 90, 120], 
                                      index=4,
                                      key='segment_length',
                                      label_visibility='collapsed')
    with col2:
        st.markdown("#### 4. 📖 Add full transcript in readable paragraphs too?")
        generate_transcript = st.radio("Generate transcript", ["No", "Yes"], horizontal=True, index=0, label_visibility='collapsed')

    st.markdown("#### 5. 🔗 Paste YouTube link below")
    if model_provider == "openai":
        if not openai_api_key:
            url = st.text_input('YouTube URL', value=st.session_state.get('url', ''), key='url_input', disabled=True, placeholder="Please enter the OpenAI API key first", label_visibility='collapsed')
        else:
            url = st.text_input('YouTube URL', value=st.session_state.get('url', ''), key='url_input', label_visibility='collapsed')
    elif model_provider == "anthropic":
        if not anthropic_api_key:
            url = st.text_input('YouTube URL', value=st.session_state.get('url', ''), key='url_input', disabled=True, placeholder="Please enter the Anthropic API key first", label_visibility='collapsed')
        else:
            url = st.text_input('YouTube URL', value=st.session_state.get('url', ''), key='url_input', label_visibility='collapsed')

    if st.button('📗 Read it!'):
        if not url:
            st.error("Please enter a URL to summarise.")
        elif "youtube.com" in url or "youtu.be" in url:
            if model_provider == "openai" and not openai_api_key:
                st.error("Please enter an OpenAI API key to use the OpenAI model.")
            elif model_provider == "anthropic" and not anthropic_api_key:
                st.error("Please enter an Anthropic API key to use the Anthropic model.")
            else:
                process_video(url, openai_api_key, anthropic_api_key, segment_length, model_provider, generate_transcript)
        else:
            if not anthropic_api_key:
                st.error("Please enter an Anthropic API key to summarise the content.")
            else:
                process_webpage(url, anthropic_api_key)

    with st.expander("🔗 Example YouTube Videos", expanded=True):
        st.markdown("""
        <h3>Try out the app with these sample YouTube videos:</h3>
        """, unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button('How to tune LLMs in Generative AI Studio (4m 34s)'):
                url = 'https://youtu.be/4A4W03qUTsw?si=rVcd_iXwQOR8dZLU'
                st.session_state['url'] = url
                st.rerun()
            if st.button('The Illusion of MONEY, TIME & EGO - Alan Watts (10m 36s)'):
                url = 'https://youtu.be/dYSQ1NF1hvw?si=breSGiLJ6UtvHltk'
                st.session_state['url'] = url
                st.rerun()
        with col2:
            if st.button("This is the tastiest Chicken and Potato recipe you can make at home (4m 20s)"):
                url = 'https://youtu.be/CiNtYiBt2oQ?si=CVbxg7xKqwUgWrvs'
                st.session_state['url'] = url
                st.rerun()
            if st.button("Intro to Large Language Models - Andrej Karpathy (59m 47s)"):
                url = 'https://youtu.be/zjkBMFhNj_g?si=X31L84ObefIB5Ghn'
                st.session_state['url'] = url
                st.rerun()
        with col3:
            if st.button("History of Britain in 20 Minutes (21m 38s)"):
                url = 'https://youtu.be/VcnSsEVsrf0?si=0BrPKm0VyAGd49Xp'
                st.session_state['url'] = url
                st.rerun()
            if st.button("Prof. Geoffrey Hinton - 'Will digital intelligence replace biological intelligence?' Romanes Lecture (36m 53s)"):
                url = 'https://youtube.com/watch?v=N1TEjTeQeg0&si=ebaKyoOqew4LNKf7'
                st.session_state['url'] = url
                st.rerun()

    with st.expander("📖 Example Output", expanded=True):
        st.markdown("""
        <h3>Here's an example of what ReadTube can generate:</h3>
        """, unsafe_allow_html=True)
        html_string = open("samples/How to tune LLMs in Generative AI Studio.html", 'r', encoding='utf-8').read()
        st.components.v1.html(html_string, height=600, scrolling=True)

    if html_file_path_global:
        create_and_show_html_main(html_file_path_global)

def process_video(url, openai_api_key, anthropic_api_key, segment_length, model_provider, generate_transcript):
    if model_provider == "openai":
        model_choice = "gpt-4-turbo-preview"
        api_key = openai_api_key
    elif model_provider == "anthropic":
        model_choice = "claude-3-opus-20240229"
        api_key = anthropic_api_key
    else:
        raise ValueError(f"Unsupported model provider: {model_provider}")

    global html_file_path_global
    generate_transcript = generate_transcript == "Yes"

    if not url:
        st.warning("Please enter a URL.")
        return

    clear_output_directory('output')

    try:
        st.info("Downloading the video...")
        video_path = download_youtube_video(url)
        print(f"Downloaded video path: {video_path}")

        st.info("Fetching video metadata...")
        metadata = get_video_metadata(url)

        st.info("Fetching transcript...")
        video_id = extract_video_id(url)
        transcript = get_transcript(video_id)
        if transcript:
            st.success("Transcript successfully fetched.")

            st.info("Processing the video and generating summary...")
            html_file_path = combine_screenshots_and_transcript(video_path, transcript, metadata, model_choice, url, get_summary, create_and_show_html_main, api_key, segment_length, generate_transcript, model_provider)
            if html_file_path:
                html_file_path_global = html_file_path
                st.success("Summary and screenshots are ready.")
        else:
            st.error("Failed to fetch transcript.")
    except Exception as e:
        st.error(f"Error processing video: {e}")

def process_webpage(url, anthropic_api_key):
    try:
        st.info("Summarising content...")
        summary = summarize_web_page(url, anthropic_api_key)
        if summary:
            st.success("Summary generated.")
            st.write(summary)
        else:
            st.error("Failed to generate summary.")
    except Exception as e:
        st.error(f"Error summarising content: {e}")

if __name__ == "__main__":
    main()