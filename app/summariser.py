import openai
from tenacity import retry, stop_after_attempt, wait_random_exponential
import time
import streamlit as st
import tiktoken
from langchain.text_splitter import TokenTextSplitter
import hashlib
from datetime import datetime
from anthropic import Anthropic
import anthropic
import requests

# Set up the Anthropic API client
client = Anthropic()
CLAUDE_MODEL_NAME = "claude-3-opus-20240229"

enc = tiktoken.encoding_for_model("gpt-4")

def summarize_web_page(url, api_key, max_input_tokens=150000, max_output_tokens=4000):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }

    st.info("Fetching the web page content...")
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        page_content = response.text
        st.success("Web page content fetched successfully.")
    else:
        st.error(f"Failed to fetch the web page. Status code: {response.status_code}")
        return None

    st.info("Encoding the page content...")
    encoding = tiktoken.get_encoding("cl100k_base")
    encoded_content = encoding.encode(page_content)
    st.success("Page content encoded.")

    if len(encoded_content) > max_input_tokens:
        st.warning(f"The web page content exceeds the maximum token limit of {max_input_tokens}. The summary will be generated based on the first {max_input_tokens} tokens.")
        encoded_content = encoded_content[:max_input_tokens]

    content_text = encoding.decode(encoded_content)
    prompt = f"<content>{content_text}</content>Please produce a detailed bullet point summary of the web page content."

    messages = [
        {"role": "user", "content": prompt}
    ]

    client = Anthropic(api_key=api_key)

    try:
        st.info("Generating the summary...")
        response = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=max_output_tokens,
            temperature=0.5,
            messages=messages
        )
        summary = response.content[0].text
        st.success("Web page summary generated successfully.")
        return summary
    except Exception as e:
        st.error(f"Error generating summary: {str(e)}")
        return None

