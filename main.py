import sys
import os
import numpy as np
import sounddevice as sd
import soundfile as sf
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QSizePolicy
)
from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QPainter, QColor, QBrush, QFont


class AudioFileVisualizer(QWidget):
    def __init__(self):
        super().__init__()
        self.data = None
        self.fs = None
        self.display_data = None
        self.current_frame = 0
        self.chunk_size = 1024
        self.audio_buffer = np.zeros(self.chunk_size)
        self.stream = None

        self.timer = QTimer()
        self.timer.timeout.connect(self.update)
        self.timer.start(16) #62.5fps

        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def load_file(self, file_path):

        self.stop()

        #äänitiedosto muunnetaan numpy taulukoksi
        self.data, self.fs = sf.read(file_path)

        print(self.fs)

        #stereo -> mono
        if len(self.data.shape) > 1:
            self.display_data = self.data.mean(axis=1)
        else:
            self.display_data = self.data

        self.current_frame = 0
        self.audio_buffer = np.zeros(self.chunk_size)

        channels = self.data.shape[1] if len(self.data.shape) > 1 else 1
        self.stream = sd.OutputStream(
            samplerate=self.fs,
            channels=channels,
            callback=self.audio_callback,
            blocksize=self.chunk_size
        )
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def audio_callback(self, outdata, frames, time, status):
        
        #onko biisiä jäljellä
        remainder = len(self.data) - self.current_frame
        if remainder <= 0:
            outdata.fill(0)
            return

        #biisin lopussa pienempi palanen
        chunk_to_play = min(frames, remainder)
        #äänentoistoon chunk
        play_segment = self.data[self.current_frame : self.current_frame + chunk_to_play]


        #jos stereo: lähetä äänikortille, jos mono: muotoile
        if len(self.data.shape) > 1:
            outdata[:chunk_to_play] = play_segment
        else:
            outdata[:chunk_to_play] = play_segment.reshape(-1, 1)

        if chunk_to_play < frames:
            outdata[chunk_to_play:] = 0

        #päivitetään visualisoijalle chunk
        self.audio_buffer = self.display_data[self.current_frame : self.current_frame + self.chunk_size]
        #inkrementoidaan seuraavaan
        self.current_frame += chunk_to_play

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing) 
        painter.fillRect(self.rect(), QColor(18, 18, 18))


        if self.data is None:
            painter.setPen(QColor(80, 80, 80))
            font = QFont("Helvetica", 20)
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Valitse äänitiedosto vasemmasta yläkulmasta")
            return

        #varmistetaan, että buffer on täynnä
        if len(self.audio_buffer) < self.chunk_size:
            return

        #fourier muunnos
        fft_data = np.abs(np.fft.rfft(self.audio_buffer))[:180] 


        padding = 3
        num_bars = len(fft_data)
        bar_width = (self.width() - (num_bars + 1) * padding) / num_bars

        for i in range(num_bars):
            magnitude = np.log1p(fft_data[i]) * 80
            bar_height = min(magnitude, self.height() * 0.9)

            x = padding + i * (bar_width + padding)
            y = (self.height() - bar_height) / 2

            painter.setBrush(QBrush(QColor(30, 215, 96)))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(int(x), int(y), int(bar_width), int(bar_height), 4, 4)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Audio File Visualizer")
        self.resize(1000, 560)


        self.setStyleSheet("background-color: #121212;")

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)


        top_bar = QHBoxLayout()
        top_bar.setSpacing(12)

        self.open_btn = QPushButton("Avaa tiedosto")
        self.open_btn.setFixedHeight(40)
        self.open_btn.setStyleSheet("""
            QPushButton {
                background-color: #1ED760;
                color: #000000;
                border: none;
                border-radius: 20px;
                padding: 0 24px;
                font-size: 14px;
                font-weight: 600;
                font-family: Helvetica;
            }
            QPushButton:hover {
                background-color: #14903F;
            }
            QPushButton:pressed {
                background-color: #169c46;
            }
        """)
        self.open_btn.clicked.connect(self.open_file)

        self.file_label = QLabel("Ei tiedostoa valittuna")
        self.file_label.setStyleSheet("""
            color: #b3b3b3;
            font-size: 13px;
            font-family: Helvetica;
        """)
        self.file_label.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)

        top_bar.addWidget(self.open_btn)
        top_bar.addWidget(self.file_label, stretch=1)
        layout.addLayout(top_bar)

        self.visualizer = AudioFileVisualizer()
        layout.addWidget(self.visualizer, stretch=1)

    def open_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Valitse äänitiedosto",
            "",
            "Äänitiedostot (*.wav *.mp3 *.flac *.ogg *.aiff *.aif);;Kaikki tiedostot (*)"
        )
        if file_path:
            self.file_label.setText(os.path.basename(file_path))
            try:
                self.visualizer.load_file(file_path)
            except Exception as e:
                self.file_label.setText(f"Virhe: {e}")

    def closeEvent(self, event):
        self.visualizer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

    