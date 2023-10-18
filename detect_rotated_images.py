import cv2
import numpy as np
from skimage.feature import corner_harris, corner_peaks

def detect_rotation(image_path):
    # Load the image
    print("Load the image")
    img = cv2.imread(image_path, 0)

    # Perform corner detection
    print("Perform corner detection")
    coords = corner_peaks(corner_harris(img), min_distance=5)

    # Calculate the angle of the detected corners
    print("Calculate the angle of the detected corners")
    print("np.arctan2")
    angle = np.arctan2(coords[:, 0] - img.shape[0] / 2, coords[:, 1] - img.shape[1] / 2)
    print("np.degrees(angle)")
    angle = np.degrees(angle)

    # Determine the most common angle (rotation)
    print("Determine the most common angle (rotation)")
    rotation = np.median(angle)

    return rotation


def rotate_image(image_path, angle):
    # Load the image
    image = cv2.imread(image_path)

    # Get the image dimensions
    height, width = image.shape[:2]

    # Calculate the rotation matrix
    rotation_matrix = cv2.getRotationMatrix2D((width / 2, height / 2), angle, 1)

    # Apply the rotation to the image
    rotated_image = cv2.warpAffine(image, rotation_matrix, (width, height))

    return rotated_image


if __name__ == "__main__":
    # image_path = "/Users/angel/Downloads/2006-08-10 02.36.01.jpg"  # Replace with your image path
    image_path = "/Users/angel/Downloads/2008-02-02 23.32.31.jpg"  # Replace with your image path
    rotation_angle = detect_rotation(image_path)
    print(f"Image Rotation: {rotation_angle} degrees")

    rotated_image = rotate_image(image_path, rotation_angle)
    # Save the rotated image to a file
    cv2.imwrite("/Users/angel/Downloads/rotated_image.jpg", rotated_image)