@retry(wait=wait_random_exponential(min=1, max=60), stop=stop_after_attempt(6))
def completion_with_backoff(model, messages, api_key, stream=False, model_provider="openai"):
    """Retry the completion function with exponential backoff."""
    print(f"Model Provider: {model_provider}")
    print(f"API Key: {api_key[:5]}...")  # Print only the first 5 characters of the API key for security
    
    try:
        if model_provider == "openai":
            print("Calling OpenAI API...")
            client = openai.OpenAI(api_key=api_key)
            response = client.chat.completions.create(model=model, messages=messages, stream=stream)
            return response
        elif model_provider == "anthropic":
            print("Calling Anthropic API...")
            client = anthropic.Anthropic(api_key=api_key)
            stream_manager = client.messages.stream(
                model=model,
                max_tokens=4000,
                temperature=1,
                system="You are a very skilled writer and communicator.",
                messages=messages,
            )
            return stream_manager
        else:
            raise ValueError(f"Unsupported model provider: {model_provider}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        raise

def format_time(seconds):
    """Format time in minutes and seconds."""
    minutes = int(seconds // 60)
    seconds = int(seconds % 60)
    return f"{minutes} minutes, {seconds} seconds"

# Function to estimate text area height based on average words per line
def estimate_text_area_height(text):
    avg_words_per_line = 15  # Adjusted average number of words per line
    words = len(text.split())
    lines = words // avg_words_per_line  # Estimate number of lines
    line_height = 25  # Adjusted height of each line in pixels
    minimum_height = 300  # Set a reasonable minimum height
    return max(minimum_height, lines * line_height)  # Return the larger of calculated height or minimum height

def get_summary(text, metadata, model_choice, api_key, generate_transcript, model_provider):
    print(f"Model Provider: {model_provider}")
    print(f"Model Choice: {model_choice}")
    st.info("Starting process to send transcript to OpenAI or Anthropic to organise transcript and generate a summary.")

    text_splitter = TokenTextSplitter(chunk_size=3500, chunk_overlap=0)
    texts = text_splitter.split_text(text)

    organised_transcript = ""
    summary = ""
    last_finish_reason = ""
    last_chunk_created_time = ""
    send_cost_transcript = 0  # Initialize send_cost_transcript

    # Create a placeholder for the organised transcript
    organised_transcript_placeholder = st.empty()

    if generate_transcript:
        # Process each chunk - only if generate_transcript is True

        # Process each chunk
        chunk_count = 0  # Initialize a counter for chunks
        for chunk in texts:
            token_count_send = len(enc.encode(chunk))
            send_cost_transcript += token_count_send / 1000 * 0.01
            if model_provider == "openai":
                for resp in completion_with_backoff(model_choice, [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": f"Split this YouTube video transcript into very short readable paragraphs. Only return the text with no other messages. Be diligent and ensure to return every word of the transcript but still correct spelling, typos and ensure correct capitalisation. Finally, detect multiple short paragraphs that are related and add a plain text subheading before them that summarises the main topics. : {chunk}"}], api_key, stream=True, model_provider=model_provider):
                    if resp.choices[0].delta.content is not None:
                        organised_transcript += resp.choices[0].delta.content
                        last_finish_reason = resp.choices[0].finish_reason or last_finish_reason
                        last_chunk_created_time = resp.created or last_chunk_created_time

                        height = estimate_text_area_height(organised_transcript)
                        chunk_key = f"chunk_{chunk_count}"  # Unique key for each chunk
                        organised_transcript_placeholder.text_area("Transcript split into paragraphs returning from GPT4-Turbo", organised_transcript, height=height, key=chunk_key)

                        chunk_count += 1  # Increment the chunk counter

            elif model_provider == "anthropic":
                stream_manager = completion_with_backoff(
                    model_choice,
                    [{"role": "user", "content": f"1) Split this YouTube video transcript into very short readable paragraphs. 2) Return every word of the transcript while correcting spelling, typos and correcting capitalisation. 3) Add a **Heading** before related paragraphs that summarise the topics in them 4) Return only the **Heading** and the paragraphs and no other messages : {chunk}"}],
                    api_key,
                    stream=True,
                    model_provider=model_provider,
                )
                with stream_manager as stream:
                    for text in stream.text_stream:
                        organised_transcript += text
                        height = estimate_text_area_height(organised_transcript)
                        chunk_key = f"chunk_{chunk_count}"  # Unique key for each chunk
                        organised_transcript_placeholder.text_area("Transcript split into paragraphs returning from Claude", organised_transcript, height=height, key=chunk_key)
                        chunk_count += 1  # Increment the chunk counter

        # Displaying the information from the last chunk
        #st.info(f"Last Finish Reason: {last_finish_reason}")
        #st.info(f"Last Chunk Created Time: {datetime.fromtimestamp(last_chunk_created_time).strftime('%Y-%m-%d %H:%M:%S')}")

        completion_tokens_used_transcript = len(enc.encode(organised_transcript))
        st.info(f"Count of organised transcript tokens received: {completion_tokens_used_transcript:,}")
        receive_cost_transcript = completion_tokens_used_transcript / 1000 * 0.03

    else:
        # If generate_transcript is False, skip the above processing
        receive_cost_transcript = 0
        organised_transcript = "Returning the transcript organised into readable paragraphs was not selected."
        organised_transcript_placeholder.text_area("Transcript split into paragraphs returning from GPT4-Turbo or Claude Opus3", organised_transcript)

    summary_prompt = (
        f"Title: {metadata['title']}\n"
        f"Author: {metadata['author']}\n"
        f"Description: {metadata['description']}\n"
        f"Transcript: {organised_transcript}\n"
        f"Briefly summarise this YouTube video in one paragraph with UK spelling and without adjectives. Followed by numbered bullets of its key points."
    )

    word_count_send_summary = len(summary_prompt.split())
    token_count_send_summary = len(enc.encode(summary_prompt))
    send_cost_summary = token_count_send_summary / 1000 * 0.01

    # Create placeholders for streaming text
    summary_placeholder = st.empty()

    # Stream the summary
    if model_provider == "openai":
        for resp in completion_with_backoff(model_choice, [{"role": "system", "content": "You are a helpful assistant."}, {"role": "user", "content": summary_prompt}], api_key, stream=True, model_provider=model_provider):
            if resp.choices[0].delta.content is not None:
                summary += resp.choices[0].delta.content
                height = estimate_text_area_height(summary)
                summary_placeholder.text_area("YouTube video summary from GPT4-Turbo", summary, height=int(height))

    elif model_provider == "anthropic":
        stream_manager = completion_with_backoff(
            model_choice,
            [{"role": "user", "content": summary_prompt}],
            api_key,
            stream=True,
            model_provider=model_provider,
        )
        with stream_manager as stream:
            for text in stream.text_stream:
                summary += text
                height = estimate_text_area_height(summary)
                summary_placeholder.text_area("YouTube video summary from Claude", summary, height=int(height))

    completion_tokens_used_summary = len(enc.encode(summary))
    receive_cost_summary = completion_tokens_used_summary / 1000 * 0.03

    # Calculating total cost
    total_cost = send_cost_transcript + receive_cost_transcript + send_cost_summary + receive_cost_summary

    st.info(f"Transcript Send Cost: ${send_cost_transcript:.2f}")
    st.info(f"Transcript Receive Cost: ${receive_cost_transcript:.2f}")
    st.info(f"Summary Send Cost: ${send_cost_summary:.2f}")
    st.info(f"Summary Receive Cost: ${receive_cost_summary:.2f}")

    # Display total cost
    st.info(f"Total Cost: ${total_cost:.2f}")

    return organised_transcript, summary