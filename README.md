# Traffic Light System with AI Car Detection

## Overview

This project implements an intelligent traffic light control system for intersection A4, utilizing computer vision and AI to dynamically manage traffic flow. The system uses YOLO (You Only Look Once) object detection to count vehicles approaching from different directions and adjusts traffic light timings accordingly to optimize traffic efficiency.

The system features a real-time GUI built with PyQt5, displaying live video feed, car counts, traffic light statuses, and system logs. It communicates with an ESP32 microcontroller via serial connection to control physical traffic lights.

## Features

- **Real-time Car Detection**: Uses YOLOv8 model trained on toy car dataset for accurate vehicle detection
- **Dynamic Traffic Light Control**: Automatically adjusts green light duration based on vehicle counts in each direction
- **Live Video Feed**: Displays annotated video stream with detected vehicles
- **Traffic Statistics**: Shows real-time counts for North-South and West-East traffic
- **Traffic Light Status Monitoring**: Visual indicators for all four traffic lights with countdown timers
- **Manual Override**: Force all lights to red or reset to auto mode
- **System Logging**: Real-time log of system actions and serial communications
- **ESP32 Integration**: Serial communication to control physical traffic lights

## Project Team

**Main Developer:**
- Ralph Angelo Gonzaga

**Team Members:**
- Kier Suralta
- Jevan Monte Racaza
- Laurence Alvizo
- Kristel Jane Donan

**Course:** ECE 110 - Feedback and Control Systems Project

## Prerequisites

- Python 3.8 or higher
- Webcam or video capture device
- ESP32 microcontroller with traffic light hardware
- Windows/Linux/Mac OS

## Installation

### Step 1: Clone or Download the Project

Copy all project files to your local machine, including:
- `traffic_light_gui.py` (main application)
- `requirements.txt` (dependencies)
- `model/weights/best.pt` (trained YOLO model)
- Other supporting files (`data.yaml`, etc.)

### Step 2: Install Python Dependencies

1. Ensure Python 3.8+ is installed on your system
2. Open a terminal/command prompt in the project directory
3. Install required packages:

```bash
pip install -r requirements.txt
```

This will install:
- ultralytics (for YOLO)
- opencv-python (for computer vision)
- pillow & pillow-heif (for image processing)
- pyserial (for ESP32 communication)
- PyQt5 (for GUI)
- numpy (for array operations)

### Step 3: Hardware Setup

1. Connect your ESP32 to the computer (default COM3, adjustable in code)
2. Ensure traffic light hardware is properly connected to ESP32
3. Verify serial communication settings (115200 baud rate)

### Step 4: Model and Data Files

Ensure the following files are present:
- `model/weights/best.pt` - Trained YOLO model weights
- `data.yaml` - Dataset configuration (if needed for retraining)

## Usage

### Running the Application

1. Connect your webcam and ESP32
2. Open terminal in project directory
3. Run the main application:

```bash
python traffic_light_gui.py
```

### GUI Overview

The application window displays:

- **Left Panel**: Live video feed with detected cars (annotated with bounding boxes)
- **Right Panel**:
  - Car counts (N-S and W-E totals)
  - Traffic light statuses with countdown timers
  - System log
  - Manual override buttons

### Traffic Light Logic

- **Auto Mode**: System cycles between E-W and N-S directions
- **Dynamic Timing**: Green light duration extends based on vehicle count:
  - 0 cars: 5 seconds
  - 1 car: 10 seconds
  - 2+ cars: 20 + 10*(cars-2) seconds
- **Direction Priority**: Switches when current direction's time expires

### Manual Controls

- **FORCE RED ALL**: Sets all traffic lights to red
- **AUTO MODE**: Resets to automatic cycling mode

### Serial Commands

The system sends commands to ESP32 in format:
- Single light: `S1:GREEN` or `S1:RED`
- Paired lights: `S1:S4:GREEN` (for synchronized control)

## Troubleshooting

### Common Issues

1. **ESP32 Connection Failed**
   - Check COM port in code (line 32: `serial.Serial("COM3", 115200, timeout=1)`)
   - Verify ESP32 is powered and connected
   - Check serial permissions on Linux/Mac

2. **Model Loading Error**
   - Ensure `model/weights/best.pt` exists
   - Verify ultralytics installation

3. **Camera Not Working**
   - Check camera index (default 0)
   - Ensure camera permissions granted

4. **PyQt5 Display Issues**
   - On Linux, install system dependencies: `sudo apt-get install python3-pyqt5`
   - On Mac, ensure XQuartz is installed for GUI

### Performance Optimization

- Adjust detection confidence: `conf=0.55` (line 106)
- Modify image size: `imgsz=416` (line 106)
- Tune thresholds for direction detection (lines 109-112)

## Project Structure

```
├── traffic_light_gui.py      # Main GUI application
├── requirements.txt          # Python dependencies
├── model/
│   └── weights/
│       └── best.pt          # Trained YOLO model
├── data.yaml                 # Dataset configuration
├── train_yolo.py            # Model training script
├── detect_cars.py           # Detection testing script
├── infer_image.py           # Image inference script
├── convert_and_split.py     # Data preprocessing
├── toy_car_detection.ipynb  # Jupyter notebook for development
├── esp32.ino                # ESP32 firmware
└── runs/                    # Training results
```

## Future Enhancements

- Multi-camera support for larger intersections
- Integration with traffic sensors
- Machine learning for traffic pattern prediction
- Web-based monitoring interface
- Emergency vehicle detection and priority

## License

This project is developed for educational purposes as part of ECE 110 coursework.

## Acknowledgments

- YOLOv8 by Ultralytics for object detection
- PyQt5 for GUI framework
- OpenCV for computer vision
- ESP32 community for microcontroller support