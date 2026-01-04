from ultralytics import YOLO
import cv2
import serial
import time

# Load the trained model
model = YOLO('model/weights/best.pt')  # Path to the best trained model

# ESP32 Serial Configuration
SERIAL_PORT = "COM3"  # Change this to your ESP32's COM port (COM3, COM4, etc.)
BAUD_RATE = 115200  # Standard ESP32 baud rate

# Initialize serial connection
ser = None
try:
    ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
    print(f"✓ Connected to ESP32 on {SERIAL_PORT} at {BAUD_RATE} baud")
    time.sleep(2)  # Wait for ESP32 to initialize

except serial.SerialException as e:
    print(f"✗ Failed to connect to ESP32 on {SERIAL_PORT}")
    print(f"  Error: {e}")
    print(f"  Available COM ports: Check Device Manager or use: python -m serial.tools.list_ports")
    print("  Make sure ESP32 is connected and COM port is correct!")
    exit(1)  # Exit if we can't connect to ESP32

# Traffic light timing configuration (in seconds)
BASE_GREEN_TIME = 5  # Base green light duration
BASE_RED_TIME = 5    # Base red light duration
MAX_INCREMENT = 15   # Maximum additional seconds per car

def calculate_green_time(north_count, south_count, east_count, west_count, direction):
    """
    Calculate dynamic green time based on individual car counts per direction.
    Scaling: 10 seconds per car, max 20 seconds for first 2 cars, then 10 seconds per additional car.
    - 0 cars: 5 seconds (base)
    - 1 car: 10 seconds
    - 2+ cars: 20 + (cars - 2) * 10 seconds (no cap)
    
    Gives priority to direction with highest car count.
    direction: "NS" for North-South (S1/S4) or "EW" for East-West (S2/S3)
    """
    if direction == "NS":
        # North-South: check which has more cars (North or South)
        ns_max = max(north_count, south_count)
        ew_max = max(east_count, west_count)
        
        if ns_max > ew_max:
            # N-S direction has more cars - calculate duration
            if ns_max == 0:
                return 5
            elif ns_max == 1:
                return 10
            else:
                return 20 + (ns_max - 2) * 10
        elif ns_max > 0:
            # N-S has some cars but E-W has more
            return 5
        else:
            # No cars in N-S
            return 5
    else:  # direction == "EW"
        # East-West: check which has more cars (East or West)
        ew_max = max(east_count, west_count)
        ns_max = max(north_count, south_count)
        
        if ew_max > ns_max:
            # E-W direction has more cars - calculate duration
            if ew_max == 0:
                return 5
            elif ew_max == 1:
                return 10
            else:
                return 20 + (ew_max - 2) * 10
        elif ew_max > 0:
            # E-W has some cars but N-S has more
            return 5
        else:
            # No cars in E-W
            return 5

def send_command_to_esp32(lane, color, duration=None):
    """
    Send command to ESP32 via serial communication.
    lane: S1, S2, S3, or S4
    color: GREEN or RED
    """
    if ser is None or not ser.is_open:
        print(f"✗ Serial connection not available")
        return False
    
    try:
        # Format: "S1:GREEN\n" or "S2:RED\n"
        command = f"{lane}:{color}\n"
        ser.write(command.encode())
        print(f"✓ Sent: {lane} {color}")
        return True
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        return False

def send_paired_command_to_esp32(lane1, lane2, color):
    """
    Send paired command to ESP32 via serial (e.g., S1 & S4 together or S2 & S3 together).
    Uses a special command format to ensure both lights are controlled together.
    """
    global ser
    if ser is None or not ser.is_open:
        print(f"✗ Serial connection not available - attempting to reconnect...")
        try:
            ser = serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1)
            time.sleep(1)
            print(f"✓ Reconnected to ESP32 on {SERIAL_PORT}")
        except serial.SerialException as e:
            print(f"✗ Reconnection failed: {e}")
            return False
    
    try:
        # Format: "S1:S4:GREEN\n" for paired commands
        command = f"{lane1}:{lane2}:{color}\n"
        ser.write(command.encode())
        print(f"✓ Sent: {lane1} & {lane2} {color}")
        return True
    except serial.SerialException as e:
        print(f"✗ Serial error: {e}")
        return False

