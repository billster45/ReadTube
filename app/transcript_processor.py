from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound

def get_transcript(video_id):
    """Get the English transcript for a YouTube video, prioritizing manual over auto-generated transcripts."""
    print("Getting video transcript...")

    try:
        # Fetch all available transcripts for the video
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Try to find a manual English transcript
        english_transcript = transcript_list.find_transcript(['en'])
        if not english_transcript.is_generated:
            # If a manual transcript is found, fetch it
            return english_transcript.fetch()

        # If no manual transcript, try to find an auto-generated English transcript
        english_generated_transcript = transcript_list.find_generated_transcript(['en'])
        return english_generated_transcript.fetch()
        
    except NoTranscriptFound:
        print(f"No English transcript found for video ID: {video_id}")
        return None
