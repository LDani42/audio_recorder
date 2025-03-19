import streamlit as st
import numpy as np
import time
import io
from datetime import datetime
import matplotlib.pyplot as plt
import wave
import threading
from streamlit_webrtc import (
    WebRtcMode,
    webrtc_streamer,
    RTCConfiguration
)
import av

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

# Use in-memory storage for Streamlit Cloud compatibility
if 'recordings' not in st.session_state:
    st.session_state.recordings = {}

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
if 'webrtc_started' not in st.session_state:
    st.session_state.webrtc_started = False

# Create placeholder for visualization
viz_placeholder = st.empty()

# Function to save audio buffer to in-memory WAV file
def save_audio_buffer(audio_frames, filename_key, sample_rate=RATE, channels=CHANNELS):
    # Convert to numpy array
    audio_data = np.concatenate(audio_frames)
    
    # Save as in-memory WAV file
    wav_buffer = io.BytesIO()
    with wave.open(wav_buffer, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 2 bytes for 'int16'
        wf.setframerate(sample_rate)
        wf.writeframes(audio_data.tobytes())
    
    # Store the WAV data in session state
    wav_buffer.seek(0)  # Reset buffer position to start
    st.session_state.recordings[filename_key] = wav_buffer.getvalue()
    
    return filename_key

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
            try:
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
            except Exception as e:
                # Catch any visualization errors to prevent thread from crashing
                print(f"Visualization error: {e}")
        
        # If we're not recording, clear the visualization
        elif not st.session_state.recording and not st.session_state.webrtc_started:
            try:
                # Show a placeholder visualization with message
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.text(0.5, 0.5, "Click 'Start Recording' to begin", 
                       horizontalalignment='center', verticalalignment='center',
                       transform=ax.transAxes, fontsize=14)
                ax.set_xticks([])
                ax.set_yticks([])
                viz_placeholder.pyplot(fig)
                plt.close(fig)
            except Exception as e:
                print(f"Placeholder error: {e}")
                
        time.sleep(0.1)  # Update every 100ms

# Start the visualization thread
if "viz_thread" not in st.session_state:
    st.session_state.viz_thread = threading.Thread(
        target=update_visualization,
        daemon=True,
    )
    st.session_state.viz_thread.start()

# Function to start recording
def start_recording():
    # Initialize WebRTC if not already started
    st.session_state.webrtc_started = True
    st.session_state.recording = True
    st.session_state.audio_buffer = []  # Clear the buffer
    st.session_state.audio_data_display = np.array([])  # Clear the display buffer
    st.session_state.recording_start_time = time.time()
    st.session_state.recorded_file = None

# Function to stop recording
def stop_recording():
    if st.session_state.recording:
        st.session_state.recording = False
        
        # Generate filename key with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_key = f"audio_{timestamp}"
        
        # Save audio to in-memory storage if we have data
        if len(st.session_state.audio_buffer) > 0:
            st.session_state.recorded_file = save_audio_buffer(
                st.session_state.audio_buffer, 
                filename_key
            )

# Create a hidden WebRTC component that automatically starts
# This allows us to hide the WebRTC UI elements
webrtc_ctx = webrtc_streamer(
    key="audio-recorder",
    mode=WebRtcMode.SENDONLY,
    rtc_configuration=RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}),
    audio_frame_callback=audio_frame_callback,
    video_frame_callback=None,
    media_stream_constraints={"video": False, "audio": True},
    async_processing=True,
    desired_playing_state=True,  # Auto-start the component
    in_recorder_factory=None,    # Disable in-recorder feature
    out_recorder_factory=None,   # Disable out-recorder feature
    show_audio_input_select=False, # Hide audio input selector
    source_video_track=None,     # No video track
    source_audio_track=None,     # Default audio track
    sendback_audio=False,        # Don't send audio back
    video_html_attrs={           # Make the video element hidden
        "style": "display: none;",
        "controls": False,
        "autoPlay": True,
    }
)

# Create columns for buttons
col1, col2 = st.columns(2)

# Start button
with col1:
    start_button = st.button(
        "Start Recording", 
        on_click=start_recording,
        disabled=st.session_state.recording or not webrtc_ctx.state.playing,
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
if st.session_state.recording and st.session_state.recording_start_time:
    elapsed_time = time.time() - st.session_state.recording_start_time
    mins, secs = divmod(int(elapsed_time), 60)
    recording_time = f"{mins:02d}:{secs:02d}"
    st.write(f"⏱️ Recording time: {recording_time}")

# Display the recorded audio file
if st.session_state.recorded_file and st.session_state.recorded_file in st.session_state.recordings:
    st.write("✅ Recording completed!")
    st.write(f"📁 Recording ID: {st.session_state.recorded_file}")
    
    # Get the audio data from session state
    audio_data = st.session_state.recordings[st.session_state.recorded_file]
    
    # Add audio playback
    st.audio(audio_data, format="audio/wav")
    
    # Add download button
    btn = st.download_button(
        label="Download Recording",
        data=audio_data,
        file_name=f"{st.session_state.recorded_file}.wav",
        mime="audio/wav"
    )

# App footer
st.write("---")
st.write("Made with Streamlit 💫")

# Add information about deployment
st.sidebar.title("Info")
st.sidebar.write("""
### Required Libraries
```
streamlit
streamlit-webrtc
numpy
matplotlib
av
```

### Using This App
1. Allow microphone access when prompted
2. Click "Start Recording" to begin
3. Speak into your microphone and watch the waveform
4. Click "Stop Recording" when finished
5. Download or play back your recording
""")

# If WebRTC didn't start automatically, show a message
if not webrtc_ctx.state.playing:
    st.warning("⚠️ Please allow microphone access to use this app.")
