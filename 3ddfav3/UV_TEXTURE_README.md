# Improved UV Texture Generation for 3DDFA-V3

## Overview

This implementation provides significantly improved UV texture generation with two distinct modes for different use cases:

1. **Analytical Texture** - Enhanced quality with maximum skin detail preservation
2. **Synthetic Texture** - Mirrored visible areas for morphing applications

## Features

### Analytical Texture Mode
- **Purpose**: High-quality texture extraction for analysis and visualization
- **Key Improvements**:
  - Adaptive sharpening using unsharp masking
  - CLAHE-based local contrast enhancement
  - Poisson blending for seamless texture integration
  - Smooth visibility mask transitions
  - Maximum skin detail preservation from original photos

### Synthetic Texture Mode
- **Purpose**: Texture generation for 3D model morphing
- **Key Features**:
  - Mirrors visible facial areas to hidden regions
  - Soft gradient blending at symmetry boundaries
  - Preserves visible area details
  - Optimized for geometric comparison during morphing

## Usage

### Basic Usage (Analytical Mode - Default)
```bash
python demo.py --inputpath examples/ --savepath examples/results \
    --device cuda --iscrop 1 --detector retinaface \
    --extractTex 1 --backbone resnet50
```

### Synthetic Texture Mode (for Morphing)
```bash
python demo.py --inputpath examples/ --savepath examples/results \
    --device cuda --iscrop 1 --detector retinaface \
    --extractTex 1 --texture_mode synthetic --backbone resnet50
```

### Generate Both Texture Types
```bash
python demo.py --inputpath examples/ --savepath examples/results \
    --device cuda --iscrop 1 --detector retinaface \
    --extractTex 1 --texture_mode both --backbone resnet50
```

### Custom Texture Resolution
```bash
python demo.py --inputpath examples/ --savepath examples/results \
    --device cuda --iscrop 1 --detector retinaface \
    --extractTex 1 --texture_size 1024 --backbone resnet50
```

### Use Legacy Texture Generation
```bash
python demo.py --inputpath examples/ --savepath examples/results \
    --device cuda --iscrop 1 --detector retinaface \
    --extractTex 1 --use_legacy_texture 1 --backbone resnet50
```

## Command Line Arguments

### New Arguments

- `--texture_mode`: Texture generation mode
  - `analytical` (default): Enhanced quality with maximum detail preservation
  - `synthetic`: Mirrored texture for morphing applications
  - `both`: Generate both analytical and synthetic textures

- `--texture_size`: UV texture resolution (default: 1024)
  - Recommended: 1024 for 800x800px input images
  - Maximum: 1024 (to maintain quality without upscaling)

- `--use_legacy_texture`: Use legacy texture extraction (default: False)
  - Set to `1` or `true` to use the original implementation

## Output Files

When using the new texture generator, the following files are generated:

### Standard Output
- `{image_name}_extractTex.obj`: 3D mesh with extracted texture colors per vertex
- `{image_name}_extractTex_uv.png`: UV texture map (single mode)
- `{image_name}_extractTex_uv_analytical.png`: Analytical UV texture (both mode)
- `{image_name}_extractTex_uv_synthetic.png`: Synthetic UV texture (both mode)

### Comparison with Original

**Original Implementation:**
- Used `cv2.seamlessClone` with PCA texture for hidden areas
- Fixed 512x512 texture resolution
- Limited detail enhancement
- Basic visibility masking

**New Implementation:**
- Configurable texture resolution (up to 1024x1024)
- Advanced detail enhancement (sharpening + CLAHE)
- Improved Poisson blending
- Smooth visibility mask transitions
- Two distinct modes for different use cases

## Technical Details

### Texture Enhancement Pipeline

1. **Detail Enhancement**
   - Unsharp masking for subtle sharpening
   - CLAHE for local contrast improvement
   - Blended with original to preserve natural look

2. **Visibility Mask Processing**
   - Gaussian blur for smooth edges
   - Large kernel (31x31) for gradual transitions
   - Prevents visible seams in blended regions

3. **Texture Blending**
   - Poisson blending using `cv2.seamlessClone`
   - Normal clone mode for natural integration
   - Fallback to weighted blend if Poisson fails

### Synthetic Texture Generation

1. **Mirroring Process**
   - Horizontal flip of visible texture
   - Soft gradient mask at center boundary
   - Width: 10% of texture size

2. **Blending Strategy**
   - Original texture dominates visible areas
   - Mirrored texture fills hidden regions
   - Smooth transition at symmetry boundary

## Performance Considerations

- **Texture Size**: Larger textures (1024x1024) require more memory and processing time
- **Device**: CUDA rendering is significantly faster than CPU
- **Both Mode**: Generates two textures, approximately 2x processing time

## Recommendations

### For Analysis
- Use `analytical` mode for maximum detail preservation
- Texture size: 1024 for best quality
- Input images: 800x800px or smaller

### For Morphing
- Use `synthetic` mode for geometric comparison
- Texture size: 1024 for consistency
- Focus on geometry rather than texture accuracy

### For Testing
- Use `both` mode to compare results
- Start with smaller texture size (512) for faster iteration
- Compare with legacy mode using `--use_legacy_texture 1`

## Troubleshooting

### Memory Issues
- Reduce `--texture_size` to 512 or 768
- Use CPU mode if CUDA memory is insufficient
- Process images one at a time

### Quality Issues
- Ensure input images are well-lit and in focus
- Use `--detector retinaface` for better face detection
- Try different texture modes to find best fit

### Artifacts
- Increase texture size for better resolution
- Use analytical mode for fewer artifacts
- Check that face detection is accurate

## Implementation Details

The new texture generator is implemented in:
- `util/uv_texture_generator.py`: Main texture generation logic
- `model/recon.py`: Integration with reconstruction pipeline
- `demo.py`: Command line interface
- `util/io.py`: Output file handling

## Backward Compatibility

The original texture extraction is preserved and can be accessed using:
```bash
--use_legacy_texture 1
```

This ensures existing workflows continue to work without modification.
