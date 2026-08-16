import type { TimelineResponse } from '../types/timeline';

/**
 * Mock timeline data for UI-v7 development.
 * Simulates 1700+ photos from 1999-2026 with realistic patterns.
 */

const POSE_BINS = [
  'left_profile', 'left_deep', 'left_mid', 'left_light',
  'frontal',
  'right_light', 'right_mid', 'right_deep', 'right_profile',
];

const ERAS: Record<string, { label: string; start: string; end: string }> = {
  era_early: { label: '1999-2004', start: '1999-01-01', end: '2004-12-31' },
  era_first: { label: '2005-2008', start: '2005-01-01', end: '2008-12-31' },
  era_second: { label: '2009-2012', start: '2009-01-01', end: '2012-12-31' },
  era_third: { label: '2013-2016', start: '2013-01-01', end: '2016-12-31' },
  era_fourth: { label: '2017-2020', start: '2017-01-01', end: '2020-12-31' },
  era_recent: { label: '2021-2026', start: '2021-01-01', end: '2026-12-31' },
};

function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

function generatePhoto(id: number, date: Date, random: () => number): TimelineResponse['photos'][number] {
  const poseBin = POSE_BINS[Math.floor(random() * POSE_BINS.length)]!;
  const year = date.getFullYear();
  
  // Simulate quality degradation in older photos
  const ageFactor = Math.max(0, 1 - (2026 - year) / 30);
  const baseQuality = 0.4 + random() * 0.4 + ageFactor * 0.2;
  
  // Simulate skin authenticity (some photos show silicone-like patterns)
  const isSuspiciousPeriod = year >= 2012 && year <= 2026;
  const siliconeBase = isSuspiciousPeriod ? 0.15 + random() * 0.25 : 0.05 + random() * 0.1;
  
  // Simulate shape difference (LDM-based)
  const shapeDiffBase = isSuspiciousPeriod ? 0.2 + random() * 0.3 : 0.05 + random() * 0.15;
  
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  const dateStr = `${year}-${month}-${day}`;
  
  return {
    id: `${dateStr}__${String(id).padStart(12, '0')}`,
    date: dateStr,
    t: date.getTime(),
    bucket: poseBin,
    era: year < 2005 ? 'era_early' : year < 2009 ? 'era_first' : year < 2013 ? 'era_second' : year < 2017 ? 'era_third' : year < 2021 ? 'era_fourth' : 'era_recent',
    quality: Math.min(1, Math.max(0, baseQuality + (random() - 0.5) * 0.1)),
    yaw: (random() - 0.5) * 60,
    pitch: (random() - 0.5) * 30,
    roll: (random() - 0.5) * 20,
    fuzzy: '',
    measurementStatus: random() > 0.1 ? 'measured' : 'limited',
    flags: random() > 0.95 ? ['coherent_jump_candidate'] : [],
    sourceMode: 'research',
    analysisStage: 'stage1_inventory',
    dateProvenanceStatus: random() > 0.9 ? 'conflict' : 'filename_only',
    
    alignmentQuality: Math.min(1, Math.max(0, baseQuality + (random() - 0.5) * 0.15)),
    poseConfidence: Math.min(1, Math.max(0, 0.7 + random() * 0.3)),
    detectionConfidence: Math.min(1, Math.max(0, 0.8 + random() * 0.2)),
    confidence: Math.min(1, Math.max(0, baseQuality + random() * 0.2)),
    
    skinQuality: Math.min(1, Math.max(0, 0.6 + random() * 0.3)),
    skinAuthenticity: Math.min(1, Math.max(0, 1 - siliconeBase)),
    siliconeProb: Math.min(1, Math.max(0, siliconeBase + (random() - 0.5) * 0.1)),
    fillerProb: Math.min(1, Math.max(0, random() * 0.1)),
    wrinkleDensity: Math.min(1, Math.max(0, 0.2 + (year - 1999) / 30 + (random() - 0.5) * 0.2)),
    subsurface: Math.min(1, Math.max(0, 0.5 + random() * 0.3)),
    uvCoverage: Math.min(1, Math.max(0, 0.6 + random() * 0.3)),
    
    boneScore: Math.min(1, Math.max(0, 0.5 + random() * 0.4)),
    orbit: (random() - 0.5) * 2,
    chin: (random() - 0.5) * 2,
    jaw: (random() - 0.5) * 2,
    cheek: (random() - 0.5) * 2,
    symmetry: Math.min(1, Math.max(0, 0.7 + random() * 0.3)),
    
    p0: (random() - 0.5) * 3,
    p1: (random() - 0.5) * 3,
    p2: (random() - 0.5) * 3,
    
    zOrbitDepth: (random() - 0.5) * 4,
    zChinProj: (random() - 0.5) * 4,
    zJawWidth: (random() - 0.5) * 4,
    zCheek: (random() - 0.5) * 4,
    
    expressionMagnitude: random() * 10,
    jawOpenDegree: random() * 20,
    jawOpenRatio: random() * 0.3,
    jawOpenDetected: random() > 0.8,
    smileDetected: random() > 0.7,
    visualAge: 30 + (year - 1999) + (random() - 0.5) * 5,
    calendarAge: 44 + (year - 1999),
    faceAreaRatio: Math.min(1, Math.max(0, 0.3 + random() * 0.4)),
    correctionMagnitude: random() * 20,
    residualYaw: (random() - 0.5) * 10,
    residualPitch: (random() - 0.5) * 5,
    residualRoll: (random() - 0.5) * 5,
    
    // LDM fields (NEW for v7)
    ldmShapeDifference: Math.min(1, Math.max(0, shapeDiffBase + (random() - 0.5) * 0.1)),
    ldm106Difference: Math.min(1, Math.max(0, shapeDiffBase + (random() - 0.5) * 0.15)),
    ldm134Difference: Math.min(1, Math.max(0, shapeDiffBase + (random() - 0.5) * 0.12)),
    visibleLdm106: Math.floor(60 + random() * 46),
    visibleLdm134: Math.floor(80 + random() * 54),
    
    canonicalYaw: (random() - 0.5) * 40,
    exifAnomaly: random() > 0.95,
    dateProvenanceLimited: random() > 0.9,
    bayesianProjectionAvailable: false,
    laplacianVariance: 50 + random() * 200,
    tenengradMean: 1000 + random() * 5000,
    noiseResidual: random() * 5,
    skinMaskCoverage: Math.min(1, Math.max(0, 0.1 + random() * 0.3)),
  };
}

