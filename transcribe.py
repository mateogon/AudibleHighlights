import os
import subprocess
from pydub import AudioSegment

def convert_mp3_to_wav(input_path, output_path, bitrate="16k"):
    try:
        audio = AudioSegment.from_mp3(input_path)
        audio = audio.set_frame_rate(16000).set_channels(1)
        audio.export(output_path, format="wav", bitrate=bitrate)
        print(f"Converted: {input_path} -> {output_path}")
    except Exception as e:
        print(f"Error converting {input_path} to WAV: {e}")

def convert_ffmpeg_to_wav(input_path, output_path):
    try:
        subprocess.run([
            "ffmpeg", "-i", input_path, "-ac", "1", "-ar", "16000", output_path
        ], check=True)
        print(f"Converted: {input_path} -> {output_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error converting {input_path} to WAV. Error: {e}")

def convert_audio(input_folder, output_folder, bitrate="16k"):
    # List of file extensions to process with ffmpeg
    ffmpeg_extensions = (".mp4", ".m4b", ".m4a", ".aac", ".ogg", ".flac", ".wav", ".wma", ".webm")
    pydub_extensions = (".mp3",)

    # List all files directly inside the input_folder (no subdirectories)
    try:
        files = sorted(os.listdir(input_folder))
    except Exception as e:
        print(f"Error accessing input folder: {e}")
        return

    for filename in files:
        input_path = os.path.join(input_folder, filename)

        # Skip directories; process only files
        if os.path.isdir(input_path):
            print(f"Skipping directory: {input_path}")
            continue

        # Get the file extension
        _, ext = os.path.splitext(filename)
        ext = ext.lower()

        # Determine the output directory name (input filename without extension)
        folder_name = os.path.splitext(filename)[0]
        output_dir = os.path.join(output_folder, folder_name)

        # Create the output directory if it doesn't exist
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
                print(f"Created directory: {output_dir}")
            except Exception as e:
                print(f"Error creating directory {output_dir}: {e}")
                continue

        # Define the output WAV file path inside the newly created directory
        output_wav_path = os.path.join(output_dir, f"{folder_name}.wav")

        # Check if the WAV file already exists to avoid redundant conversions
        if not os.path.exists(output_wav_path):
            if ext in pydub_extensions:
                convert_mp3_to_wav(input_path, output_wav_path, bitrate)
            elif ext in ffmpeg_extensions:
                convert_ffmpeg_to_wav(input_path, output_wav_path)
            else:
                print(f"Unsupported file format: {filename}, skipping...")
        else:
            print(f"WAV file already exists: {output_wav_path}, skipping...")

def transcribe_wav_files(output_folder, model_name='base', language='en'):
    import whisper_timestamped as whisper
    import torch
    import json

    # Check if the Whisper model exists; if not, download it
    try:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        print(f"Using device: {device}")
        model = whisper.load_model(model_name, device=device)
    except Exception as e:
        print(f"Error loading Whisper model: {e}")
        return

    # List all subdirectories inside the output_folder
    try:
        subdirectories = sorted([d for d in os.listdir(output_folder) if os.path.isdir(os.path.join(output_folder, d))])
    except Exception as e:
        print(f"Error accessing output folder: {e}")
        return

    for subdir in subdirectories:
        subdir_path = os.path.join(output_folder, subdir)
        files = sorted(os.listdir(subdir_path))

        for filename in files:
            if filename.endswith(".wav"):
                wav_path = os.path.join(subdir_path, filename)
                base_filename = os.path.splitext(filename)[0]
                txt_output_path = os.path.join(subdir_path, f"{base_filename}.txt")
                json_output_path = os.path.join(subdir_path, f"{base_filename}.json")

                # Check if transcription already exists
                if not os.path.exists(txt_output_path) or not os.path.exists(json_output_path):
                    print(f"Transcribing {filename} in {subdir_path}")
                    try:
                        # Transcribe the audio file
                        result = whisper.transcribe(
                            model,
                            wav_path,
                            language=language,
                            # Uncomment the following lines if you want to use these options
                            # vad=True,
                            # detect_disfluencies=True,
                        )

                        # Save the transcription to a text file
                        with open(txt_output_path, 'w', encoding='utf-8') as f:
                            f.write(result['text'])

                        # Save the detailed result to a JSON file
                        with open(json_output_path, 'w', encoding='utf-8') as f:
                            json.dump(result, f, indent=2, ensure_ascii=False)

                        print(f"Transcription created: {wav_path} -> {txt_output_path} & {json_output_path}")
                    except Exception as e:
                        print(f"Error transcribing {wav_path}: {e}")
                else:
                    print(f"Transcription already exists for: {wav_path}, skipping...")

# Get the current directory as the project folder
project_folder = os.path.dirname(os.path.abspath(__file__))

def setup_project_folders(project_folder):
    input_folder = os.path.join(project_folder, "input")
    output_folder = os.path.join(project_folder, "output")

    # Create directories if they don't exist
    for folder in [input_folder, output_folder]:
        if not os.path.exists(folder):
            try:
                os.makedirs(folder)
                print(f"Created folder: {folder}")
            except Exception as e:
                print(f"Error creating folder {folder}: {e}")

    return input_folder, output_folder

# Setup project folders and get paths
input_folder, output_folder = setup_project_folders(project_folder)

# Choose the Whisper model you want to use: tiny, base, small, medium, large
model_name = "tiny"  # You can change this to the desired model size
language = "en"  # Set the language code (e.g., 'es' for Spanish)

# Convert audio files to WAV format
convert_audio(input_folder, output_folder)

# Transcribe WAV files using whisper-timestamped
transcribe_wav_files(output_folder, model_name=model_name, language=language)