def control_traffic_lights(north_count, south_count, west_count, east_count):
    """
    Control traffic lights based on car counts.
    - S1 and S4 (North-South): Get green if more cars detected
    - S2 and S3 (West-East): Get green if more cars detected
    """
    # Calculate green times based on car counts
    ns_count = north_count + south_count  # North-South total
    we_count = west_count + east_count      # West-East total
    
    # Use new timing logic that compares lanes
    green_time = calculate_green_time(ns_count, we_count)
    
    print(f"\n--- Traffic Control ---")
    print(f"N-S Cars: {ns_count} | W-E Cars: {we_count}")
    print(f"Green Time: {green_time}s")
    
    # Decide which direction gets priority based on car count
    if ns_count >= we_count:
        # North-South has priority or equal cars
        print("► S1 & S4 (N-S) GREEN | S2 & S3 (W-E) RED")
        send_command_to_esp32("S1", "GREEN")
        send_command_to_esp32("S4", "GREEN")
        send_command_to_esp32("S2", "RED")
        send_command_to_esp32("S3", "RED")
        # Sleep for dynamic duration
        time.sleep(green_time)
    else:
        # West-East has priority
        print("► S2 & S3 (W-E) GREEN | S1 & S4 (N-S) RED")
        send_command_to_esp32("S2", "GREEN")
        send_command_to_esp32("S3", "GREEN")
        send_command_to_esp32("S1", "RED")
        send_command_to_esp32("S4", "RED")
        # Sleep for dynamic duration
        time.sleep(green_time)

# Initialize webcam
cap = cv2.VideoCapture(0)  # Use 0 for default webcam

if not cap.isOpened():
    print("Cannot open webcam")
    exit()

print("✓ Webcam opened successfully")
print("Press 'q' to quit")
print(f"Connecting to ESP32 on {SERIAL_PORT} at {BAUD_RATE} baud")

frame_count = 0

