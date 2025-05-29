import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pytube import YouTube
from pytube.exceptions import RegexMatchError, VideoUnavailable, PytubeError # Added PytubeError for more specific handling
import threading
import os
import requests # For fetching thumbnail
from PIL import Image, ImageTk # For displaying thumbnail
from io import BytesIO

class YouTubeDownloaderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("YouTube Video Downloader")
        self.root.geometry("650x550")
        self.root.resizable(False, False)

        self.yt = None
        self.streams = None
        self.selected_stream = None
        self.download_path = os.getcwd()
        self.thumbnail_photo = None

        # --- UI Elements ---
        ttk.Label(root, text="YouTube URL:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.url_entry = ttk.Entry(root, width=60)
        self.url_entry.grid(row=0, column=1, padx=5, pady=5, columnspan=2)
        self.fetch_button = ttk.Button(root, text="Fetch Info", command=self.fetch_video_info)
        self.fetch_button.grid(row=0, column=3, padx=5, pady=5)

        info_frame = ttk.LabelFrame(root, text="Video Information")
        info_frame.grid(row=1, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        self.thumbnail_label = ttk.Label(info_frame, text="Thumbnail will appear here")
        self.thumbnail_label.grid(row=0, column=0, rowspan=3, padx=10, pady=5, sticky="nsew")

        ttk.Label(info_frame, text="Title:").grid(row=0, column=1, padx=5, pady=2, sticky="w")
        self.title_label = ttk.Label(info_frame, text="N/A", wraplength=350)
        self.title_label.grid(row=0, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(info_frame, text="Duration:").grid(row=1, column=1, padx=5, pady=2, sticky="w")
        self.duration_label = ttk.Label(info_frame, text="N/A")
        self.duration_label.grid(row=1, column=2, padx=5, pady=2, sticky="w")

        ttk.Label(info_frame, text="Size:").grid(row=2, column=1, padx=5, pady=2, sticky="w")
        self.size_label = ttk.Label(info_frame, text="N/A")
        self.size_label.grid(row=2, column=2, padx=5, pady=2, sticky="w")

        options_frame = ttk.LabelFrame(root, text="Download Options")
        options_frame.grid(row=2, column=0, columnspan=4, padx=5, pady=5, sticky="ew")

        ttk.Label(options_frame, text="Download Type:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.download_type = tk.StringVar(value="video")
        self.video_radio = ttk.Radiobutton(options_frame, text="Video + Audio", variable=self.download_type, value="video", command=self.update_resolution_options)
        self.video_radio.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        self.audio_radio = ttk.Radiobutton(options_frame, text="Audio Only", variable=self.download_type, value="audio", command=self.update_resolution_options)
        self.audio_radio.grid(row=0, column=2, padx=5, pady=5, sticky="w")

        ttk.Label(options_frame, text="Resolution (Video):").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.resolution_var = tk.StringVar()
        self.resolution_menu = ttk.Combobox(options_frame, textvariable=self.resolution_var, state="disabled", width=20)
        self.resolution_menu.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="w")
        self.resolution_menu.bind("<<ComboboxSelected>>", self.update_file_size)

        ttk.Label(root, text="Download Folder:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.path_label = ttk.Label(root, text=self.download_path, relief="sunken", width=50)
        self.path_label.grid(row=3, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        self.browse_button = ttk.Button(root, text="Browse", command=self.browse_folder)
        self.browse_button.grid(row=3, column=3, padx=5, pady=5)

        self.download_button = ttk.Button(root, text="Download", command=self.start_download_thread, state="disabled")
        self.download_button.grid(row=4, column=0, columnspan=4, padx=5, pady=10)

        self.progress_bar = ttk.Progressbar(root, orient="horizontal", length=600, mode="determinate")
        self.progress_bar.grid(row=5, column=0, columnspan=4, padx=5, pady=5)

        self.status_label = ttk.Label(root, text="Enter a URL and click 'Fetch Info'")
        self.status_label.grid(row=6, column=0, columnspan=4, padx=5, pady=5)

        info_frame.columnconfigure(2, weight=1)

    def _disable_ui_for_processing(self):
        self.fetch_button.config(state="disabled")
        self.download_button.config(state="disabled")
        self.video_radio.config(state="disabled")
        self.audio_radio.config(state="disabled")
        self.resolution_menu.config(state="disabled")
        self.browse_button.config(state="disabled")

    def _enable_ui_after_processing(self):
        self.fetch_button.config(state="normal")
        # Download button state depends on stream selection, handled elsewhere
        self.video_radio.config(state="normal")
        self.audio_radio.config(state="normal")
        if self.download_type.get() == "video" and self.resolution_menu['values']:
            self.resolution_menu.config(state="readonly")
        else:
            self.resolution_menu.config(state="disabled")
        self.browse_button.config(state="normal")
        # Enable download button if a stream is selected
        if self.selected_stream:
            self.download_button.config(state="normal")


    def fetch_video_info(self):
        url = self.url_entry.get()
        if not url:
            messagebox.showerror("Error", "Please enter a YouTube URL.")
            return

        self.status_label.config(text="Fetching video information...")
        self._disable_ui_for_processing()
        self.resolution_var.set("")
        self.title_label.config(text="N/A")
        self.duration_label.config(text="N/A")
        self.size_label.config(text="N/A")
        self.thumbnail_label.image = None
        self.thumbnail_label.config(image=None, text="Loading thumbnail...")

        threading.Thread(target=self._fetch_video_info_thread, args=(url,), daemon=True).start()

    def _fetch_video_info_thread(self, url):
        try:
            self.yt = YouTube(url,
                              on_progress_callback=self.on_progress,
                              on_complete_callback=self.on_complete)

            self.root.after(0, lambda: self.title_label.config(text=self.yt.title))
            duration_sec = self.yt.length
            duration_str = f"{duration_sec // 60}m {duration_sec % 60}s"
            self.root.after(0, lambda: self.duration_label.config(text=duration_str))
            self.load_thumbnail(self.yt.thumbnail_url)
            self.update_resolution_options()
            self.root.after(0, lambda: self.status_label.config(text="Video info fetched. Select options and download."))
            # Don't enable download button here directly, update_resolution_options/update_file_size will handle it

        except (RegexMatchError, PytubeError) as e: # Catch specific Pytube errors too
            error_message_str = str(e)
            if "HTTP Error 400" in error_message_str or "HTTP Error 410" in error_message_str:
                 error_message_str += "\n\nTry updating pytube: pip install --upgrade pytube"
            self.root.after(0, lambda err_msg=error_message_str: messagebox.showerror("Fetch Error", f"{err_msg}"))
            self.root.after(0, lambda err_msg=error_message_str: self.status_label.config(text=f"Fetch Error: {err_msg.splitlines()[0]}")) # Show first line
        except VideoUnavailable:
            self.root.after(0, lambda: messagebox.showerror("Error", "Video is unavailable (private, deleted, etc.)."))
            self.root.after(0, lambda: self.status_label.config(text="Video unavailable."))
        except Exception as e: # Generic catch-all
            error_message_str = str(e)
            self.root.after(0, lambda err_msg=error_message_str: messagebox.showerror("Error", f"An unexpected error occurred: {err_msg}"))
            self.root.after(0, lambda err_msg=error_message_str: self.status_label.config(text=f"Error: {err_msg}"))
        finally:
            self.root.after(0, self._enable_ui_after_processing)


    def load_thumbnail(self, url):
        try:
            response = requests.get(url, stream=True, timeout=5) # Added timeout
            response.raise_for_status()
            img_data = response.raw.read()
            img = Image.open(BytesIO(img_data))
            img.thumbnail((160, 90))
            self.thumbnail_photo = ImageTk.PhotoImage(img)
            self.root.after(0, lambda: (
                self.thumbnail_label.config(image=self.thumbnail_photo, text=""),
                setattr(self.thumbnail_label, 'image', self.thumbnail_photo)
            ))
        except Exception as e:
            self.thumbnail_photo = None
            self.root.after(0, lambda: (
                self.thumbnail_label.config(text="No thumbnail", image=''),
                setattr(self.thumbnail_label, 'image', None)
            ))
            print(f"Error loading thumbnail: {e}")


    def update_resolution_options(self):
        if not self.yt:
            return

        download_mode = self.download_type.get()
        self.resolution_menu.set('')
        self.size_label.config(text="N/A")
        self.selected_stream = None # Reset selected stream
        self.download_button.config(state="disabled") # Disable download button initially

        if download_mode == "video":
            self.streams = self.yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc()
            resolutions = [stream.resolution for stream in self.streams if stream.resolution]
            if resolutions:
                unique_resolutions = sorted(list(set(resolutions)), key=lambda x: int(x[:-1]), reverse=True)
                self.resolution_menu.config(values=unique_resolutions, state="readonly")
                if unique_resolutions: # Check if list is not empty
                    self.resolution_menu.set(unique_resolutions[0])
            else:
                self.resolution_menu.config(values=[], state="disabled")
                self.status_label.config(text="No progressive MP4 streams found for video.")
        elif download_mode == "audio":
            self.streams = self.yt.streams.filter(only_audio=True, file_extension='mp4').order_by('abr').desc()
            self.resolution_menu.config(values=[], state="disabled")
            if self.streams:
                self.selected_stream = self.streams.first() # Directly select best audio
            else:
                 self.status_label.config(text="No audio MP4 streams found.")
        
        self.update_file_size()


    def update_file_size(self, event=None):
        if not self.yt:
            return

        download_mode = self.download_type.get()
        # self.selected_stream is reset in update_resolution_options or set for audio there

        if download_mode == "video":
            selected_res = self.resolution_var.get()
            self.selected_stream = None # Ensure it's None before checking
            if selected_res and self.streams:
                for s in self.streams: # self.streams should be video streams here
                    if s.resolution == selected_res:
                        self.selected_stream = s
                        break
        # For audio, self.selected_stream is already set in update_resolution_options if available

        if self.selected_stream:
            filesize_mb = self.selected_stream.filesize / (1024 * 1024)
            self.size_label.config(text=f"{filesize_mb:.2f} MB")
            self.download_button.config(state="normal")
        else:
            self.size_label.config(text="N/A")
            self.download_button.config(state="disabled")


    def browse_folder(self):
        folder_selected = filedialog.askdirectory()
        if folder_selected:
            self.download_path = folder_selected
            self.path_label.config(text=self.download_path)

    def start_download_thread(self):
        if not self.yt or not self.selected_stream:
            messagebox.showerror("Error", "No video fetched or stream selected.")
            return
        if not self.download_path:
            messagebox.showerror("Error", "Please select a download folder.")
            return

        self._disable_ui_for_processing()
        self.progress_bar["value"] = 0
        self.status_label.config(text=f"Downloading: {self.selected_stream.title}...")
        threading.Thread(target=self._download_video, args=(self.selected_stream,), daemon=True).start()

    def _download_video(self, stream_to_download):
        try:
            stream_to_download.download(output_path=self.download_path)
            # on_complete callback handles success
        except Exception as e:
            error_message_str = str(e)
            self.root.after(0, lambda err_msg=error_message_str: messagebox.showerror("Download Error", f"Failed to download: {err_msg}"))
            self.root.after(0, lambda err_msg=error_message_str: self.status_label.config(text=f"Error during download: {err_msg.splitlines()[0]}"))
            self.root.after(0, self._enable_ui_after_processing) # Re-enable UI on error


    def on_progress(self, stream, chunk, bytes_remaining):
        total_size = stream.filesize
        bytes_downloaded = total_size - bytes_remaining
        percentage = (bytes_downloaded / total_size) * 100
        self.root.after(0, lambda: self.progress_bar.config(value=percentage))
        self.root.after(0, lambda: self.status_label.config(text=f"Downloading... {percentage:.2f}%"))


    def on_complete(self, stream, file_path):
        self.root.after(0, lambda: self.status_label.config(text=f"Download Complete! Saved to: {file_path}"))
        self.root.after(0, lambda: messagebox.showinfo("Success", f"Download complete!\nSaved to: {file_path}"))
        self.root.after(0, self.progress_bar.config(value=0))
        self.root.after(0, self._enable_ui_after_processing)


if __name__ == "__main__":
    root = tk.Tk()
    app = YouTubeDownloaderApp(root)
    root.mainloop()