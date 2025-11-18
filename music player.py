import sys
import os
import random
from PyQt6 import QtWidgets, QtCore, QtGui, QtMultimedia, QtMultimediaWidgets
from mutagen.easyid3 import EasyID3
from mutagen.mp3 import MP3
from mutagen.wave import WAVE

HISTORY_FILE = "song_history.txt"

class VideoWidget(QtMultimediaWidgets.QVideoWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.exit_fullscreen_callback = None

    def keyPressEvent(self, event):
        if event.key() == QtCore.Qt.Key.Key_Escape:
            if self.isFullScreen() and self.exit_fullscreen_callback:
                self.exit_fullscreen_callback()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'exit_fullscreen_overlay_btn'):
            btn_width = self.exit_fullscreen_overlay_btn.sizeHint().width()
            self.exit_fullscreen_overlay_btn.move(self.width() - btn_width - 20, 20)


class MusicPlayer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Ultimate Music Player")
        self.resize(700, 550)
        self.playlist = []
        self.current_index = 0
        self.shuffle = False
        self.repeat_mode = "off"
        self.is_paused = False
        self.position_updating = False
        self.is_video = False
        self.current_media_url = None

        self.audio_output = QtMultimedia.QAudioOutput()
        self.player = QtMultimedia.QMediaPlayer()
        self.player.setAudioOutput(self.audio_output)

        self.video_widget = VideoWidget()
        self.video_widget.setMinimumHeight(300)
        self.player.setVideoOutput(self.video_widget)

        self.video_widget.exit_fullscreen_callback = self.exit_fullscreen

        self.exit_fullscreen_overlay_btn = QtWidgets.QPushButton("Exit Fullscreen", self.video_widget)
        self.exit_fullscreen_overlay_btn.setStyleSheet("""
            #background-color: rgba(0, 0, 0, 150);
            #color: white;
            #font-weight: bold;
            #padding: 5px 10px;
            #border-radius: 5px;
        #""")

        self.exit_fullscreen_overlay_btn.hide()
        self.exit_fullscreen_overlay_btn.clicked.connect(self.exit_fullscreen)
        self.video_widget.exit_fullscreen_overlay_btn = self.exit_fullscreen_overlay_btn

        self.load_song_history()
        self.setup_ui()
        self.bind_signals()

        if self.playlist:
            self.load_current_song_info()

    def setup_ui(self):
        main_layout = QtWidgets.QVBoxLayout(self)

        info_layout = QtWidgets.QHBoxLayout()
        self.song_info_label = QtWidgets.QLabel("No song loaded")
        self.song_info_label.setMinimumWidth(300)
        info_layout.addWidget(self.song_info_label)
        info_layout.addStretch()
        main_layout.addLayout(info_layout)

        main_layout.addWidget(self.video_widget)
        self.video_widget.hide()

        self.playlist_widget = QtWidgets.QListWidget()
        self.playlist_widget.addItems([os.path.basename(f) for f in self.playlist])
        main_layout.addWidget(self.playlist_widget)

        controls_layout = QtWidgets.QHBoxLayout()

        self.load_button = QtWidgets.QPushButton("Load Songs")
        self.prev_button = QtWidgets.QPushButton("Prev")
        self.play_button = QtWidgets.QPushButton("Play")
        self.pause_button = QtWidgets.QPushButton("Pause")
        self.stop_button = QtWidgets.QPushButton("Stop")
        self.next_button = QtWidgets.QPushButton("Next")
        self.shuffle_button = QtWidgets.QPushButton("Shuffle Off")
        self.repeat_button = QtWidgets.QPushButton("Repeat Off")
        self.fullscreen_button = QtWidgets.QPushButton("Fullscreen")
        self.exit_fullscreen_button = QtWidgets.QPushButton("Exit Fullscreen")
        self.exit_fullscreen_button.setEnabled(False)
        self.exit_fullscreen_button.clicked.connect(self.exit_fullscreen)
        self.save_playlist_button = QtWidgets.QPushButton("Save Playlist")
        self.load_playlist_button = QtWidgets.QPushButton("Load Playlist")

        for btn in [self.load_button, self.prev_button, self.play_button, self.pause_button,
                    self.stop_button, self.next_button, self.shuffle_button, self.repeat_button,
                    self.fullscreen_button, self.exit_fullscreen_button,
                    self.save_playlist_button, self.load_playlist_button]:
            controls_layout.addWidget(btn)

        main_layout.addLayout(controls_layout)

        progress_layout = QtWidgets.QHBoxLayout()
        self.elapsed_label = QtWidgets.QLabel("00:00")
        self.progress_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.total_label = QtWidgets.QLabel("00:00")
        progress_layout.addWidget(self.elapsed_label)
        progress_layout.addWidget(self.progress_slider)
        progress_layout.addWidget(self.total_label)
        main_layout.addLayout(progress_layout)

        volume_layout = QtWidgets.QHBoxLayout()
        volume_label = QtWidgets.QLabel("Volume")
        self.volume_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(70)
        volume_layout.addWidget(volume_label)
        volume_layout.addWidget(self.volume_slider)
        main_layout.addLayout(volume_layout)

    def bind_signals(self):
        self.load_button.clicked.connect(self.load_songs)
        self.prev_button.clicked.connect(self.prev_song)
        self.play_button.clicked.connect(self.play_song)
        self.pause_button.clicked.connect(self.pause_song)
        self.stop_button.clicked.connect(self.stop_song)
        self.next_button.clicked.connect(self.next_song)
        self.shuffle_button.clicked.connect(self.toggle_shuffle)
        self.repeat_button.clicked.connect(self.toggle_repeat)
        self.fullscreen_button.clicked.connect(self.toggle_fullscreen)
        self.save_playlist_button.clicked.connect(self.save_playlist)
        self.load_playlist_button.clicked.connect(self.load_playlist)
        self.playlist_widget.itemDoubleClicked.connect(self.playlist_double_click)
        self.progress_slider.sliderMoved.connect(self.seek_position)
        self.player.positionChanged.connect(self.update_position)
        self.player.durationChanged.connect(self.update_duration)
        self.volume_slider.valueChanged.connect(self.change_volume)
        self.player.mediaStatusChanged.connect(self.handle_media_status)

    def load_songs(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select Audio/Video Files", "",
                                                          "Media Files (*.mp3 *.wav *.mp4)")
        if files:
            added_new = False
            for f in files:
                if f not in self.playlist:
                    self.playlist.append(f)
                    added_new = True
            if added_new:
                self.save_song_history()
                self.update_playlist_widget()
                if len(self.playlist) == len(files):
                    self.current_index = 0
                    self.load_current_song_info()
                    self.play_song()

    def update_playlist_widget(self):
        self.playlist_widget.clear()
        self.playlist_widget.addItems([os.path.basename(f) for f in self.playlist])
        self.playlist_widget.setCurrentRow(self.current_index)

    def load_current_song_info(self):
        if not self.playlist:
            self.song_info_label.setText("No song loaded")
            self.total_label.setText("00:00")
            self.video_widget.hide()
            self.is_video = False
            return
        filepath = self.playlist[self.current_index]
        ext = os.path.splitext(filepath)[1].lower()
        length = 0
        try:
            if ext == ".mp3":
                audio = EasyID3(filepath)
                mp3 = MP3(filepath)
                length = mp3.info.length
                title = audio.get('title', [os.path.basename(filepath)])[0]
                artist = audio.get('artist', ['Unknown Artist'])[0]
                album = audio.get('album', ['Unknown Album'])[0]
                self.song_info_label.setText(f"{title} - {artist} [{album}]")
                self.video_widget.hide()
                self.is_video = False
            elif ext == ".wav":
                wave = WAVE(filepath)
                length = wave.info.length
                self.song_info_label.setText(os.path.basename(filepath))
                self.video_widget.hide()
                self.is_video = False
            elif ext == ".mp4":
                self.song_info_label.setText(os.path.basename(filepath))
                self.video_widget.show()
                self.is_video = True
            else:
                self.song_info_label.setText(os.path.basename(filepath))
                self.video_widget.hide()
                self.is_video = False
        except Exception:
            self.song_info_label.setText(os.path.basename(filepath))
            self.video_widget.hide()
            self.is_video = False
        self.total_label.setText(self.format_time(length) if length > 0 else "--:--")

    def play_song(self):
        if not self.playlist:
            QtWidgets.QMessageBox.warning(self, "No songs", "Load some songs first!")
            return
        filepath = self.playlist[self.current_index]
        url = QtCore.QUrl.fromLocalFile(filepath)

        if self.current_media_url != url:
            self.player.setSource(url)
            self.current_media_url = url

        self.player.play()
        self.is_paused = False
        self.update_playlist_widget()
        self.load_current_song_info()

    def pause_song(self):
        if self.is_paused:
            self.player.play()
            self.is_paused = False
        else:
            self.player.pause()
            self.is_paused = True

    def stop_song(self):
        self.player.stop()
        self.progress_slider.setValue(0)
        self.elapsed_label.setText("00:00")
        if self.is_video:
            self.video_widget.hide()

    def next_song(self):
        if not self.playlist:
            return
        if self.shuffle:
            self.current_index = random.randint(0, len(self.playlist) - 1)
        else:
            self.current_index = (self.current_index + 1) % len(self.playlist)
        self.current_media_url = None
        self.play_song()

    def prev_song(self):
        if not self.playlist:
            return
        self.current_index = (self.current_index - 1) % len(self.playlist)
        self.current_media_url = None
        self.play_song()

    def toggle_shuffle(self):
        self.shuffle = not self.shuffle
        self.shuffle_button.setText("Shuffle On" if self.shuffle else "Shuffle Off")

    def toggle_repeat(self):
        modes = ["off", "one", "all"]
        current = self.repeat_mode
        next_mode = modes[(modes.index(current) + 1) % len(modes)]
        self.repeat_mode = next_mode
        self.repeat_button.setText(f"Repeat {next_mode.capitalize()}")

    def toggle_fullscreen(self):
        if self.is_video and not self.video_widget.isFullScreen():
            self.video_widget.setFullScreen(True)
            self.fullscreen_button.setEnabled(False)
            self.exit_fullscreen_button.setEnabled(True)
            self.exit_fullscreen_overlay_btn.show()

    def exit_fullscreen(self):
        if self.video_widget.isFullScreen():
            self.video_widget.setFullScreen(False)
            self.fullscreen_button.setEnabled(True)
            self.exit_fullscreen_button.setEnabled(False)
            self.exit_fullscreen_overlay_btn.hide()

    def update_position(self, position):
        if not self.position_updating:
            self.position_updating = True
            duration = self.player.duration()
            if duration > 0:
                self.progress_slider.setValue(int((position / duration) * 1000))
                self.elapsed_label.setText(self.format_time(position / 1000))
            else:
                self.progress_slider.setValue(0)
                self.elapsed_label.setText("--:--")
            self.position_updating = False

    def update_duration(self, duration):
        self.total_label.setText(self.format_time(duration / 1000) if duration > 0 else "--:--")

    def seek_position(self, position):
        duration = self.player.duration()
        if duration > 0:
            new_pos = (position / 1000) * duration
            self.player.setPosition(int(new_pos))

    def change_volume(self, val):
        volume = val / 100
        self.audio_output.setVolume(volume)

    def playlist_double_click(self, item):
        row = self.playlist_widget.currentRow()
        if row != -1:
            self.current_index = row
            self.current_media_url = None
            self.play_song()

    def save_playlist(self):
        if not self.playlist:
            QtWidgets.QMessageBox.warning(self, "Empty playlist", "No songs to save!")
            return
        file, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Playlist", "", "Text Files (*.txt)")
        if file:
            with open(file, "w", encoding="utf-8") as f:
                for song in self.playlist:
                    f.write(song + "\n")
            QtWidgets.QMessageBox.information(self, "Saved", f"Playlist saved to {file}")

    def load_playlist(self):
        file, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Playlist", "", "Text Files (*.txt)")
        if file:
            with open(file, "r", encoding="utf-8") as f:
                self.playlist = [line.strip() for line in f.readlines()]
            self.current_index = 0
            self.current_media_url = None
            self.save_song_history()
            self.update_playlist_widget()
            self.load_current_song_info()
            self.play_song()

    def save_song_history(self):
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                for song in self.playlist:
                    f.write(song + "\n")
        except Exception:
            pass

    def load_song_history(self):
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    self.playlist = [line.strip() for line in f.readlines()]
            except Exception:
                self.playlist = []
        else:
            self.playlist = []

    def handle_media_status(self, status):
        if status == QtMultimedia.QMediaPlayer.MediaStatus.EndOfMedia:
            if self.repeat_mode == "one":
                self.current_media_url = None
                self.play_song()
            elif self.repeat_mode == "all":
                self.current_media_url = None
                self.next_song()
            else:
                self.stop_song()

    def format_time(self, seconds):
        m, s = divmod(int(seconds), 60)
        return f"{m:02}:{s:02}"

    def closeEvent(self, event):
        self.save_song_history()
        self.player.stop()
        event.accept()

def main():
    app = QtWidgets.QApplication(sys.argv)
    player = MusicPlayer()
    player.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()