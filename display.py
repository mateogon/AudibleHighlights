import json
import time
from tkinter import *
from tkinter.colorchooser import askcolor
from tkinter import ttk  # For Treeview
import vlc
import threading
from mutagen.mp4 import MP4

# Global variables
delay = 200  # Default delay in milliseconds
highlight_color = 'cyan'
audio_duration = 0
player = None
update_interval = 20  # Update interval in milliseconds
playback_speed = 1.0  # Default playback speed
is_slider_being_dragged = False  # Flag to track slider interaction

# Declare global widgets that need to be accessed outside create_display
timeline_slider = None
status_label = None

def load_transcription(json_file_path):
    """Load and parse the JSON file with word-level timestamps, precomputing character indices."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading JSON file: {e}")
        return []

    words = []
    total_chars = 0  # Initialize character count
    previous_end_time = 0
    for segment in data.get('segments', []):
        for word_info in segment.get('words', []):
            word_text = word_info.get('text', '').strip()
            start_time = float(word_info.get('start', 0))
            end_time = float(word_info.get('end', 0))

            # Detect gaps or overlaps
            if start_time > previous_end_time:
                print(f"Gap detected between {previous_end_time}s and {start_time}s")
            elif start_time < previous_end_time:
                print(f"Overlap detected at {start_time}s")

            words.append({
                'word': word_text,
                'start_time': start_time,
                'end_time': end_time,
                'char_index_start': total_chars,
                'char_index_end': total_chars + len(word_text)
            })
            total_chars += len(word_text) + 1  # +1 for the space
            previous_end_time = end_time
    return words

def find_current_word(word_data, current_time):
    """Find the word that corresponds to the current time using binary search."""
    left, right = 0, len(word_data) - 1
    while left <= right:
        mid = (left + right) // 2
        word = word_data[mid]
        if word['start_time'] <= current_time <= word['end_time']:
            return word
        elif current_time < word['start_time']:
            right = mid - 1
        else:
            left = mid + 1
    return None

def extract_chapters(m4b_file_path):
    """Extract chapters from an M4B file using Mutagen."""
    try:
        audio = MP4(m4b_file_path)
        chapters = audio.chapters
        if not chapters:
            print("No chapters found in the M4B file.")
            return []
        
        chapters_list = []
        for chapter in chapters:
            chapters_list.append({'title': chapter.title, 'start_time': chapter.start})
        return chapters_list
    except Exception as e:
        print(f"Error extracting chapters: {e}")
        return []

def sync_audio_and_text(root, word_data, text_display, delay_slider, timeline_slider, current_time_label, total_time_label):
    """Synchronize audio playback with text highlighting."""
    current_word = None  # Track the currently highlighted word

    def update():
        nonlocal current_word
        try:
            if player is not None and (player.is_playing() or player.get_state() == vlc.State.Paused):
                # Get current playback time in milliseconds
                current_time_ms = player.get_time()
                if current_time_ms == -1:
                    current_time_ms = 0
                current_time = current_time_ms / 1000.0 + delay / 1000.0

                # Find the current word using binary search
                word_info = find_current_word(word_data, current_time)
                if word_info and word_info != current_word:
                    current_word = word_info
                    text_display.config(state=NORMAL)
                    text_display.tag_remove('highlight', '1.0', 'end')
                    word_start_idx = f"1.0 + {word_info['char_index_start']} chars"
                    word_end_idx = f"1.0 + {word_info['char_index_end']} chars"
                    text_display.tag_add('highlight', word_start_idx, word_end_idx)
                    text_display.tag_config('highlight', background=highlight_color)
                    text_display.see(word_start_idx)
                    text_display.config(state=DISABLED)
                elif not word_info and current_word is not None:
                    text_display.config(state=NORMAL)
                    text_display.tag_remove('highlight', '1.0', 'end')
                    current_word = None
                    text_display.config(state=DISABLED)

                # Update the timeline slider only if the user is not dragging it
                if not is_slider_being_dragged and audio_duration > 0:
                    position_ratio = current_time_ms
                    position_ratio = max(0, min(position_ratio, audio_duration))  # Clamp between 0 and audio_duration
                    timeline_slider.set(position_ratio)

                # Update current time label
                current_time_formatted = time.strftime('%H:%M:%S', time.gmtime(current_time_ms / 1000.0))
                current_time_label.config(text=f"Current Time: {current_time_formatted}")

        except Exception as e:
            print(f"Error during synchronization: {e}")

        # Schedule the next update
        root.after(update_interval, update)

    # Start the update loop
    root.after(update_interval, update)

# Playback control functions using VLC
def play_audio():
    """Start audio playback."""
    try:
        if player is not None:
            player.play()
            set_playback_speed(playback_speed)
            status_label.config(text="Playing", fg="green")
    except Exception as e:
        print(f"Error in play_audio: {e}")
        status_label.config(text="Error during playback", fg="red")

def pause_audio():
    """Pause audio playback."""
    try:
        if player is not None:
            player.pause()
            status_label.config(text="Paused", fg="orange")
    except Exception as e:
        print(f"Error in pause_audio: {e}")
        status_label.config(text="Error during pause", fg="red")

def stop_audio():
    """Stop audio playback."""
    try:
        if player is not None:
            player.stop()
            status_label.config(text="Stopped", fg="blue")
    except Exception as e:
        print(f"Error in stop_audio: {e}")
        status_label.config(text="Error during stop", fg="red")

def forward_15_seconds():
    """Skip forward by 15 seconds."""
    try:
        if player is not None:
            current_time = player.get_time()
            new_time = min(current_time + 15000, audio_duration)
            player.set_time(int(new_time))
            status_label.config(text="Skipped Forward 15s", fg="blue")
    except Exception as e:
        print(f"Error in forward_15_seconds: {e}")
        status_label.config(text="Error during forward skip", fg="red")

def back_15_seconds():
    """Skip backward by 15 seconds."""
    try:
        if player is not None:
            current_time = player.get_time()
            new_time = max(current_time - 15000, 0)
            player.set_time(int(new_time))
            status_label.config(text="Skipped Backward 15s", fg="blue")
    except Exception as e:
        print(f"Error in back_15_seconds: {e}")
        status_label.config(text="Error during backward skip", fg="red")

def update_delay(value):
    """Update the highlight delay based on the slider."""
    global delay
    try:
        delay = int(value)
    except Exception as e:
        print(f"Error updating delay: {e}")

def pick_color(text_display):
    """Open a color picker to select highlight color."""
    global highlight_color
    try:
        color = askcolor()[1]
        if color:
            highlight_color = color
            text_display.tag_config('highlight', background=highlight_color)
    except Exception as e:
        print(f"Error in pick_color: {e}")

def seek_audio(event=None):
    """Seek to a specific position in the audio based on the timeline slider."""
    try:
        if player is not None and audio_duration > 0:
            new_time = float(timeline_slider.get())
            new_time = max(0, min(new_time, audio_duration))  # Clamp between 0 and audio_duration
            player.set_time(int(new_time))
            status_label.config(text="Playback position updated", fg="blue")
    except Exception as e:
        print(f"Error in seek_audio: {e}")
        status_label.config(text="Error during seeking", fg="red")

def set_playback_speed(value):
    """Set the playback speed of the audio."""
    global playback_speed
    try:
        playback_speed = float(value)
        if player is not None:
            player.set_rate(playback_speed)
    except Exception as e:
        print(f"Error setting playback speed: {e}")

def create_display(word_data, audio_file_path):
    """Initialize VLC player, set up the GUI, and start synchronization."""
    global audio_duration, player, timeline_slider, is_slider_being_dragged, status_label
    try:
        # Initialize VLC player
        instance = vlc.Instance()
        player = instance.media_player_new()
        media = instance.media_new(audio_file_path)
        player.set_media(media)
        player.stop()  # Ensure the player is stopped

        # Parse the media to get the duration
        media.parse_with_options(vlc.MediaParseFlag.fetch_local, timeout=10)
        # Wait until the media is parsed
        parsed = media.get_parsed_status()
        start_time = time.time()
        while parsed != vlc.MediaParsedStatus.done and parsed != vlc.MediaParsedStatus.failed:
            if time.time() - start_time > 10:
                print("Media parsing timed out.")
                break
            time.sleep(0.1)
            parsed = media.get_parsed_status()

        # Get audio duration
        audio_duration = media.get_duration()  # Duration in milliseconds

        # Check if audio_duration is valid
        if audio_duration <= 0:
            audio_duration = 1  # Prevent division by zero errors

        root = Tk()
        root.title("Audiobook Sync")

        # Create PanedWindow to hold chapters and transcript
        paned_window = PanedWindow(root, orient=HORIZONTAL, sashrelief=RAISED, sashwidth=5)
        paned_window.pack(fill=BOTH, expand=True)

        # Side Panel for Chapters
        chapters_frame = Frame(paned_window, width=200)
        paned_window.add(chapters_frame)

        chapters_label = Label(chapters_frame, text="Chapters", font=("Helvetica", 14))
        chapters_label.pack(pady=5)

        # Treeview for Chapters
        chapters_tree = ttk.Treeview(chapters_frame, columns=("Time"), show='headings', selectmode='browse')
        chapters_tree.heading("Time", text="Start Time")
        chapters_tree.column("Time", width=100, anchor='center')
        chapters_tree.pack(fill=BOTH, expand=True, padx=5, pady=5)

        # Scrollbar for Treeview
        scrollbar = Scrollbar(chapters_frame, orient=VERTICAL, command=chapters_tree.yview)
        chapters_tree.configure(yscroll=scrollbar.set)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Extract and populate chapters
        chapters = extract_chapters(audio_file_path)
        for idx, chapter in enumerate(chapters, start=1):
            # Format start_time to HH:MM:SS
            start_time_formatted = time.strftime('%H:%M:%S', time.gmtime(chapter['start_time']))
            chapters_tree.insert('', 'end', iid=idx, values=(f"{chapter['title']} ({start_time_formatted})",))

        # Bind double-click on a chapter to seek_audio
        chapters_tree.bind("<Double-1>", lambda event: on_chapter_select())

        # Transcript Frame
        transcript_frame = Frame(paned_window)
        paned_window.add(transcript_frame)

        # Create a Text widget to display the transcript
        text_display = Text(transcript_frame, wrap=WORD, font=("Helvetica", 16))
        text_display.pack(expand=True, fill=BOTH)

        # Insert the entire transcript into the Text widget
        transcript = ' '.join([word['word'] for word in word_data])
        text_display.config(state=NORMAL)
        text_display.insert('1.0', transcript)
        text_display.config(state=DISABLED)

        # Validate character indices
        total_chars_in_text = len(transcript)
        last_word_char_end = word_data[-1]['char_index_end'] if word_data else 0
        if last_word_char_end != total_chars_in_text:
            print(f"Warning: Last word char_index_end ({last_word_char_end}) does not match total_chars_in_text ({total_chars_in_text})")
        else:
            print("Character indices correctly mapped.")

        # Control Panel
        control_panel = Frame(root)
        control_panel.pack(fill=X)

        # Playback Buttons
        play_button = Button(control_panel, text="Play", command=play_audio)
        play_button.pack(side=LEFT, padx=5, pady=5)

        pause_button = Button(control_panel, text="Pause", command=pause_audio)
        pause_button.pack(side=LEFT, padx=5, pady=5)

        stop_button = Button(control_panel, text="Stop", command=stop_audio)
        stop_button.pack(side=LEFT, padx=5, pady=5)

        back_button = Button(control_panel, text="<< 15s", command=back_15_seconds)
        back_button.pack(side=LEFT, padx=5, pady=5)

        forward_button = Button(control_panel, text="15s >>", command=forward_15_seconds)
        forward_button.pack(side=LEFT, padx=5, pady=5)

        # Color Picker Button
        color_button = Button(control_panel, text="Pick Highlight Color", command=lambda: pick_color(text_display))
        color_button.pack(side=LEFT, padx=5, pady=5)

        # Delay Slider
        delay_slider = Scale(control_panel, from_=-500, to=500, orient=HORIZONTAL,
                             label="Highlight Delay (ms)", command=update_delay)
        delay_slider.set(delay)  # Set default delay
        delay_slider.pack(side=LEFT, padx=5, pady=5)

        # Playback Speed Control
        speed_label = Label(control_panel, text="Playback Speed:")
        speed_label.pack(side=LEFT, padx=(20, 5))

        speed_options = ["0.5", "0.75", "1.0", "1.25", "1.5", "2.0"]
        speed_var = StringVar(value="1.0")
        speed_menu = OptionMenu(control_panel, speed_var, *speed_options, command=set_playback_speed)
        speed_menu.pack(side=LEFT, padx=5, pady=5)

        # Timeline/Seek Slider
        timeline_frame = Frame(root)
        timeline_frame.pack(fill=X, padx=5, pady=5)

        timeline_slider = Scale(timeline_frame, from_=0, to=audio_duration, orient=HORIZONTAL, length=600, resolution=10)
        timeline_slider.pack(side=TOP, fill=X, expand=True)

        # Bind mouse events to track user interaction with the slider
        timeline_slider.bind("<ButtonPress-1>", lambda event: set_slider_dragging(True))
        timeline_slider.bind("<ButtonRelease-1>", lambda event: on_slider_release())

        # Labels for current time and total duration
        current_time_label = Label(timeline_frame, text="Current Time: 00:00:00")
        current_time_label.pack(side=LEFT)

        total_duration_formatted = time.strftime('%H:%M:%S', time.gmtime(audio_duration / 1000.0))
        total_time_label = Label(timeline_frame, text=f"Total Duration: {total_duration_formatted}")
        total_time_label.pack(side=RIGHT)

        # Status Label
        status_label = Label(root, text="Ready to play", fg="green")
        status_label.pack(side=BOTTOM, fill=X)

        # Start the synchronization function
        sync_audio_and_text(root, word_data, text_display, delay_slider, timeline_slider,
                            current_time_label, total_time_label)

        # Define helper functions inside create_display
        def set_slider_dragging(state):
            """Set the slider dragging flag."""
            global is_slider_being_dragged
            is_slider_being_dragged = state

        def on_slider_release():
            """Handle the slider release event to perform seeking."""
            set_slider_dragging(False)
            seek_audio()

        def on_chapter_select():
            """Handle chapter selection from the Treeview."""
            selected_item = chapters_tree.focus()
            if selected_item:
                chapter_text = chapters_tree.item(selected_item, 'values')[0]
                # Extract start time from the chapter_text
                # Assuming format: "Chapter Title (HH:MM:SS)"
                if '(' in chapter_text and ')' in chapter_text:
                    time_str = chapter_text.split('(')[-1].rstrip(')')
                    try:
                        h, m, s = map(float, time_str.split(':'))
                        seek_time_ms = int((h * 3600 + m * 60 + s) * 1000)
                        if player is not None:
                            player.set_time(seek_time_ms)
                            status_label.config(text=f"Jumped to chapter at {time_str}", fg="blue")
                    except ValueError:
                        print("Invalid time format in chapter.")
                else:
                    print("Invalid chapter format.")

        return root
    except Exception as e:
        print(f"Error creating display: {e}")
        return None

def main():
    """Main function to load transcription, create display, and start GUI."""
    # Paths to the audio and transcription files
    audio_file_path = "input/path/to/.m4b"
    json_file_path = "output/path/to/.json"

    # Load word-level transcription data
    word_data = load_transcription(json_file_path)
    if not word_data:
        print("No word data loaded. Exiting.")
        return

    # Create the display and start the GUI
    root = create_display(word_data, audio_file_path)
    if root is not None:
        root.mainloop()
    else:
        print("Failed to create the GUI.")

if __name__ == "__main__":
    main()