export function generateMockTimeline(photoCount: number = 1709): TimelineResponse {
  const random = seededRandom(42);
  const photos: TimelineResponse['photos'] = [];
  
  const startDate = new Date('1999-01-01').getTime();
  const endDate = new Date('2026-08-15').getTime();
  const totalSpan = endDate - startDate;
  
  for (let i = 0; i < photoCount; i++) {
    // Distribute photos with some clustering
    const clusterBias = Math.pow(random(), 0.7); // More photos in later years
    const time = startDate + clusterBias * totalSpan;
    const date = new Date(time);
    
    // Add some randomness to date
    date.setDate(date.getDate() + Math.floor((random() - 0.5) * 30));
    
    photos.push(generatePhoto(i, date, random));
  }
  
  // Sort by date
  photos.sort((a, b) => (a.t ?? 0) - (b.t ?? 0));
  
  return {
    schema: 'deeputin-api-stage1-inventory-v1.0',
    source_mode: 'research',
    not_a_verdict: true,
    note: 'Mock data for UI-v7 development',
    photos,
    era_meta: ERAS,
    chronology_anomalies: {
      change_points: { years: [2007, 2012, 2016, 2020] },
      baseline_return: { years: [2010, 2018] },
      irreversible_return: { years: [] },
      chronology_rate: { years: [2014, 2022] },
      biological_rate: { years: [2015, 2023] },
    },
    analysis_manifest: {
      change_points: { years: [2012, 2020] },
    },
    analysis_stage: 'stage1_inventory',
    stage1_manifest: {
      total_photos: photoCount,
      processed_photos: photoCount,
    },
  };
}
