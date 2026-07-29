/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export type PoseBucket = 'frontal_0' | 'frontal_yaw15' | 'frontal_yaw30' | 'profile_L' | 'profile_R';

export interface PhotoQuality {
  overallScore: number;
  blur: number;
  noise: number;
}

export type Hypothesis = 'H0' | 'H1' | 'H2';

export type FuzzyLabel =
  | 'STRONGLY_MATCHING'
  | 'CONSISTENT'
  | 'INSUFFICIENT_DATA'
  | 'WEAK_EVIDENCE'
  | 'SUSPICIOUS_TEXTURE'
  | 'GEOMETRIC_MISMATCH'
  | 'IDENTITY_ANOMALY'
  | 'TEMPORAL_IMPOSSIBILITY';

export interface PhotoGeometry {
  geometry_score: number; // Bone Score
  orbit_depth: number; // Orbits
  orbit_fossa: number; // Orbits helper
  chin_projection: number; // Chin
  gonial_angle: number; // Chin helper
  jaw_width: number; // Jaw
  bigonial: number; // Jaw helper
  mandibular_body: number; // Jaw helper
  ramus_height: number; // Cheekbones
  zygomatic_arch: number; // Cheekbones helper
  symmetry_score: number; //Symmetry
  pose_yaw_deg: number; // Pose Yaw
}

export interface PhotoTexture {
  texture_silicone_prob: number; // Silicone Prob
  texture_specular_gloss: number; // Specular Gloss
  texture_lbp_complexity: number; // LBP Entropy
  texture_frangi_vessel: number; // Frangi Vessel
  texture_wrinkle_forehead: number; // Wrinkles forehead
  texture_wrinkle_nasolabial: number; // Wrinkles nasolabial
  texture_subsurface_scatter_proxy: number; // Subsurface Scatter
}

export interface Photo {
  id: string; // photo_id e.g., "DSC_04932" or similar
  date: string; // YYYY-MM-DD
  year: number;
  month: number;
  day: number;
  poseBucket: PoseBucket;
  quality: PhotoQuality;
  exifYear: number;
  isHidden: boolean;
  dominantHypothesis: Hypothesis;
  posteriors: {
    H0: number; // same_person
    H1: number; // mask/surgery/alteration
    H2: number; // identity_swap
  };
  fuzzyLabel: FuzzyLabel;
  confidence: number;
  geometry: PhotoGeometry;
  texture: PhotoTexture;
  flags: string[]; // e.g. 'TEMPORAL_IMPOSSIBILITY', 'RETURN_TO_BASELINE', 'TRANSITION', 'TEXTURE_SPIKE', 'EXIF_DATE_ANOMALY', 'IMPOSSIBLE_SHORT'
  visualAge: number;
  calendarAge: number;
}

export interface EventPin {
  id: string;
  date: string; // YYYY-MM-DD
  label: string;
  icon: string;
  color: string;
  source: string;
  description: string;
  isCustom?: boolean;
}

export interface Era {
  id: string;
  name: string;
  start: string; // YYYY-MM-DD
  end: string;   // YYYY-MM-DD
  color: string;
  description: string;
  photosCount?: number;
}