# Traffic light state tracking
current_time_init = time.time()
tl1_state = "GREEN"  # S1 (Traffic Light 1 - E-W)
tl4_state = "GREEN"  # S4 (Traffic Light 4 - E-W)
tl2_state = "RED"  # S2 (Traffic Light 2 - N-S) - Start with N-S red
tl3_state = "RED"  # S3 (Traffic Light 3 - N-S) - Start with N-S red
tl1_green_start = current_time_init
tl4_green_start = current_time_init
tl2_green_start = 0
tl3_green_start = 0
current_tl1_duration = BASE_GREEN_TIME  # Initial green duration for E-W
current_tl4_duration = BASE_GREEN_TIME  # Initial green duration for E-W
current_tl2_duration = BASE_GREEN_TIME
current_tl3_duration = BASE_GREEN_TIME
current_cycle_direction = "EW"  # Start with E-W (S1/S4) green
last_ns_count = 0
last_we_count = 0
first_cycle_complete = False  # Track if initial cycle has completed

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Get frame dimensions
    height, width = frame.shape[:2]
    vertical_line_x = width // 2
    horizontal_line_y = height // 2
    
    # Define thresholds for all directions
    north_threshold_y = height // 2 - 100
    south_threshold_y = height // 2 + 100
    west_threshold_x = width // 2 - 120
    east_threshold_x = width // 2 + 120

    # Perform detection with adjusted parameters (lower resolution for speed)
    results = model(frame, conf=0.55, iou=0.3, imgsz=416)  # Consistent size for speed

    # Reset counters for real-time counts per frame
    from_west = 0
    from_north = 0
    from_east = 0
    from_south = 0

    # Process detections for directions
    for i in range(len(results[0].boxes)):
        bbox = results[0].boxes.xyxy[i]
        center_x = (bbox[0] + bbox[2]) / 2
        center_y = (bbox[1] + bbox[3]) / 2
        
        # Determine direction based on position with all four thresholds
        if center_x < vertical_line_x and center_y < horizontal_line_y:
            # Top-left quadrant: West or North
            if center_y < north_threshold_y:
                direction = "North"
                from_north += 1
            elif center_x < west_threshold_x:
                direction = "West"
                from_west += 1
            else:
                direction = "North"
                from_north += 1
        elif center_x > vertical_line_x and center_y < horizontal_line_y:
            # Top-right quadrant: East or North
            if center_y < north_threshold_y:
                direction = "North"
                from_north += 1
            elif center_x > east_threshold_x:
                direction = "East"
                from_east += 1
            else:
                direction = "North"
                from_north += 1
        elif center_x < vertical_line_x and center_y > horizontal_line_y:
            # Bottom-left quadrant: West or South
            if center_y > south_threshold_y:
                direction = "South"
                from_south += 1
            elif center_x < west_threshold_x:
                direction = "West"
                from_west += 1
            else:
                direction = "South"
                from_south += 1
        else:
            # Bottom-right quadrant: East or South
            if center_y > south_threshold_y:
                direction = "South"
                from_south += 1
            elif center_x > east_threshold_x:
                direction = "East"
                from_east += 1
            else:
                direction = "South"
                from_south += 1
        
        # Annotate direction on the frame
        cv2.putText(frame, direction, (int(bbox[0]), int(bbox[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

    # Plot YOLO results on frame
    annotated_frame = results[0].plot()
    
    # Threshold lines are defined but not drawn (invisible)
    # They are only used for detection logic, not for visualization

    # Overlay direction counts on the frame (real-time per frame)
    cv2.putText(annotated_frame, f"West: {from_west}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(annotated_frame, f"North: {from_north}", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(annotated_frame, f"East: {from_east}", (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    cv2.putText(annotated_frame, f"South: {from_south}", (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    # Calculate remaining time for each traffic light
    current_time = time.time()
    
    # Update car counts for this frame
    ns_count = from_north + from_south
    we_count = from_west + from_east
    
    # AUTO-CYCLE: Check if current green light has expired and switch if needed
    if current_cycle_direction == "EW":
        elapsed = current_time - tl1_green_start
        # Only allow duration increases during a green cycle (never shorten remaining time)
        new_duration = calculate_green_time(from_north, from_south, from_east, from_west, "EW")
        if new_duration > current_tl1_duration:
            current_tl1_duration = new_duration
            current_tl4_duration = new_duration
            print(f"Duration extended to {new_duration}s")
        
        # Only switch if elapsed time has TRULY exceeded the duration
        if elapsed >= current_tl1_duration and tl1_state == "GREEN":
            # E-W green has expired, switch to N-S green
            green_duration = calculate_green_time(from_north, from_south, from_east, from_west, "NS")
            
            print(f"✓ SWITCHING: E-W was green for {elapsed:.1f}s (required: {current_tl1_duration}s)")
            
            tl2_state = "GREEN"
            tl3_state = "GREEN"
            tl2_green_start = current_time
            tl3_green_start = current_time
            current_tl2_duration = green_duration
            current_tl3_duration = green_duration
            current_cycle_direction = "NS"
            first_cycle_complete = True
            
            send_paired_command_to_esp32("S2", "S3", "GREEN")
            tl1_state = "RED"
            tl4_state = "RED"
            send_paired_command_to_esp32("S1", "S4", "RED")
            print(f"✓ AUTO-CYCLE: E-W → N-S GREEN (Duration: {green_duration}s)")
    else:
        elapsed = current_time - tl2_green_start
        # Only allow duration increases during a green cycle (never shorten remaining time)
        new_duration = calculate_green_time(from_north, from_south, from_east, from_west, "NS")
        if new_duration > current_tl2_duration:
            current_tl2_duration = new_duration
            current_tl3_duration = new_duration
            print(f"Duration extended to {new_duration}s")
        
        # Only switch if elapsed time has TRULY exceeded the duration
        if elapsed >= current_tl2_duration and tl2_state == "GREEN":
            # N-S green has expired, switch to E-W green
            green_duration = calculate_green_time(from_north, from_south, from_east, from_west, "EW")
            
            print(f"✓ SWITCHING: N-S was green for {elapsed:.1f}s (required: {current_tl2_duration}s)")
            
            tl1_state = "GREEN"
            tl4_state = "GREEN"
            tl1_green_start = current_time
            tl4_green_start = current_time
            current_tl1_duration = green_duration
            current_tl4_duration = green_duration
            current_cycle_direction = "EW"
            first_cycle_complete = True
            
            send_paired_command_to_esp32("S1", "S4", "GREEN")
            tl2_state = "RED"
            tl3_state = "RED"
            send_paired_command_to_esp32("S2", "S3", "RED")
            print(f"✓ AUTO-CYCLE: N-S → E-W GREEN (Duration: {green_duration}s)")
    
    # SAFETY CHECK: Ensure at least one direction is always green (only check once per second to avoid interference)
    if frame_count % 30 == 0 and tl1_state == "RED" and tl2_state == "RED":
        print("⚠ SAFETY: All lights were red, forcing E-W green")
        tl1_state = "GREEN"
        tl4_state = "GREEN"
        tl2_state = "RED"
        tl3_state = "RED"
        tl1_green_start = current_time
        tl4_green_start = current_time
        current_tl1_duration = calculate_green_time(from_north, from_south, from_east, from_west, "EW")
        current_tl4_duration = current_tl1_duration
        current_cycle_direction = "EW"
        send_paired_command_to_esp32("S1", "S4", "GREEN")
        send_paired_command_to_esp32("S2", "S3", "RED")
    
    # Traffic Light 1 (S1) - N-S
    if tl1_state == "GREEN":
        elapsed = current_time - tl1_green_start
        remaining = max(0, current_tl1_duration - elapsed)
    else:
        remaining = 0
    tl1_color = (0, 255, 0) if tl1_state == "GREEN" else (0, 0, 255)  # Green or Red
    cv2.putText(annotated_frame, f"TL1: {tl1_state}", (width - 220, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl1_color, 2)
    cv2.putText(annotated_frame, f"{remaining:.1f}s", (width - 220, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl1_color, 2)
    
    # Traffic Light 4 (S4) - N-S
    if tl4_state == "GREEN":
        elapsed = current_time - tl4_green_start
        remaining = max(0, current_tl4_duration - elapsed)
    else:
        remaining = 0
    tl4_color = (0, 255, 0) if tl4_state == "GREEN" else (0, 0, 255)  # Green or Red
    cv2.putText(annotated_frame, f"TL4: {tl4_state}", (width - 220, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl4_color, 2)
    cv2.putText(annotated_frame, f"{remaining:.1f}s", (width - 220, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl4_color, 2)
    
    # Traffic Light 2 (S2) - W-E
    if tl2_state == "GREEN":
        elapsed = current_time - tl2_green_start
        remaining = max(0, current_tl2_duration - elapsed)
    else:
        remaining = 0
    tl2_color = (0, 255, 0) if tl2_state == "GREEN" else (0, 0, 255)  # Green or Red
    cv2.putText(annotated_frame, f"TL2: {tl2_state}", (width - 220, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl2_color, 2)
    cv2.putText(annotated_frame, f"{remaining:.1f}s", (width - 220, 180), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl2_color, 2)
    
    # Traffic Light 3 (S3) - W-E
    if tl3_state == "GREEN":
        elapsed = current_time - tl3_green_start
        remaining = max(0, current_tl3_duration - elapsed)
    else:
        remaining = 0
    tl3_color = (0, 255, 0) if tl3_state == "GREEN" else (0, 0, 255)  # Green or Red
    cv2.putText(annotated_frame, f"TL3: {tl3_state}", (width - 220, 210), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl3_color, 2)
    cv2.putText(annotated_frame, f"{remaining:.1f}s", (width - 220, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.7, tl3_color, 2)

    # Display the frame
    cv2.imshow('Traffic Light System', annotated_frame)

    # Update frame counter
    frame_count += 1

    # Exit on 'q' key
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
cap.release()
cv2.destroyAllWindows()
