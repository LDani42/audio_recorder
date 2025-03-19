import streamlit as st
import numpy as np
import time
import os
from datetime import datetime
import matplotlib.pyplot as plt
import av
import queue
import threading
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
import wave

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
RATE = 44100  # Sample rate
CHANNELS = 1  # Mono audio

# Create a folder for recordings if it doesn't exist
if not os.path.exists("recordings"):
    os.makedirs("recordings")

# Initialize session state
if 'audio_buffer' not in st.session_state:
    st.session_state.audio_buffer = []
if 'recording' not in st.session_state:
    st.session_state.recording = False
if 'recorded_file' not in st.session_state:
    st.session_state.recorded_file = None
if 'recording_start_time' not in st.session_state:
    st.session_state.recording_start_time = None
if 'audio_data_display' not in st.session_state:
    st.session_state.audio_data_display = np.array([])

# Create placeholder for visualization
viz_placeholder = st.empty()

# Function to save audio buffer to WAV file
def save_audio_buffer(audio_frames, filename, sample_rate=RATE, channels=CHANNELS):
    # Convert to numpy array
    audio_data = np.concatenate(audio_frames)
    
    # Save as WAV file
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 2 bytes for 'int16'
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    return filename

# Audio callback function
def audio_frame_callback(frame):
    # Convert audio frame to numpy array
    audio_frame = frame.to_ndarray()
    
    # If actively recording, add to buffer
    if st.session_state.recording:
        # Add the audio data to our buffer
        st.session_state.audio_buffer.append(audio_frame.reshape(-1))
        
        # Add the most recent data to the display buffer
        if len(st.session_state.audio_data_display) > RATE * 2:  # Keep only 2 seconds of data for display
            st.session_state.audio_data_display = np.append(
                st.session_state.audio_data_display[len(audio_frame.reshape(-1)):],
                audio_frame.reshape(-1)
            )
        else:
            st.session_state.audio_data_display = np.append(
                st.session_state.audio_data_display,
                audio_frame.reshape(-1)
            )
    
    return frame

# Thread for updating the audio visualization
def update_visualization():
    while True:
        if st.session_state.recording and len(st.session_state.audio_data_display) > 0:
            # Create visualization
            fig, ax = plt.subplots(figsize=(10, 4))
            
            # Get the data to display
            display_data = st.session_state.audio_data_display
            samples_to_show = len(display_data)
            
            if samples_to_show > 0:
                # Calculate a suitable Y-axis range to make the waveform more visible
                data_max = max(np.max(np.abs(display_data)), 1000)  # Prevent division by zero
                
                # Use a scaling factor to amplify the waveform
                scaling_factor = 5.0  # Increase this to make the waveform appear larger
                y_limit = max(data_max * scaling_factor, 10000)  # Set a reasonable minimum
                
                # Plot the waveform with thicker line for better visibility
                ax.plot(display_data, color='blue', alpha=0.8, linewidth=1.5)
                
                # Calculate RMS (volume level) for visual feedback
                rms = np.sqrt(np.mean(np.square(display_data.astype(np.float32))))
                level = min(1.0, rms / 5000)  # More sensitive normalization
                
                # Add a volume indicator - red line
                ax.axhline(y=0, color='r', linestyle='-', alpha=level, linewidth=2)
                
                # Set more responsive y-axis limits
                ax.set_ylim(-y_limit, y_limit)
                ax.set_xlim(0, samples_to_show)
                ax.set_xticks([])
                ax.set_yticks([])
                
                # Calculate recording time
                if st.session_state.recording_start_time:
                    elapsed_time = time.time() - st.session_state.recording_start_time
                    mins, secs = divmod(int(elapsed_time), 60)
                    recording_time = f"{mins:02d}:{secs:02d}"
                    ax.set_title(f"Recording... Level: {int(level*100)}% - Time: {recording_time}")
                else:
                    ax.set_title(f"Recording... Level: {int(level*100)}%")
                
                # Display in Streamlit
                viz_placeholder.pyplot(fig)
                plt.close(fig)
        
        time.sleep(0.1)  # Update every 100ms

# Function to start recording
def start_recording():
    st.session_state.recording = True
    st.session_state.audio_buffer = []  # Clear the buffer
    st.session_state.audio_data_display = np.array([])  # Clear the display buffer
    st.session_state.recording_start_time = time.time()
    st.session_state.recorded_file = None

# Function to stop recording
def stop_recording():
    if st.session_state.recording:
        st.session_state.recording = False
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"recordings/audio_{timestamp}.wav"
        
        # Save audio to file if we have data
        if len(st.session_state.audio_buffer) > 0:
            st.session_state.recorded_file = save_audio_buffer(
                st.session_state.audio_buffer, 
                filename
            )

# RTC Configuration (using Google's STUN servers)
rtc_config = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

# Create columns for buttons
col1, col2 = st.columns(2)

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

# WebRTC streamer for audio
webrtc_ctx = webrtc_streamer(
    key="audio-recorder",
    mode=WebRtcMode.SENDONLY,
    rtc_configuration=rtc_config,
    audio_frame_callback=audio_frame_callback,
    video_frame_callback=None,
    media_stream_constraints={"video": False, "audio": True},
    async_processing=True,
)

# Start the visualization thread when the WebRTC context is ready
if webrtc_ctx.state.playing and "viz_thread" not in st.session_state:
    st.session_state.viz_thread = threading.Thread(
        target=update_visualization,
        daemon=True,
    )
    st.session_state.viz_thread.start()

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

# App footer
st.write("---")
st.write("Made with Streamlit 💫")

# Add information about deployment
st.sidebar.title("Deployment Info")
st.sidebar.write("""
### Required Libraries
This app uses streamlit-webrtc for audio capture:
```
pip install streamlit numpy matplotlib streamlit-webrtc
```

### Deployment Ready
This version uses WebRTC instead of PyAudio, making it suitable for cloud deployment on:
- Streamlit Cloud
- Heroku
- Any cloud service

### Instructions
1. Click "Start" to begin recording
2. Allow microphone access when prompted
3. Speak into your microphone
4. Click "Stop" when finished
5. Download or play back your recording
""")
