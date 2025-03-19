import streamlit as st
import numpy as np
import time
import io
from datetime import datetime
import matplotlib.pyplot as plt
import wave
from streamlit_webrtc import webrtc_streamer, WebRtcMode, RTCConfiguration
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
if 'audio_data_display' not in st.session_state:
    st.session_state.audio_data_display = np.array([])

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
        audio_chunk = audio_frame.reshape(-1)
        st.session_state.audio_data_display = np.append(
            st.session_state.audio_data_display[-RATE:] if len(st.session_state.audio_data_display) > RATE else st.session_state.audio_data_display,
            audio_chunk
        )
        
        # Create visualization
        if len(st.session_state.audio_data_display) > 0:
            fig, ax = plt.subplots(figsize=(10, 4))
            
            # Plot audio data
            display_data = st.session_state.audio_data_display
            
            # Calculate a suitable Y-axis range
            data_max = max(np.max(np.abs(display_data)), 1000)
            scaling_factor = 5.0
            y_limit = max(data_max * scaling_factor, 10000)
            
            # Plot the waveform
            ax.plot(display_data, color='blue', alpha=0.8, linewidth=1.5)
            
            # Calculate RMS (volume level)
            rms = np.sqrt(np.mean(np.square(audio_chunk.astype(np.float32))))
            level = min(1.0, rms / 5000)
            
            # Add a volume indicator
            ax.axhline(y=0, color='r', linestyle='-', alpha=level, linewidth=2)
            
            # Set axis limits
            ax.set_ylim(-y_limit, y_limit)
            ax.set_xlim(0, len(display_data))
            ax.set_xticks([])
            ax.set_yticks([])
            
            # Display elapsed recording time
            elapsed_time = time.time() - st.session_state.recording_start_time if hasattr(st.session_state, 'recording_start_time') else 0
            mins, secs = divmod(int(elapsed_time), 60)
            recording_time = f"{mins:02d}:{secs:02d}"
            ax.set_title(f"Recording... Level: {int(level*100)}% - Time: {recording_time}")
            
            # Display in Streamlit
            viz_placeholder.pyplot(fig)
            plt.close(fig)
    
    return frame

# Function to start recording
def start_recording():
    st.session_state.recording = True
    st.session_state.audio_buffer = []
    st.session_state.audio_data_display = np.array([])
    st.session_state.recording_start_time = time.time()

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

# Basic WebRTC configuration
webrtc_ctx = webrtc_streamer(
    key="audio-recorder",
    mode=WebRtcMode.SENDONLY,
    rtc_configuration=RTCConfiguration({"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}),
    media_stream_constraints={"video": False, "audio": True},
    audio_frame_callback=audio_frame_callback
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

# Show a message if WebRTC is not playing
if not webrtc_ctx.state.playing:
    st.info("📢 Click 'START' in the WebRTC component above and allow microphone access to begin.")
else:
    if not st.session_state.recording:
        # Show a simple placeholder when not recording
        with viz_placeholder.container():
            st.info("Click 'Start Recording' to begin capturing audio.")

# Display the recorded audio file
if st.session_state.recorded_file and st.session_state.recorded_file in st.session_state.recordings:
    st.success("✅ Recording completed!")
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
