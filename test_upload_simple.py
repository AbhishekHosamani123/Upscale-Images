import requests
import os
from PIL import Image
import io

def test_image_upload():
    """Test the image upload functionality"""
    
    # Create a simple test image
    test_image = Image.new('RGB', (100, 100), color='red')
    img_buffer = io.BytesIO()
    test_image.save(img_buffer, format='PNG')
    img_buffer.seek(0)
    
    # Test upload
    files = {'file': ('test.png', img_buffer, 'image/png')}
    data = {
        'scale_factor': 2.0,
        'interpolation': 'ai_enhanced',
        'quality': 95
    }
    
    try:
        response = requests.post('http://localhost:5000/upload', files=files, data=data)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('success'):
                print("SUCCESS: Upload successful!")
                print(f"File ID: {result.get('file_id')}")
                print(f"Processing time: {result.get('processing_time')}s")
                print(f"File size: {result.get('file_size')} bytes")
            else:
                print("FAILED: Upload failed:")
                print(f"Error: {result.get('error')}")
        else:
            print(f"HTTP Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_image_upload()
