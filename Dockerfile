# Use Python 3.11 as the base image
FROM python:3.11-slim

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install FFmpeg and additional dependencies
RUN apt-get update --fix-missing && \
    apt-get install -y ffmpeg libgtk2.0-dev pkg-config

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Make port 8501 available to the world outside this container
EXPOSE 8501

# Run streamlit_app.py when the container launches
CMD ["streamlit", "run", "streamlit_app.py"]