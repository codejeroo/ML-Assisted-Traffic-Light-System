import sys
import cv2
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QPushButton, QFrame, QGridLayout)
from PyQt5.QtGui import QImage, QPixmap, QFont, QColor, QPalette
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
from ultralytics import YOLO
import time
import serial

class VideoThread(QThread):
    frame_signal = pyqtSignal(np.ndarray)
    stats_signal = pyqtSignal(dict)
    log_signal = pyqtSignal(str)
    q
    def __init__(self):
        super().__init__()
        self.model = YOLO('model/weights/best.pt')
        self.cap = cv2.VideoCapture(0)
        self.running = True
        
        # Serial connection
        self.ser = None
        self.connect_to_esp32()
        
        # Traffic light state
        self.tl1_state = "GREEN"  # S1 (E-W)
        self.tl4_state = "GREEN"  # S4 (E-W)
        self.tl2_state = "RED"    # S2 (N-S)
        self.tl3_state = "RED"    # S3 (N-S)
        self.tl1_green_start = time.time()
        self.tl4_green_start = time.time()
        self.tl2_green_start = 0
        self.tl3_green_start = 0
        self.current_tl1_duration = 5
        self.current_tl4_duration = 5
        self.current_tl2_duration = 5
        self.current_tl3_duration = 5
        self.current_cycle_direction = "EW"
        self.frame_count = 0
        
    def connect_to_esp32(self):
        try:
            self.ser = serial.Serial("COM3", 115200, timeout=1)
            time.sleep(2)
            self.log_signal.emit("[SYSTEM] ✓ Connected to ESP32 on COM3")
        except serial.SerialException as e:
            self.log_signal.emit(f"[ERROR] ✗ Failed to connect: {e}")
            
    def send_command(self, lane, color):
        if self.ser is None or not self.ser.is_open:
            return False
        try:
            command = f"{lane}:{color}\n"
            self.ser.write(command.encode())
            self.log_signal.emit(f"[SENT] >>> {lane} {color}")
            return True
        except serial.SerialException as e:
            self.log_signal.emit(f"[ERROR] Serial error: {e}")
            return False
    
    def send_paired_command(self, lane1, lane2, color):
        if self.ser is None or not self.ser.is_open:
            return False
        try:
            command = f"{lane1}:{lane2}:{color}\n"
            self.ser.write(command.encode())
            self.log_signal.emit(f"[SENT] >>> {lane1} & {lane2} {color}")
            return True
        except serial.SerialException as e:
            self.log_signal.emit(f"[ERROR] Serial error: {e}")
            return False
    
    def calculate_green_time(self, north_count, south_count, east_count, west_count, direction):
        """Calculate dynamic green time based on individual car counts"""
        if direction == "NS":
            ns_max = max(north_count, south_count)
            ew_max = max(east_count, west_count)
            
            if ns_max > ew_max:
                if ns_max == 0:
                    return 5
                elif ns_max == 1:
                    return 10
                else:
                    return 20 + (ns_max - 2) * 10
            elif ns_max > 0:
                return 5
            else:
                return 5
        else:  # EW
            ew_max = max(east_count, west_count)
            ns_max = max(north_count, south_count)
            
            if ew_max > ns_max:
                if ew_max == 0:
                    return 5
                elif ew_max == 1:
                    return 10
                else:
                    return 20 + (ew_max - 2) * 10
            elif ew_max > 0:
                return 5
            else:
                return 5
    
    def run(self):
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                break
            
            # Get frame dimensions
            height, width = frame.shape[:2]
            
            # Define thresholds for all directions
            north_threshold_y = height // 2 - 100
            south_threshold_y = height // 2 + 100
            west_threshold_x = width // 2 - 120
            east_threshold_x = width // 2 + 120
            
            # Detection
            results = self.model(frame, conf=0.55, iou=0.3, imgsz=416)
            
            # Reset counters
            from_west = 0
            from_north = 0
            from_east = 0
            from_south = 0
            
            # Process detections
            for i in range(len(results[0].boxes)):
                bbox = results[0].boxes.xyxy[i]
                center_x = (bbox[0] + bbox[2]) / 2
                center_y = (bbox[1] + bbox[3]) / 2
                
                # Determine direction
                if center_x < width // 2 and center_y < height // 2:
                    if center_y < north_threshold_y:
                        from_north += 1
                    elif center_x < width // 2 - 120:
                        from_west += 1
                    else:
                        from_north += 1
                elif center_x > width // 2 and center_y < height // 2:
                    if center_y < north_threshold_y:
                        from_north += 1
                    elif center_x > east_threshold_x:
                        from_east += 1
                    else:
                        from_north += 1
                elif center_x < width // 2 and center_y > height // 2:
                    if center_y > south_threshold_y:
                        from_south += 1
                    elif center_x < west_threshold_x:
                        from_west += 1
                    else:
                        from_south += 1
                else:
                    if center_y > south_threshold_y:
                        from_south += 1
                    elif center_x > east_threshold_x:
                        from_east += 1
                    else:
                        from_south += 1
            
            # AUTO-CYCLE logic
            current_time = time.time()
            
            if self.current_cycle_direction == "EW":
                elapsed = current_time - self.tl1_green_start
                new_duration = self.calculate_green_time(from_north, from_south, from_east, from_west, "EW")
                if new_duration > self.current_tl1_duration:
                    self.current_tl1_duration = new_duration
                    self.current_tl4_duration = new_duration
                    self.log_signal.emit(f"[AUTO] Duration extended to {new_duration}s")
                
                if elapsed >= self.current_tl1_duration and self.tl1_state == "GREEN":
                    green_duration = self.calculate_green_time(from_north, from_south, from_east, from_west, "NS")
                    
                    self.tl2_state = "GREEN"
                    self.tl3_state = "GREEN"
                    self.tl2_green_start = current_time
                    self.tl3_green_start = current_time
                    self.current_tl2_duration = green_duration
                    self.current_tl3_duration = green_duration
                    self.current_cycle_direction = "NS"
                    
                    self.send_paired_command("S2", "S3", "GREEN")
                    self.tl1_state = "RED"
                    self.tl4_state = "RED"
                    self.send_paired_command("S1", "S4", "RED")
                    self.log_signal.emit(f"[AUTO] E-W → N-S GREEN (Duration: {green_duration}s)")
            else:
                elapsed = current_time - self.tl2_green_start
                new_duration = self.calculate_green_time(from_north, from_south, from_east, from_west, "NS")
                if new_duration > self.current_tl2_duration:
                    self.current_tl2_duration = new_duration
                    self.current_tl3_duration = new_duration
                    self.log_signal.emit(f"[AUTO] Duration extended to {new_duration}s")
                
                if elapsed >= self.current_tl2_duration and self.tl2_state == "GREEN":
                    green_duration = self.calculate_green_time(from_north, from_south, from_east, from_west, "EW")
                    
                    self.tl1_state = "GREEN"
                    self.tl4_state = "GREEN"
                    self.tl1_green_start = current_time
                    self.tl4_green_start = current_time
                    self.current_tl1_duration = green_duration
                    self.current_tl4_duration = green_duration
                    self.current_cycle_direction = "EW"
                    
                    self.send_paired_command("S1", "S4", "GREEN")
                    self.tl2_state = "RED"
                    self.tl3_state = "RED"
                    self.send_paired_command("S2", "S3", "RED")
                    self.log_signal.emit(f"[AUTO] N-S → E-W GREEN (Duration: {green_duration}s)")
            
            # Annotate frame
            annotated_frame = results[0].plot()
            
            # Emit signals
            self.frame_signal.emit(annotated_frame)
            
            # Calculate remaining time for each traffic light
            if self.tl1_state == "GREEN":
                tl1_remaining = max(0, self.current_tl1_duration - (current_time - self.tl1_green_start))
            else:
                tl1_remaining = 0
            if self.tl4_state == "GREEN":
                tl4_remaining = max(0, self.current_tl4_duration - (current_time - self.tl4_green_start))
            else:
                tl4_remaining = 0
            if self.tl2_state == "GREEN":
                tl2_remaining = max(0, self.current_tl2_duration - (current_time - self.tl2_green_start))
            else:
                tl2_remaining = 0
            if self.tl3_state == "GREEN":
                tl3_remaining = max(0, self.current_tl3_duration - (current_time - self.tl3_green_start))
            else:
                tl3_remaining = 0

            stats = {
                'north': from_north,
                'south': from_south,
                'east': from_east,
                'west': from_west,
                'ns_total': from_north + from_south,
                'we_total': from_west + from_east,
                'tl1_state': self.tl1_state,
                'tl1_remaining': int(tl1_remaining),
                'tl2_state': self.tl2_state,
                'tl2_remaining': int(tl2_remaining),
                'tl3_state': self.tl3_state,
                'tl3_remaining': int(tl3_remaining),
                'tl4_state': self.tl4_state,
                'tl4_remaining': int(tl4_remaining)
            }
            self.stats_signal.emit(stats)
            
            self.frame_count += 1
            time.sleep(0.03)  # ~30 FPS
    
    def stop(self):
        self.running = False
        if self.ser:
            self.ser.close()
        self.cap.release()

class TrafficLightGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("LIVE TRAFFIC FEED - INTERSECTION A4")
        self.setGeometry(100, 100, 1400, 900)
        self.setStyleSheet("background-color: #0a0e27;")
        
        # Central widget (vertical: header, content, footer)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        outer_layout = QVBoxLayout(central_widget)
        outer_layout.setContentsMargins(12, 12, 12, 12)
        outer_layout.setSpacing(12)

        # Header
        header = QLabel("ECE 110 - Feedback and Control Systems Project")
        header.setFont(QFont("Arial", 16, QFont.Bold))
        header.setStyleSheet("color: #00ffff; padding: 8px;")
        header.setAlignment(Qt.AlignCenter)
        outer_layout.addWidget(header)

        # Content layout (main UI columns)
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(15, 5, 15, 5)
        main_layout.setSpacing(15)
        
        # Left side - Video feed
        left_layout = QVBoxLayout()
        
        # Video label
        self.video_label = QLabel()
        self.video_label.setMinimumSize(650, 550)
        self.video_label.setStyleSheet("""
            border: 2px solid #00ffff;
            border-radius: 10px;
            background-color: #000;
        """)
        self.video_label.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.video_label)
        
        # System status
        status_label = QLabel("SYSTEM STATUS: ACTIVE  |  SERIAL PORT: COM3  |  AI MODEL: YOLOv8 - READY")
        status_label.setFont(QFont("Courier New", 9))
        status_label.setStyleSheet("color: #00ffff; background-color: #0a0e27;")
        left_layout.addWidget(status_label)
        
        main_layout.addLayout(left_layout, 2)
        
        # Right side - Stats and Controls
        right_layout = QVBoxLayout()
        right_layout.setSpacing(20)
        
        # Car counts section
        counts_frame = self.create_stats_frame()
        right_layout.addWidget(counts_frame)
        
        # System log section
        log_frame = self.create_log_frame()
        right_layout.addWidget(log_frame)
        
        # Manual override section
        override_frame = self.create_override_frame()
        right_layout.addWidget(override_frame)
        
        right_layout.addStretch()
        
        main_layout.addLayout(right_layout, 1)

        # Add content (video + side panel) to outer layout
        outer_layout.addLayout(main_layout)

        # Footer
        footer = QLabel("Developed by Ralph Angelo Gonzaga along with its members, Kier Suralta, Jevan Monte Racaza, Laurence Alvizo and Kristel Jane Donan.")
        footer.setFont(QFont("Courier New", 9))
        footer.setStyleSheet("color: #99ccff; padding: 6px;")
        footer.setAlignment(Qt.AlignCenter)
        outer_layout.addWidget(footer)
        
        # Start video thread
        self.video_thread = VideoThread()
        self.video_thread.frame_signal.connect(self.update_frame)
        self.video_thread.stats_signal.connect(self.update_stats)
        self.video_thread.log_signal.connect(self.update_log)
        self.video_thread.start()
    
    def create_stats_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                border: 2px solid #00ffff;
                border-radius: 8px;
                background-color: #0f1435;
                padding: 10px;
            }
        """)
        
        layout = QGridLayout(frame)
        layout.setSpacing(12)

        # Title
        title = QLabel("CARS DETECTED")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        title.setStyleSheet("color: #00ffff;")
        layout.addWidget(title, 0, 0, 1, 3)

        # N-S count
        ns_label = QLabel("N-S:")
        ns_label.setFont(QFont("Arial", 10))
        ns_label.setStyleSheet("color: #888;")
        self.ns_count = QLabel("0")
        self.ns_count.setFont(QFont("Courier New", 24, QFont.Bold))
        self.ns_count.setStyleSheet("color: #00ff00;")
        layout.addWidget(ns_label, 1, 0)
        layout.addWidget(self.ns_count, 1, 1, 1, 2, alignment=Qt.AlignRight)

        # W-E count
        we_label = QLabel("W-E:")
        we_label.setFont(QFont("Arial", 10))
        we_label.setStyleSheet("color: #888;")
        self.we_count = QLabel("0")
        self.we_count.setFont(QFont("Courier New", 24, QFont.Bold))
        self.we_count.setStyleSheet("color: #00ff00;")
        layout.addWidget(we_label, 2, 0)
        layout.addWidget(self.we_count, 2, 1, 1, 2, alignment=Qt.AlignRight)

        # Traffic light status (TL1..TL4)
        lights_title = QLabel("TRAFFIC LIGHTS")
        lights_title.setFont(QFont("Arial", 11, QFont.Bold))
        lights_title.setStyleSheet("color: #00ffff;")
        layout.addWidget(lights_title, 3, 0, 1, 3)

        # TL1
        tl1_label = QLabel("TL1 (S1)")
        tl1_label.setStyleSheet("color: #ddd;")
        self.tl1_status = QLabel()
        self.tl1_status.setFixedSize(22, 22)
        self.tl1_status.setStyleSheet("border-radius:11px; background-color: #00aaff;")
        self.tl1_countdown = QLabel("0s")
        self.tl1_countdown.setFont(QFont("Courier New", 12, QFont.Bold))
        self.tl1_countdown.setStyleSheet("color: #00ffff;")
        layout.addWidget(tl1_label, 4, 0)
        layout.addWidget(self.tl1_status, 4, 1, alignment=Qt.AlignRight)
        layout.addWidget(self.tl1_countdown, 4, 2, alignment=Qt.AlignRight)

        # TL2
        tl2_label = QLabel("TL2 (S2)")
        tl2_label.setStyleSheet("color: #ddd;")
        self.tl2_status = QLabel()
        self.tl2_status.setFixedSize(22, 22)
        self.tl2_status.setStyleSheet("border-radius:11px; background-color: #d32f2f;")
        self.tl2_countdown = QLabel("0s")
        self.tl2_countdown.setFont(QFont("Courier New", 12, QFont.Bold))
        self.tl2_countdown.setStyleSheet("color: #00ffff;")
        layout.addWidget(tl2_label, 5, 0)
        layout.addWidget(self.tl2_status, 5, 1, alignment=Qt.AlignRight)
        layout.addWidget(self.tl2_countdown, 5, 2, alignment=Qt.AlignRight)

        # TL3
        tl3_label = QLabel("TL3 (S3)")
        tl3_label.setStyleSheet("color: #ddd;")
        self.tl3_status = QLabel()
        self.tl3_status.setFixedSize(22, 22)
        self.tl3_status.setStyleSheet("border-radius:11px; background-color: #d32f2f;")
        self.tl3_countdown = QLabel("0s")
        self.tl3_countdown.setFont(QFont("Courier New", 12, QFont.Bold))
        self.tl3_countdown.setStyleSheet("color: #00ffff;")
        layout.addWidget(tl3_label, 6, 0)
        layout.addWidget(self.tl3_status, 6, 1, alignment=Qt.AlignRight)
        layout.addWidget(self.tl3_countdown, 6, 2, alignment=Qt.AlignRight)

        # TL4
        tl4_label = QLabel("TL4 (S4)")
        tl4_label.setStyleSheet("color: #ddd;")
        self.tl4_status = QLabel()
        self.tl4_status.setFixedSize(22, 22)
        self.tl4_status.setStyleSheet("border-radius:11px; background-color: #00aaff;")
        self.tl4_countdown = QLabel("0s")
        self.tl4_countdown.setFont(QFont("Courier New", 12, QFont.Bold))
        self.tl4_countdown.setStyleSheet("color: #00ffff;")
        layout.addWidget(tl4_label, 7, 0)
        layout.addWidget(self.tl4_status, 7, 1, alignment=Qt.AlignRight)
        layout.addWidget(self.tl4_countdown, 7, 2, alignment=Qt.AlignRight)

        return frame
    
    def create_log_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                border: 2px solid #00ffff;
                border-radius: 8px;
                background-color: #0f1435;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("SYSTEM LOG")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        title.setStyleSheet("color: #00ffff;")
        layout.addWidget(title)
        
        # Log text area
        self.log_text = QLabel()
        self.log_text.setFont(QFont("Courier New", 8))
        self.log_text.setStyleSheet("color: #00ff00; background-color: #000; padding: 5px;")
        self.log_text.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self.log_text.setWordWrap(True)
        self.log_text.setText("[09:45:22] >>> SENT: S2_GREEN\n[09:45:15] AI: North-South Priority Set\n[09:45:15] AI: North-South Priority Set")
        layout.addWidget(self.log_text)
        
        return frame
    
    def create_override_frame(self):
        frame = QFrame()
        frame.setStyleSheet("""
            QFrame {
                border: 2px solid #00ffff;
                border-radius: 8px;
                background-color: #0f1435;
                padding: 10px;
            }
        """)
        
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("MANUAL OVERRIDE")
        title.setFont(QFont("Arial", 11, QFont.Bold))
        title.setStyleSheet("color: #00ffff;")
        layout.addWidget(title)
        
        # Buttons layout
        buttons_layout = QHBoxLayout()
        
        # Force Red All button
        self.force_red_btn = QPushButton("FORCE RED ALL")
        self.force_red_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.force_red_btn.setStyleSheet("""
            QPushButton {
                background-color: #660000;
                color: #ff6b6b;
                border: 2px solid #ff6b6b;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #770000;
            }
            QPushButton:pressed {
                background-color: #550000;
            }
        """)
        self.force_red_btn.clicked.connect(self.force_red_all)
        buttons_layout.addWidget(self.force_red_btn)
        
        # Auto mode button
        self.auto_mode_btn = QPushButton("AUTO MODE")
        self.auto_mode_btn.setFont(QFont("Arial", 10, QFont.Bold))
        self.auto_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #003366;
                color: #00ffff;
                border: 2px solid #00ffff;
                border-radius: 5px;
                padding: 8px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #004477;
            }
            QPushButton:pressed {
                background-color: #002255;
            }
        """)
        self.auto_mode_btn.clicked.connect(self.auto_mode)
        buttons_layout.addWidget(self.auto_mode_btn)
        
        layout.addLayout(buttons_layout)
        
        return frame
    
    def update_frame(self, frame):
        # Convert frame to RGB
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Resize to fit label
        h, w = rgb_frame.shape[:2]
        target_w = 640
        target_h = int(h * (target_w / w))
        rgb_frame = cv2.resize(rgb_frame, (target_w, target_h))
        
        # Convert to QImage
        h, w, ch = rgb_frame.shape
        bytes_per_line = ch * w
        qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Update label
        pixmap = QPixmap.fromImage(qt_image)
        self.video_label.setPixmap(pixmap)
    
    def update_stats(self, stats):
        self.ns_count.setText(str(stats['ns_total']))
        self.we_count.setText(str(stats['we_total']))

        # Update traffic light statuses (use blue for GREEN, red for RED to match design)
        def color_for_state(state):
            return '#00aaff' if state == 'GREEN' else '#d32f2f'

        # TL1
        if 'tl1_state' in stats:
            self.tl1_status.setStyleSheet(f"border-radius:11px; background-color: {color_for_state(stats['tl1_state'])};")
            self.tl1_countdown.setText(f"{stats.get('tl1_remaining', 0)}s")
        # TL2
        if 'tl2_state' in stats:
            self.tl2_status.setStyleSheet(f"border-radius:11px; background-color: {color_for_state(stats['tl2_state'])};")
            self.tl2_countdown.setText(f"{stats.get('tl2_remaining', 0)}s")
        # TL3
        if 'tl3_state' in stats:
            self.tl3_status.setStyleSheet(f"border-radius:11px; background-color: {color_for_state(stats['tl3_state'])};")
            self.tl3_countdown.setText(f"{stats.get('tl3_remaining', 0)}s")
        # TL4
        if 'tl4_state' in stats:
            self.tl4_status.setStyleSheet(f"border-radius:11px; background-color: {color_for_state(stats['tl4_state'])};")
            self.tl4_countdown.setText(f"{stats.get('tl4_remaining', 0)}s")
    
    def update_log(self, message):
        current_text = self.log_text.text()
        lines = current_text.split('\n')
        lines.insert(0, message)
        # Keep only last 5 messages
        if len(lines) > 5:
            lines = lines[:5]
        self.log_text.setText('\n'.join(lines))
    
    def force_red_all(self):
        self.video_thread.send_paired_command("S1", "S4", "RED")
        self.video_thread.send_paired_command("S2", "S3", "RED")
        self.update_log("[MANUAL] >>> FORCE RED ALL")
    
    def auto_mode(self):
        # Reset to auto-cycle
        current_time = time.time()
        self.video_thread.tl1_state = "GREEN"
        self.video_thread.tl4_state = "GREEN"
        self.video_thread.tl2_state = "RED"
        self.video_thread.tl3_state = "RED"
        self.video_thread.tl1_green_start = current_time
        self.video_thread.tl4_green_start = current_time
        self.video_thread.current_tl1_duration = 5
        self.video_thread.current_tl4_duration = 5
        self.video_thread.current_cycle_direction = "EW"
        self.video_thread.send_paired_command("S1", "S4", "GREEN")
        self.video_thread.send_paired_command("S2", "S3", "RED")
        self.update_log("[MANUAL] >>> AUTO MODE ACTIVATED")
    
    def closeEvent(self, event):
        self.video_thread.stop()
        self.video_thread.wait()
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    gui = TrafficLightGUI()
    gui.show()
    sys.exit(app.exec_())
