import os
from PIL import Image
from PIL.ExifTags import TAGS

def resize_image(input_image_path, output_image_path, target_width):
    try:
        with Image.open(input_image_path) as img:
            # Determine whether the image is portrait or landscape
            width, height = img.size
            if width > height:
                # Landscape image
                new_width = target_width
                new_height = int(height * (target_width / width))
            else:
                # Portrait image or square image
                new_height = target_width
                new_width = int(width * (target_width / height))

            # Resize the image while maintaining aspect ratio
            img.thumbnail((new_width, new_height))

            exif = img.info['exif']
            # Save the resized image
            img.save(output_image_path, 'JPEG', exif=exif)
            print(f"Image resized and saved as {output_image_path}")
    except FileNotFoundError:
        print(f"File {input_image_path} not found.")
    except Exception as e:
        print(f"An error occurred: {str(e)}")


# resize_image("/Users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos/2023/2023-01-01 (01-31) Varios Enero/2023-01-06 19.17.37.jpg", "/Users/angel/Downloads/2023-01-06 19.17.37.jpg", 1200)

# image = Image.open("/Users/angel/Downloads/2023-01-06 19.17.37.jpg")
# exif_data = image._getexif()
# for tag, value in exif_data.items():
#     tag_name = TAGS.get(tag, tag)
#     print(f"tag_name {tag_name} value {value}")

image = Image.open("/Users/angel/Insync/ladirecciondeangel@gmail.com/Google Drive/Fotitos/2023/2023-01-01 (01-31) Varios Enero/2023-01-08 16.02.21.jpg")
exif_data = image._getexif()
for tag, value in exif_data.items():
    tag_name = TAGS.get(tag, tag)
    print(f"tag_name {tag_name} value {value}")
