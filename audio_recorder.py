import streamlit as st
import numpy as np
import pyaudio
import wave
import time
import os
from datetime import datetime
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Set page configuration
st.set_page_config(
    page_title="Audio Recorder",
    page_icon="🎤",
    layout="centered"
)

# App title and description
st.title("🎤 Simple Audio Recorder")
st.write("Record audio from your microphone and save it as a WAV file.")

# Audio parameters
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 44100
CHUNK = 1024
MAX_RECORD_SECONDS = 60

# Function to record audio
def record_audio(duration, filename):
    p = pyaudio.PyAudio()
    
    # Open audio stream
    stream = p.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    # Initialize variables
    frames = []
    audio_data = np.array([])
    
    # Create a placeholder for the visualization
    viz_placeholder = st.empty()
    
    # Start recording
    st.write("🔴 Recording...")
    progress_bar = st.progress(0)
    
    start_time = time.time()
    for i in range(0, int(RATE / CHUNK * duration)):
        # Check if stop button was pressed
        if st.session_state.get('stop_recording', False):
            break
            
        # Read audio data
        data = stream.read(CHUNK, exception_on_overflow=False)
        frames.append(data)
        
        # Convert to numpy array for visualization
        audio_chunk = np.frombuffer(data, dtype=np.int16)
        audio_data = np.append(audio_data, audio_chunk)
        
        # Update visualization every few chunks
        if i % 5 == 0:
            # Create visualization with larger figure for better visibility
            fig, ax = plt.subplots(figsize=(10, 4))
            
            # Plot only the last ~0.5 seconds of audio for responsive display
            samples_to_show = min(len(audio_data), RATE // 2)
            
            # Get the audio data to display
            display_data = audio_data[-samples_to_show:]
            
            # Calculate a suitable Y-axis range to make the waveform more visible
            # Instead of using the full int16 range (-32768 to 32767)
            # Scale the y-axis based on the actual signal amplitude, but with a minimum range
            data_max = max(np.max(np.abs(display_data)), 1000)  # Prevent division by zero
            
            # Use a scaling factor to amplify the waveform
            scaling_factor = 5.0  # Increase this to make the waveform appear larger
            y_limit = max(data_max * scaling_factor, 10000)  # Set a reasonable minimum
            
            # Plot the waveform with thicker line for better visibility
            ax.plot(display_data, color='blue', alpha=0.8, linewidth=1.5)
            
            # Calculate RMS (volume level) for the most recent chunk
            rms = np.sqrt(np.mean(np.square(audio_chunk.astype(np.float32))))
            level = min(1.0, rms / 5000)  # More sensitive normalization (was 10000)
            
            # Add a volume indicator - thicker red line
            ax.axhline(y=0, color='r', linestyle='-', alpha=level, linewidth=2)
            
            # Set more responsive y-axis limits
            ax.set_ylim(-y_limit, y_limit)
            ax.set_xlim(0, samples_to_show)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.set_title(f"Recording... Level: {int(level*100)}%")
            
            # Display in Streamlit
            viz_placeholder.pyplot(fig)
            plt.close(fig)
        
        # Update progress bar
        elapsed_time = time.time() - start_time
        progress = min(1.0, elapsed_time / duration)
        progress_bar.progress(progress)
        
        # Display recording time
        if i % 10 == 0:
            mins, secs = divmod(int(elapsed_time), 60)
            st.session_state.recording_time = f"{mins:02d}:{secs:02d}"
    
    # Stop and close the stream
    stream.stop_stream()
    stream.close()
    p.terminate()
    
    # Save the recorded audio to a WAV file
    wf = wave.open(filename, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    
    return filename

# Create a folder for recordings if it doesn't exist
if not os.path.exists("recordings"):
    os.makedirs("recordings")

# Initialize session state
if 'recording' not in st.session_state:
    st.session_state.recording = False
if 'recorded_file' not in st.session_state:
    st.session_state.recorded_file = None
if 'recording_time' not in st.session_state:
    st.session_state.recording_time = "00:00"

# Create columns for buttons
col1, col2 = st.columns(2)

# Function to handle start recording
def start_recording():
    st.session_state.recording = True
    st.session_state.stop_recording = False

# Function to handle stop recording
def stop_recording():
    st.session_state.stop_recording = True
    st.session_state.recording = False

# Start button
with col1:
    start_button = st.button(
        "Start Recording", 
        on_click=start_recording,
        disabled=st.session_state.recording,
        type="primary"
    )

# Stop button
with col2:
    stop_button = st.button(
        "Stop Recording", 
        on_click=stop_recording,
        disabled=not st.session_state.recording,
        type="secondary"
    )

# Display recording time
if st.session_state.recording or st.session_state.recorded_file:
    st.write(f"⏱️ Recording time: {st.session_state.recording_time}")

# Record audio when the recording state is True
if st.session_state.recording:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"recordings/audio_{timestamp}.wav"
    
    # Record audio and save to file
    recorded_file = record_audio(MAX_RECORD_SECONDS, filename)
    
    # Update session state
    st.session_state.recorded_file = recorded_file
    st.session_state.recording = False

# Display the recorded audio file
if st.session_state.recorded_file and os.path.exists(st.session_state.recorded_file):
    st.write("✅ Recording completed!")
    st.write(f"📁 Saved as: {st.session_state.recorded_file}")
    
    # Add audio playback
    st.audio(st.session_state.recorded_file)
    
    # Add download button
    with open(st.session_state.recorded_file, "rb") as file:
        btn = st.download_button(
            label="Download Recording",
            data=file,
            file_name=os.path.basename(st.session_state.recorded_file),
            mime="audio/wav"
        )

# Add information about required libraries
st.sidebar.title("Info")
st.sidebar.write("""
### Required Libraries
Make sure you have these packages installed:
```
pip install streamlit numpy pyaudio matplotlib
```

### Note
- On some systems, you may need to install PortAudio before installing PyAudio:
  - Windows: pip install pipwin, then pipwin install pyaudio
  - Mac: brew install portaudio, then pip install pyaudio
  - Linux: sudo apt-get install python3-pyaudio
""")

# App footer
st.write("---")
st.write("Made by ProtoBots.ai 💫")
