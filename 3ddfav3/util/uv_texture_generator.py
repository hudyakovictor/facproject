"""
Improved UV Texture Generator for 3DDFA-V3
Provides two types of UV texture generation:
1. Analytical: Enhanced quality with maximum detail preservation
2. Synthetic: Mirrors visible areas to hidden areas for morphing
"""

import cv2
import numpy as np
import torch
import torch.nn.functional as F
from scipy import ndimage


class UVTextureGenerator:
    """
    High-quality UV texture generation with enhanced detail preservation
    """
    
    def __init__(self, uv_coords, tri, device='cuda', texture_size=1024):
        """
        Args:
            uv_coords: UV coordinates for vertices (N, 2) in range [0, 1]
            tri: Triangle faces (M, 3)
            device: 'cuda' or 'cpu'
            texture_size: Output texture resolution (default 1024 for 1000x1000px requirement)
        """
        self.uv_coords = uv_coords
        self.tri = torch.tensor(tri, dtype=torch.int64, device=device) if isinstance(tri, np.ndarray) else tri
        self.device = device
        self.texture_size = texture_size
        
        # Process UV coordinates for rendering
        self._setup_uv_coords()
        
    def _setup_uv_coords(self):
        """Setup UV coordinates for rendering"""
        uv_coords_numpy = self.uv_coords.copy()
        uv_coords_numpy[:, 0] = uv_coords_numpy[:, 0] * (self.texture_size - 1)
        uv_coords_numpy[:, 1] = uv_coords_numpy[:, 1] * (self.texture_size - 1)
        uv_coords_numpy = np.hstack((uv_coords_numpy, np.zeros((uv_coords_numpy.shape[0], 1))))
        
        self.uv_coords_torch = (torch.tensor(uv_coords_numpy, requires_grad=False, 
                                             dtype=torch.float32, device=self.device) / 
                                (self.texture_size - 1) - 0.5) * 2
        self.uv_coords_numpy = uv_coords_numpy.copy()
        self.uv_coords_numpy[:, 1] = self.texture_size - self.uv_coords_numpy[:, 1] - 1
        
    def _get_uv_renderer(self):
        """Get appropriate UV renderer based on device"""
        if self.device == 'cpu':
            from util.cpu_renderer import MeshRenderer_UV_cpu
            renderer = MeshRenderer_UV_cpu(rasterize_size=int(self.texture_size))
            # Add small perturbation for CPU renderer to avoid artifacts
            uv_coords = self.uv_coords_torch + 1e-6
        else:
            from util.nv_diffrast import MeshRenderer_UV
            renderer = MeshRenderer_UV(rasterize_size=int(self.texture_size))
            uv_coords = self.uv_coords_torch
            
        return renderer, uv_coords
    
    def _enhance_texture_details(self, texture_img):
        """
        Enhance texture details while preserving skin characteristics
        Uses adaptive sharpening and detail enhancement
        """
        # Check if already in 0-1 range
        if texture_img.max() <= 1.0:
            texture_float = texture_img.astype(np.float32)
        else:
            texture_float = texture_img.astype(np.float32) / 255.0
        
        # Apply subtle sharpening using unsharp masking
        gaussian_blur = cv2.GaussianBlur(texture_float, (0, 0), 1.0)
        sharpened = cv2.addWeighted(texture_float, 1.5, gaussian_blur, -0.5, 0)
        
        # Enhance local contrast using CLAHE on each channel
        enhanced = np.zeros_like(sharpened)
        for c in range(3):
            lab = cv2.cvtColor((np.clip(sharpened, 0, 1) * 255).astype(np.uint8), cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge([l, a, b])
            enhanced_c = cv2.cvtColor(lab, cv2.COLOR_LAB2RGB).astype(np.float32) / 255.0
            enhanced[:, :, c] = enhanced_c[:, :, c]
        
        # Blend original with enhanced
        result = cv2.addWeighted(texture_float, 0.7, enhanced, 0.3, 0)
        
        return np.clip(result, 0, 1)
    
    def _poisson_blend(self, source, target, mask):
        """
        Poisson blending for seamless texture integration
        """
        try:
            # Convert to uint8 for OpenCV
            source_uint8 = (source * 255).astype(np.uint8)
            target_uint8 = (target * 255).astype(np.uint8)
            mask_uint8 = (mask * 255).astype(np.uint8)
            
            # Use seamless clone with normal clone for better integration
            center = (self.texture_size // 2, self.texture_size // 2)
            result = cv2.seamlessClone(source_uint8, target_uint8, 
                                      mask_uint8, center, cv2.NORMAL_CLONE)
            
            return result.astype(np.float32) / 255.0
        except Exception as e:
            print(f"Poisson blending failed, using simple blend: {e}")
            return (1 - mask) * source + mask * target
    
    def _mirror_texture(self, texture_img):
        """
        Mirror visible areas to hidden areas for synthetic texture
        """
        # Horizontal flip
        flipped = cv2.flip(texture_img, 1)
        
        # Create a soft blend mask for the center region
        mask = np.ones((self.texture_size, self.texture_size), dtype=np.float32)
        center_width = self.texture_size // 10
        center_start = self.texture_size // 2 - center_width // 2
        center_end = self.texture_size // 2 + center_width // 2
        
        # Create gradient in center region
        for i in range(center_start, center_end):
            alpha = (i - center_start) / center_width
            mask[:, i] = alpha
        
        # Blend original and flipped with soft transition
        mask = np.stack([mask] * 3, axis=-1)
        result = texture_img * (1 - mask) + flipped * mask
        
        return result
    
    def generate_analytical_texture(self, face_texture, input_img, v2d, visible_idx):
        """
        Generate analytical UV texture with enhanced quality
        Preserves maximum skin details from original photo
        
        Args:
            face_texture: Face texture from PCA model (B, N, 3)
            input_img: Input image tensor (B, 3, H, W)
            v2d: 2D vertex coordinates (B, N, 2)
            visible_idx: Visibility mask for vertices (N,)
            
        Returns:
            uv_texture: Generated UV texture (H, W, 3)
            vertex_colors: Colors per vertex (N, 3)
        """
        renderer, uv_coords = self._get_uv_renderer()
        
        # Render PCA texture to UV space
        _, _, uv_color_pca, _ = renderer(
            uv_coords.unsqueeze(0).clone(), 
            self.tri, 
            torch.clamp(face_texture, 0, 1).clone()
        )
        
        # Sample colors from input image using 2D projections
        img_colors = self._sample_image_colors(input_img, v2d)
        
        # Render image colors to UV space
        _, _, uv_color_img, _ = renderer(
            uv_coords.unsqueeze(0).clone(),
            self.tri,
            img_colors.unsqueeze(0).clone()
        )
        
        # Create visibility weight mask
        uv_weight = self._render_visibility_mask(visible_idx, renderer, uv_coords)
        
        # Convert to numpy for processing
        uv_color_pca = uv_color_pca.detach().cpu().permute(0, 2, 3, 1).numpy()[0]
        uv_color_img = uv_color_img.detach().cpu().permute(0, 2, 3, 1).numpy()[0]
        uv_weight = uv_weight.detach().cpu().permute(0, 2, 3, 1).numpy()[0]
        
        # Enhance image texture details
        uv_color_img_enhanced = self._enhance_texture_details(uv_color_img)
        
        # Create blended weight mask with edge smoothing
        weight_mask = self._smooth_visibility_mask(uv_weight)
        
        # Poisson blend enhanced image texture with PCA texture
        blended_texture = self._poisson_blend(
            uv_color_img_enhanced, 
            uv_color_pca, 
            weight_mask
        )
        
        # Apply final enhancement to blended result
        final_texture = self._enhance_texture_details(blended_texture)
        
        # Get vertex colors from final texture
        vertex_colors = self._get_vertex_colors_from_uv(final_texture)
        
        return final_texture, vertex_colors
    
    def generate_synthetic_texture(self, face_texture, input_img, v2d, visible_idx):
        """
        Generate synthetic UV texture for morphing
        Mirrors visible areas to hidden regions
        
        Args:
            face_texture: Face texture from PCA model (B, N, 3)
            input_img: Input image tensor (B, 3, H, W)
            v2d: 2D vertex coordinates (B, N, 2)
            visible_idx: Visibility mask for vertices (N,)
            
        Returns:
            uv_texture: Generated UV texture (H, W, 3)
            vertex_colors: Colors per vertex (N, 3)
        """
        renderer, uv_coords = self._get_uv_renderer()
        
        # Render PCA texture to UV space
        _, _, uv_color_pca, _ = renderer(
            uv_coords.unsqueeze(0).clone(),
            self.tri,
            torch.clamp(face_texture, 0, 1).clone()
        )
        
        # Sample colors from input image
        img_colors = self._sample_image_colors(input_img, v2d)
        
        # Render image colors to UV space
        _, _, uv_color_img, _ = renderer(
            uv_coords.unsqueeze(0).clone(),
            self.tri,
            img_colors.unsqueeze(0).clone()
        )
        
        # Create visibility weight mask
        uv_weight = self._render_visibility_mask(visible_idx, renderer, uv_coords)
        
        # Convert to numpy
        uv_color_img = uv_color_img.detach().cpu().permute(0, 2, 3, 1).numpy()[0]
        uv_weight = uv_weight.detach().cpu().permute(0, 2, 3, 1).numpy()[0]
        
        # Enhance image texture
        uv_color_img_enhanced = self._enhance_texture_details(uv_color_img)
        
        # Mirror texture to fill hidden areas
        mirrored_texture = self._mirror_texture(uv_color_img_enhanced)
        
        # Create blend mask based on visibility
        weight_mask = self._smooth_visibility_mask(uv_weight)
        
        # Blend mirrored texture with original based on visibility
        synthetic_texture = uv_color_img_enhanced * (1 - weight_mask) + mirrored_texture * weight_mask
        
        # Apply subtle enhancement
        final_texture = self._enhance_texture_details(synthetic_texture)
        
        # Get vertex colors
        vertex_colors = self._get_vertex_colors_from_uv(final_texture)
        
        return final_texture, vertex_colors
    
    def _sample_image_colors(self, input_img, v2d):
        """
        Sample colors from input image using 2D vertex projections
        Uses bilinear interpolation for smooth sampling
        """
        B, C, H, W = input_img.shape
        
        # Sample using bilinear interpolation
        img_colors = self._bilinear_interpolate_torch(
            input_img.permute(0, 2, 3, 1).detach()[0],
            v2d[0, :, 0].detach(),
            H - 1 - v2d[0, :, 1].detach()
        )
        
        return img_colors
    
    def _bilinear_interpolate_torch(self, img, x, y):
        """Bilinear interpolation using PyTorch"""
        x0 = torch.floor(x).long()
        x1 = x0 + 1
        y0 = torch.floor(y).long()
        y1 = y0 + 1
        
        x0 = torch.clamp(x0, 0, img.shape[1] - 1)
        x1 = torch.clamp(x1, 0, img.shape[1] - 1)
        y0 = torch.clamp(y0, 0, img.shape[0] - 1)
        y1 = torch.clamp(y1, 0, img.shape[0] - 1)
        
        i_a = img[y0, x0]
        i_b = img[y1, x0]
        i_c = img[y0, x1]
        i_d = img[y1, x1]
        
        wa = (x1 - x) * (y1 - y)
        wb = (x1 - x) * (y - y0)
        wc = (x - x0) * (y1 - y)
        wd = (x - x0) * (y - y0)
        
        return wa.unsqueeze(-1) * i_a + wb.unsqueeze(-1) * i_b + wc.unsqueeze(-1) * i_c + wd.unsqueeze(-1) * i_d
    
    def _render_visibility_mask(self, visible_idx, renderer, uv_coords):
        """Render visibility mask to UV space"""
        visible_mask = (1 - torch.stack((visible_idx,) * 3, axis=-1).unsqueeze(0)
                       .type(torch.float32).to(self.tri.device))
        _, _, uv_weight, _ = renderer(
            uv_coords.unsqueeze(0).clone(),
            self.tri,
            visible_mask.clone()
        )
        return uv_weight
    
    def _smooth_visibility_mask(self, mask):
        """Apply smoothing to visibility mask for better blending"""
        # Convert to single channel
        mask_single = mask[:, :, 0]
        
        # Apply Gaussian blur for smooth edges
        mask_smooth = cv2.GaussianBlur(mask_single, (31, 31), 10)
        
        # Stack back to 3 channels
        mask_smooth = np.stack([mask_smooth] * 3, axis=-1)
        
        return mask_smooth
    
    def _get_vertex_colors_from_uv(self, uv_texture):
        """
        Sample colors from UV texture for each vertex using UV coordinates
        """
        # Use bilinear interpolation to sample from UV texture
        uv_coords_normalized = self.uv_coords_numpy.copy()
        uv_coords_normalized[:, 0] = uv_coords_normalized[:, 0] / (self.texture_size - 1)
        uv_coords_normalized[:, 1] = uv_coords_normalized[:, 1] / (self.texture_size - 1)
        
        # Sample colors
        vertex_colors = self._bilinear_interpolate_numpy(
            uv_texture,
            uv_coords_normalized[:, 0] * (self.texture_size - 1),
            uv_coords_normalized[:, 1] * (self.texture_size - 1)
        )
        
        return vertex_colors
    
    def _bilinear_interpolate_numpy(self, img, x, y):
        """Bilinear interpolation using NumPy"""
        x0 = np.floor(x).astype(np.int32)
        x1 = x0 + 1
        y0 = np.floor(y).astype(np.int32)
        y1 = y0 + 1
        
        x0 = np.clip(x0, 0, img.shape[1] - 1)
        x1 = np.clip(x1, 0, img.shape[1] - 1)
        y0 = np.clip(y0, 0, img.shape[0] - 1)
        y1 = np.clip(y1, 0, img.shape[0] - 1)
        
        i_a = img[y0, x0]
        i_b = img[y1, x0]
        i_c = img[y0, x1]
        i_d = img[y1, x1]
        
        wa = (x1 - x) * (y1 - y)
        wb = (x1 - x) * (y - y0)
        wc = (x - x0) * (y1 - y)
        wd = (x - x0) * (y - y0)
        
        return wa[..., np.newaxis] * i_a + wb[..., np.newaxis] * i_b + \
               wc[..., np.newaxis] * i_c + wd[..., np.newaxis] * i_d


def get_colors_from_uv(colors, uv_coords):
    """Helper function for backward compatibility"""
    res = bilinear_interpolate_numpy(colors, uv_coords[:, 0], uv_coords[:, 1])
    return res


def bilinear_interpolate_numpy(img, x, y):
    """Helper function for backward compatibility"""
    x0 = np.floor(x).astype(np.int32)
    x1 = x0 + 1
    y0 = np.floor(y).astype(np.int32)
    y1 = y0 + 1
    
    x0 = np.clip(x0, 0, img.shape[1] - 1)
    x1 = np.clip(x1, 0, img.shape[1] - 1)
    y0 = np.clip(y0, 0, img.shape[0] - 1)
    y1 = np.clip(y1, 0, img.shape[0] - 1)
    
    i_a = img[y0, x0]
    i_b = img[y1, x0]
    i_c = img[y0, x1]
    i_d = img[y1, x1]
    
    wa = (x1 - x) * (y1 - y)
    wb = (x1 - x) * (y - y0)
    wc = (x - x0) * (y1 - y)
    wd = (x - x0) * (y - y0)
    
    return wa[..., np.newaxis] * i_a + wb[..., np.newaxis] * i_b + \
           wc[..., np.newaxis] * i_c + wd[..., np.newaxis] * i_d
