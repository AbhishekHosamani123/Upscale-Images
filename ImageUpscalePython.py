import cv2
import numpy as np
import os
import argparse
from pathlib import Path
import time
from typing import Tuple, Optional
import logging
from scipy import ndimage
from skimage import restoration, filters, exposure
from skimage.morphology import disk
from skimage.filters import unsharp_mask

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ImageUpscaler:
    """
    Advanced AI-Powered Image Upscaler with quality enhancement
    """
    
    def __init__(self):
        self.interpolation_methods = {
            'cubic': cv2.INTER_CUBIC,
            'lanczos': cv2.INTER_LANCZOS4,
            'linear': cv2.INTER_LINEAR,
            'area': cv2.INTER_AREA,
            'nearest': cv2.INTER_NEAREST,
            'ai_enhanced': 'ai_enhanced',
            'super_resolution': 'super_resolution'
        }
        
    def validate_input(self, input_path: str) -> bool:
        """Validate input file exists and is a valid image"""
        if not os.path.exists(input_path):
            logger.error(f"Input file does not exist: {input_path}")
            return False
            
        # Check if it's a valid image by trying to read it
        try:
            test_img = cv2.imread(input_path)
            if test_img is None:
                logger.error(f"Invalid image file: {input_path}")
                return False
            return True
        except Exception as e:
            logger.error(f"Error reading image: {e}")
            return False
    
    def apply_ai_enhancement(self, img: np.ndarray, scale_factor: float) -> np.ndarray:
        """
        Apply AI-powered enhancement techniques for better upscaling quality
        """
        logger.info("Applying AI-powered enhancement...")
        
        try:
            # Use faster OpenCV-based enhancement instead of scikit-image
            # Step 1: Noise reduction using bilateral filter
            img_denoised = cv2.bilateralFilter(img, 9, 75, 75)
            
            # Step 2: Edge enhancement using unsharp masking
            gaussian = cv2.GaussianBlur(img_denoised, (0, 0), 2.0)
            img_enhanced = cv2.addWeighted(img_denoised, 1.5, gaussian, -0.5, 0)
            
            # Step 3: Contrast enhancement using CLAHE
            lab = cv2.cvtColor(img_enhanced, cv2.COLOR_BGR2LAB)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            lab[:,:,0] = clahe.apply(lab[:,:,0])
            img_contrast = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
            
            # Step 4: Detail enhancement using morphological operations
            img_detail = self._enhance_details_fast(img_contrast)
            
            return img_detail
            
        except Exception as e:
            logger.warning(f"AI enhancement failed, using fallback: {e}")
            # Fallback to simple sharpening
            return self._apply_enhanced_sharpening(img)
    
    def _enhance_details_fast(self, img: np.ndarray) -> np.ndarray:
        """Fast detail enhancement using OpenCV"""
        try:
            # Convert to grayscale for processing
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Laplacian for edge detection
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            laplacian = np.uint8(np.absolute(laplacian))
            
            # Create enhancement mask
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            enhanced = cv2.filter2D(img, -1, kernel)
            
            # Blend original with enhanced version
            result = cv2.addWeighted(img, 0.7, enhanced, 0.3, 0)
            
            return np.clip(result, 0, 255).astype(np.uint8)
            
        except Exception as e:
            logger.warning(f"Detail enhancement failed: {e}")
            return img
    
    def _enhance_details(self, img: np.ndarray) -> np.ndarray:
        """Enhance fine details using morphological operations"""
        enhanced = img.copy()
        
        # Apply detail enhancement to each channel
        for i in range(img.shape[2]):
            channel = img[:, :, i]
            
            # Top-hat transform to enhance bright details
            kernel = disk(2)
            tophat = cv2.morphologyEx(channel, cv2.MORPH_TOPHAT, kernel)
            
            # Black-hat transform to enhance dark details
            blackhat = cv2.morphologyEx(channel, cv2.MORPH_BLACKHAT, kernel)
            
            # Combine original with enhanced details
            enhanced[:, :, i] = np.clip(channel + 0.5 * tophat - 0.3 * blackhat, 0, 1)
        
        return enhanced
    
    def apply_super_resolution(self, img: np.ndarray, scale_factor: float) -> np.ndarray:
        """
        Apply super-resolution techniques inspired by ESRGAN (optimized version)
        """
        logger.info("Applying super-resolution enhancement...")
        
        try:
            # Step 1: Initial upscaling with Lanczos
            height, width = img.shape[:2]
            new_height, new_width = int(height * scale_factor), int(width * scale_factor)
            
            # Use Lanczos for initial upscaling
            upscaled = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            
            # Step 2: Apply bilateral filter for edge-preserving smoothing
            upscaled = cv2.bilateralFilter(upscaled, 9, 75, 75)
            
            # Step 3: Edge enhancement (simplified)
            upscaled = self._enhance_edges_fast(upscaled)
            
            # Step 4: Texture synthesis (simplified)
            upscaled = self._synthesize_texture_fast(upscaled, img, scale_factor)
            
            return upscaled
            
        except Exception as e:
            logger.warning(f"Super resolution failed, using fallback: {e}")
            # Fallback to Lanczos with sharpening
            height, width = img.shape[:2]
            new_height, new_width = int(height * scale_factor), int(width * scale_factor)
            upscaled = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_LANCZOS4)
            return self._apply_enhanced_sharpening(upscaled)
    
    def _enhance_edges_fast(self, img: np.ndarray) -> np.ndarray:
        """Fast edge enhancement using OpenCV"""
        try:
            # Convert to grayscale for edge detection
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            
            # Apply Laplacian filter
            laplacian = cv2.Laplacian(gray, cv2.CV_64F)
            
            # Create edge mask
            edge_mask = np.abs(laplacian)
            edge_mask = np.clip(edge_mask / edge_mask.max(), 0, 1)
            
            # Apply edge enhancement to each channel
            enhanced = img.copy().astype(np.float32)
            for i in range(3):
                enhanced[:, :, i] = img[:, :, i].astype(np.float32) + 0.2 * edge_mask * 255
            
            return np.clip(enhanced, 0, 255).astype(np.uint8)
            
        except Exception as e:
            logger.warning(f"Edge enhancement failed: {e}")
            return img
    
    def _synthesize_texture_fast(self, upscaled: np.ndarray, original: np.ndarray, scale_factor: float) -> np.ndarray:
        """Fast texture synthesis using OpenCV"""
        try:
            # Extract high-frequency components from original
            original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
            
            # Apply high-pass filter
            kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])
            high_freq = cv2.filter2D(original_gray, -1, kernel)
            
            # Upscale high-frequency components
            high_freq_upscaled = cv2.resize(high_freq, 
                                          (upscaled.shape[1], upscaled.shape[0]), 
                                          interpolation=cv2.INTER_CUBIC)
            
            # Add high-frequency details to upscaled image
            result = upscaled.copy().astype(np.float32)
            for i in range(3):
                result[:, :, i] += 0.05 * high_freq_upscaled
            
            return np.clip(result, 0, 255).astype(np.uint8)
            
        except Exception as e:
            logger.warning(f"Texture synthesis failed: {e}")
            return upscaled
    
    def _enhance_edges(self, img: np.ndarray) -> np.ndarray:
        """Enhance edges using Laplacian sharpening"""
        # Convert to grayscale for edge detection
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Apply Laplacian filter
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        
        # Create edge mask
        edge_mask = np.abs(laplacian)
        edge_mask = np.clip(edge_mask / edge_mask.max(), 0, 1)
        
        # Apply edge enhancement to each channel
        enhanced = img.copy().astype(np.float32)
        for i in range(3):
            enhanced[:, :, i] = img[:, :, i].astype(np.float32) + 0.3 * edge_mask * 255
        
        return np.clip(enhanced, 0, 255).astype(np.uint8)
    
    def _synthesize_texture(self, upscaled: np.ndarray, original: np.ndarray, scale_factor: float) -> np.ndarray:
        """Synthesize high-frequency details"""
        # Extract high-frequency components from original
        original_gray = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)
        
        # Apply high-pass filter
        kernel = np.array([[-1, -1, -1], [-1, 8, -1], [-1, -1, -1]])
        high_freq = cv2.filter2D(original_gray, -1, kernel)
        
        # Upscale high-frequency components
        high_freq_upscaled = cv2.resize(high_freq, 
                                      (upscaled.shape[1], upscaled.shape[0]), 
                                      interpolation=cv2.INTER_CUBIC)
        
        # Add high-frequency details to upscaled image
        result = upscaled.copy().astype(np.float32)
        for i in range(3):
            result[:, :, i] += 0.1 * high_freq_upscaled
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def _apply_enhanced_sharpening(self, img: np.ndarray) -> np.ndarray:
        """Apply enhanced sharpening with multiple techniques"""
        # Method 1: Unsharp masking
        gaussian = cv2.GaussianBlur(img, (0, 0), 2.0)
        unsharp_mask = cv2.addWeighted(img, 1.5, gaussian, -0.5, 0)
        
        # Method 2: Laplacian sharpening
        laplacian = cv2.Laplacian(img, cv2.CV_64F)
        laplacian_sharpened = img.astype(np.float64) + 0.3 * laplacian
        
        # Method 3: Edge-preserving filter
        edge_preserved = cv2.edgePreservingFilter(img, flags=1, sigma_s=50, sigma_r=0.4)
        
        # Combine all methods
        result = cv2.addWeighted(unsharp_mask, 0.4, laplacian_sharpened.astype(np.uint8), 0.3, 0)
        result = cv2.addWeighted(result, 0.7, edge_preserved, 0.3, 0)
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def calculate_target_size(self, original_size: Tuple[int, int], 
                            scale_factor: Optional[float] = None,
                            target_width: Optional[int] = None,
                            target_height: Optional[int] = None) -> Tuple[int, int]:
        """Calculate target dimensions based on various input methods"""
        orig_width, orig_height = original_size
        
        if scale_factor:
            return int(orig_width * scale_factor), int(orig_height * scale_factor)
        elif target_width and target_height:
            return target_width, target_height
        elif target_width:
            aspect_ratio = orig_height / orig_width
            return target_width, int(target_width * aspect_ratio)
        elif target_height:
            aspect_ratio = orig_width / orig_height
            return int(target_height * aspect_ratio), target_height
        else:
            # Default to 2x scale
            return orig_width * 2, orig_height * 2
    
    def upscale_image(self, input_path: str, output_path: str,
                     scale_factor: Optional[float] = None,
                     target_width: Optional[int] = None,
                     target_height: Optional[int] = None,
                     interpolation: str = 'ai_enhanced',
                     quality: int = 95) -> bool:
        """
        Upscale image with various options
        
        Args:
            input_path: Path to input image
            output_path: Path for output image
            scale_factor: Scale factor (e.g., 2.0 for 2x upscale)
            target_width: Target width in pixels
            target_height: Target height in pixels
            interpolation: Interpolation method ('cubic', 'lanczos', 'linear', 'area', 'nearest', 'ai_enhanced', 'super_resolution')
            quality: Output quality (1-100)
        """
        
        # Validate inputs
        if not self.validate_input(input_path):
            return False
            
        if interpolation not in self.interpolation_methods:
            logger.error(f"Invalid interpolation method: {interpolation}")
            return False
        
        try:
            start_time = time.time()
            
            # Load image
            logger.info(f"Loading image: {input_path}")
            img = cv2.imread(input_path)
            
            if img is None:
                logger.error("Failed to load image")
                return False
            
            original_size = img.shape[1], img.shape[0]  # width, height
            logger.info(f"Original size: {original_size[0]}x{original_size[1]}")
            
            # Calculate target size
            target_size = self.calculate_target_size(
                original_size, scale_factor, target_width, target_height
            )
            
            logger.info(f"Target size: {target_size[0]}x{target_size[1]}")
            
            # Calculate scale factor for AI methods
            actual_scale_factor = target_size[0] / original_size[0]
            
            # Choose interpolation method and apply AI enhancement
            if interpolation == 'ai_enhanced':
                logger.info("Using AI-enhanced upscaling...")
                # First upscale with Lanczos
                upscaled_img = cv2.resize(img, target_size, interpolation=cv2.INTER_LANCZOS4)
                # Then apply AI enhancement
                upscaled_img = self.apply_ai_enhancement(upscaled_img, actual_scale_factor)
                
            elif interpolation == 'super_resolution':
                logger.info("Using super-resolution upscaling...")
                upscaled_img = self.apply_super_resolution(img, actual_scale_factor)
                
            else:
                # Traditional interpolation methods
                interp_method = self.interpolation_methods[interpolation]
                logger.info(f"Upscaling using {interpolation} interpolation...")
                upscaled_img = cv2.resize(img, target_size, interpolation=interp_method)
                
                # Apply enhanced sharpening for better quality
                if interpolation in ['cubic', 'lanczos']:
                    upscaled_img = self._apply_enhanced_sharpening(upscaled_img)
            
            # Save output
            logger.info(f"Saving upscaled image: {output_path}")
            
            # Determine compression parameters based on file extension
            output_ext = Path(output_path).suffix.lower()
            if output_ext in ['.jpg', '.jpeg']:
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            elif output_ext == '.png':
                encode_params = [cv2.IMWRITE_PNG_COMPRESSION, 9 - (quality // 10)]
            else:
                encode_params = []
            
            success = cv2.imwrite(output_path, upscaled_img, encode_params)
            
            if success:
                elapsed_time = time.time() - start_time
                logger.info(f"Upscaling completed in {elapsed_time:.2f} seconds")
                logger.info(f"Output saved to: {output_path}")
                return True
            else:
                logger.error("Failed to save output image")
                return False
                
        except Exception as e:
            logger.error(f"Error during upscaling: {e}")
            return False
    
    def batch_upscale(self, input_dir: str, output_dir: str,
                    scale_factor: Optional[float] = None,
                    target_width: Optional[int] = None,
                    target_height: Optional[int] = None,
                    interpolation: str = 'lanczos',
                    quality: int = 95) -> int:
        """
        Batch upscale all images in a directory
        """
        input_path = Path(input_dir)
        output_path = Path(output_dir)
        
        if not input_path.exists():
            logger.error(f"Input directory does not exist: {input_dir}")
            return 0
        
        # Create output directory if it doesn't exist
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Supported image extensions
        image_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif', '.webp'}
        
        # Find all image files
        image_files = [f for f in input_path.iterdir() 
                      if f.suffix.lower() in image_extensions and f.is_file()]
        
        if not image_files:
            logger.warning(f"No image files found in {input_dir}")
            return 0
        
        logger.info(f"Found {len(image_files)} images to process")
        
        successful = 0
        for i, img_file in enumerate(image_files, 1):
            logger.info(f"Processing {i}/{len(image_files)}: {img_file.name}")
            
            output_file = output_path / f"upscaled_{img_file.name}"
            
            if self.upscale_image(str(img_file), str(output_file),
                                scale_factor, target_width, target_height,
                                interpolation, quality):
                successful += 1
        
        logger.info(f"Batch processing completed: {successful}/{len(image_files)} images processed successfully")
        return successful

def main():
    """Command line interface"""
    parser = argparse.ArgumentParser(description='Advanced Image Upscaler')
    parser.add_argument('input', help='Input image file or directory')
    parser.add_argument('-o', '--output', help='Output file or directory')
    parser.add_argument('-s', '--scale', type=float, help='Scale factor (e.g., 2.0 for 2x)')
    parser.add_argument('-w', '--width', type=int, help='Target width')
    parser.add_argument('-h', '--height', type=int, help='Target height')
    parser.add_argument('-i', '--interpolation', default='ai_enhanced',
                       choices=['cubic', 'lanczos', 'linear', 'area', 'nearest', 'ai_enhanced', 'super_resolution'],
                       help='Interpolation method')
    parser.add_argument('-q', '--quality', type=int, default=95,
                       help='Output quality (1-100)')
    parser.add_argument('--batch', action='store_true',
                       help='Process all images in input directory')
    
    args = parser.parse_args()
    
    upscaler = ImageUpscaler()
    
    if args.batch:
        # Batch processing
        if not args.output:
            args.output = 'upscaled_images'
        
        upscaler.batch_upscale(args.input, args.output, args.scale,
                             args.width, args.height, args.interpolation, args.quality)
    else:
        # Single image processing
        if not args.output:
            input_path = Path(args.input)
            args.output = f"upscaled_{input_path.name}"
        
        upscaler.upscale_image(args.input, args.output, args.scale,
                             args.width, args.height, args.interpolation, args.quality)

if __name__ == "__main__":
    # Example usage for direct script execution
    upscaler = ImageUpscaler()
    
    # Example: 2x upscale with AI-enhanced interpolation
    upscaler.upscale_image('image.png', 'output_upscaled.png', 
                          scale_factor=2.0, interpolation='ai_enhanced', quality=95)
