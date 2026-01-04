from ultralytics import YOLO
import cv2
import os

# Load the trained model
model = YOLO('model/weights/best.pt')

# Path to the test image
image_path = 'Dataset/test/IMG_5083.jpg'  # Change this to any image in test folder

# Load the image
image = cv2.imread(image_path)
if image is None:
    print(f"Could not load image: {image_path}")
    exit()

# Get image dimensions
height, width = image.shape[:2]

# Define center lines
vertical_line_x = width // 2
horizontal_line_y = height // 2

# Define additional south threshold line (below center)
south_threshold_y = height // 2 + 380  # Adjust this value if needed

# Define additional north threshold line (above center)
north_threshold_y = height // 2 - 600  # Adjust this value if needed

# Define additional east threshold line (right of center)
east_threshold_x = width // 2 + 420  # Adjust this value if needed

# Define additional west threshold line (left of center)
west_threshold_x = width // 2 - 420  # Adjust this value if needed

# Draw center lines first
cv2.line(image, (vertical_line_x, 0), (vertical_line_x, height), (255, 255, 255), 2)  # White vertical
cv2.line(image, (0, horizontal_line_y), (width, horizontal_line_y), (255, 255, 255), 2)  # White horizontal

# Draw north threshold line
cv2.line(image, (0, north_threshold_y), (width, north_threshold_y), (100, 100, 255), 2)  # Light red threshold line

# Draw south threshold line
cv2.line(image, (0, south_threshold_y), (width, south_threshold_y), (0, 200, 200), 2)  # Cyan threshold line

# Draw west threshold line
cv2.line(image, (west_threshold_x, 0), (west_threshold_x, height), (200, 100, 100), 2)  # Light blue threshold line

# Draw east threshold line
cv2.line(image, (east_threshold_x, 0), (east_threshold_x, height), (100, 200, 200), 2)  # Light green threshold line

# Draw directional areas with different colors
# North area (top) - above the horizontal line
cv2.rectangle(image, (0, 0), (width, horizontal_line_y), (255, 0, 0), 2)  # Blue
cv2.putText(image, "NORTH", (width // 2 - 50, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

# South area (bottom) - below the horizontal line
cv2.rectangle(image, (0, horizontal_line_y), (width, height), (0, 0, 255), 2)  # Red
cv2.putText(image, "SOUTH", (width // 2 - 50, height - 20), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

# West area (left) - left of the vertical line
cv2.rectangle(image, (0, 0), (vertical_line_x, height), (0, 255, 0), 2)  # Green
cv2.putText(image, "WEST", (20, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

# East area (right) - right of the vertical line
cv2.rectangle(image, (vertical_line_x, 0), (width, height), (0, 165, 255), 2)  # Orange
cv2.putText(image, "EAST", (width - 100, height // 2), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 165, 255), 2)

# Perform detection with adjusted parameters
results = model(image, conf=0.5, iou=0.5)  # Lower confidence for more detections

# Initialize counters
west_count = 0
north_count = 0
south_count = 0
east_count = 0

# Process each detection
for i in range(len(results[0].boxes)):
    bbox = results[0].boxes.xyxy[i]
    center_x = int((bbox[0] + bbox[2]) / 2)
    center_y = int((bbox[1] + bbox[3]) / 2)
    
    # Determine direction based on position with all four thresholds
    if center_x < vertical_line_x and center_y < horizontal_line_y:
        # Top-left quadrant: West or North (apply north and west thresholds)
        if center_y < north_threshold_y:
            direction = "North"
            north_count += 1
        elif center_x < west_threshold_x:
            direction = "West"
            west_count += 1
        else:
            direction = "North"
            north_count += 1
    elif center_x > vertical_line_x and center_y < horizontal_line_y:
        # Top-right quadrant: East or North (apply north and east thresholds)
        if center_y < north_threshold_y:
            direction = "North"
            north_count += 1
        elif center_x > east_threshold_x:
            direction = "East"
            east_count += 1
        else:
            direction = "North"
            north_count += 1
    elif center_x < vertical_line_x and center_y > horizontal_line_y:
        # Bottom-left quadrant: West or South (apply south and west thresholds)
        if center_y > south_threshold_y:
            direction = "South"
            south_count += 1
        elif center_x < west_threshold_x:
            direction = "West"
            west_count += 1
        else:
            direction = "South"
            south_count += 1
    else:
        # Bottom-right quadrant: East or South (apply south and east thresholds)
        if center_y > south_threshold_y:
            direction = "South"
            south_count += 1
        elif center_x > east_threshold_x:
            direction = "East"
            east_count += 1
        else:
            direction = "South"
            south_count += 1
    
    # Anotate thne direction on the image
    cv2.putText(image, direction, (int(bbox[0]), int(bbox[1]) - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)

# Plot results on image (this will add bounding boxes)
annotated_image = results[0].plot()

# Ensure the image is in BGR format for OpenCV
if annotated_image.dtype != 'uint8':
    annotated_image = annotated_image.astype('uint8')

# Add text with background rectangles for visibility
text_items = [
    (f"Total Cars: {len(results[0].boxes)}", 40),
    (f"West: {west_count}", 80),
    (f"North: {north_count}", 120),
    (f"East: {east_count}", 160),
    (f"South: {south_count}", 200)
]

for text, y_pos in text_items:
    # Draw black background rectangle
    cv2.rectangle(annotated_image, (5, y_pos - 30), (280, y_pos + 5), (0, 0, 0), -1)
    # Draw white text
    cv2.putText(annotated_image, text, (15, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)

# Create output folder if it doesn't exist
output_dir = 'output'
os.makedirs(output_dir, exist_ok=True)

# Save the annotated image
output_path = os.path.join(output_dir, 'inferenced_image.jpg')
cv2.imwrite(output_path, annotated_image)
print(f"Annotated image saved to: {output_path}")