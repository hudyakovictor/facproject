/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import { Photo, EventPin, Era, PoseBucket, Hypothesis, FuzzyLabel } from './types';

// Birth Date of Subject
export const BIRTH_DATE = '1952-10-07';

// 5 Eras from the Technical Specification (ТЗ)
export const ERAS: Era[] = [
  {
    id: 'ERA_1_BASELINE',
    name: 'ERA 1: BASELINE (Эталон)',
    start: '1999-01-01',
    end: '2011-12-31',
    color: '#4f98a3', // teal
    description: 'Опорный исторический период. Стабильная лицевая геометрия и естественное старение кожи.'
  },
  {
    id: 'ERA_2_EARLY',
    name: 'ERA 2: EARLY CHANGES',
    start: '2012-01-01',
    end: '2014-12-31',
    color: '#e8af34', // gold
    description: 'Начало уловимых отклонений. Первые зафиксированные попытки косметического вмешательства.'
  },
  {
    id: 'ERA_3_UDMURT',
    name: 'ERA 3: UDMURT CLUSTER',
    start: '2015-01-01',
    end: '2021-09-08',
    color: '#dd6974', // red-pink
    description: 'Период экстремальных геометрических отклонений костной структуры. Пик гипотезы UDMURT.'
  },
  {
    id: 'ERA_4_TRANSITION',
    name: 'ERA 4: TRANSITION ZONE',
    start: '2021-09-09',
    end: '2023-09-30',
    color: '#fdab43', // orange
    description: 'Переходная фаза. Высокая хаотичность метрик, локальные флуктуации и фальш-старты.'
  },
  {
    id: 'ERA_5_VASILICH',
    name: 'ERA 5: VASILICH CURRENT',
    start: '2023-10-01',
    end: '2026-06-06',
    color: '#a86fdf', // purple
    description: 'Текущий обособленный кластер. Стабильные биометрические маркеры, отличные от эталонной геометрии.'
  }
];

// Historical events from publications corresponding to Section 7 & 15
export const EVENT_PINS: EventPin[] = [
  {
    id: 'DISAPPEARANCE_2015',
    date: '2015-03-11',
    label: 'DISAPPEARANCE 2015',
    icon: 'AlertTriangle',
    color: '#e8af34', // gold
    source: 'BBC News (2015)',
    description: '10-дневное исчезновение субъекта из публичного пространства. Возникновение первых организованных публикаций и аналитик о возможных двойниках.'
  },
  {
    id: 'BUDAN_STATEMENT',
    date: '2022-08-01',
    label: 'BUDAN STATEMENT',
    icon: 'Volume2',
    color: '#5591c7', // blue
    source: 'GUR (2022)',
    description: 'Публичное заявление Буданова о возможной замене и использовании двойников. Пресс-служба Кремля официально отвергла данные.'
  },
  {
    id: 'JP_AI_STUDY',
    date: '2023-11-20',
    label: 'JP AI STUDY',
    icon: 'Microscope',
    color: '#4f98a3', // teal
    source: 'Japanese AI Visual Lab (2023)',
    description: 'Публикация японского ИИ-исследования внешних изменений уха, походки и голоса, показавшая высокую вероятность несовпадений.'
  },
  {
    id: 'MINCHENKO_REPORT',
    date: '2024-04-15',
    label: 'MINCHENKO REPORT',
    icon: 'FileText',
    color: '#797876', // gray
    source: 'Minchenko Consulting (2024)',
    description: 'Экспертный доклад по публичным образам и управлению информационным пространством; анализ динамики медийных выступлений.'
  },
  {
    id: 'ERA_3_START',
    date: '2015-01-01',
    label: 'START ERA 3 (UDMURT)',
    icon: 'Play',
    color: '#dd6974', // red-pink
    source: 'Системная метка',
    description: 'Начало ERA_3_UDMURT. 480 аналитических снимков. Пик вероятности гипотезы H2 (U_UDMURT)'
  },
  {
    id: 'ERA_4_START',
    date: '2021-09-09',
    label: 'START ERA 4 (TRANS)',
    icon: 'Play',
    color: '#fdab43', // orange
    source: 'Системная метка',
    description: 'Вход в переходную хаотическую зону. Значительный рост среднеквадратичных отклонений.'
  },
  {
    id: 'ERA_5_START',
    date: '2023-10-01',
    label: 'START ERA 5 (VASILICH)',
    icon: 'Play',
    color: '#a86fdf', // purple
    source: 'Системная метка',
    description: 'Вход в кластер ERA_5_VASILICH. Формирование нового устойчивого стационарного состояния.'
  },
  {
    id: 'RTR_EVENT',
    date: '2025-02-15',
    label: 'RETURN TO BASELINE',
    icon: 'RefreshCw',
    color: '#ffffff', // white
    source: 'Forensic System Flag',
    description: 'RETURN_TO_BASELINE флаг зафиксирован. Временный статистический откат метрик лица к показателям оригинальной ERA_1.'
  }
];

// Seedable random helper to make data generation 100% deterministic & robust
function mulberry32(a: number) {
  return function() {
    let t = a += 0x6D2B79F5;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

// Generates exactly 1809 photos distributed over time matching the stats in Appendix A:
// ERA 1: 520
// ERA 2: 180
// ERA 3: 480
// ERA 4: 210
// ERA 5: 419
export function generateDataset(): Photo[] {
  const photos: Photo[] = [];
  const rand = mulberry32(19521007); // Seed based on birthday

  // Map out durations and distribute points
  const distributions = [
    { eraId: 'ERA_1_BASELINE', count: 520, startYear: 1999, endYear: 2011 },
    { eraId: 'ERA_2_EARLY', count: 180, startYear: 2012, endYear: 2014 },
    { eraId: 'ERA_3_UDMURT', count: 480, startYear: 2015, endYear: 2021 },
    { eraId: 'ERA_4_TRANSITION', count: 210, startYear: 2021, endYear: 2023 },
    { eraId: 'ERA_5_VASILICH', count: 419, startYear: 2023, endYear: 2026 }
  ];

  const buckets: PoseBucket[] = ['frontal_0', 'frontal_yaw15', 'frontal_yaw30', 'profile_L', 'profile_R'];

  // Track dates across generations
  let photoIndex = 1;

  distributions.forEach((dist) => {
    const { eraId, count, startYear, endYear } = dist;
    
    // Generate dates spread nicely through the interval
    const totalDays = (endYear - startYear + 1) * 365;
    const dayDelta = totalDays / (count + 1);

    for (let i = 0; i < count; i++) {
        // Calculate deterministic date
        const offsetDays = Math.round((i + 1) * dayDelta + (rand() * 10 - 5));
        const dateObj = new Date(startYear, 0, 1);
        dateObj.setDate(dateObj.getDate() + offsetDays);

        // Cap to absolute max date June 6, 2026
        if (dateObj.getTime() > new Date('2026-06-06').getTime()) {
          dateObj.setTime(new Date(`2026-06-0${Math.floor(rand() * 5 + 1)}`).getTime());
        }

        const year = dateObj.getFullYear();
        const month = dateObj.getMonth() + 1;
        const day = dateObj.getDate();
        const dateStr = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;

        // Pose bucket distributed: frontal_0 is more common
        const bucketRand = rand();
        let poseBucket: PoseBucket = 'frontal_0';
        if (bucketRand < 0.50) poseBucket = 'frontal_0';
        else if (bucketRand < 0.65) poseBucket = 'frontal_yaw15';
        else if (bucketRand < 0.80) poseBucket = 'frontal_yaw30';
        else if (bucketRand < 0.90) poseBucket = 'profile_L';
        else poseBucket = 'profile_R';

        // Quality attributes
        const qOverall = 0.25 + rand() * 0.70;
        const qBlur = rand() * 0.3;
        const qNoise = rand() * 0.25;

        // Calendar age in decimal years
        const birthTime = new Date(BIRTH_DATE).getTime();
        const calendarAge = (dateObj.getTime() - birthTime) / (1000 * 60 * 60 * 24 * 365.25);

        // Biometric & texture states change by Era
        let h0 = 1.0, h1 = 0.0, h2 = 0.0;
        let dominantHypothesis: Hypothesis = 'H0';
        let fuzzyLabel: FuzzyLabel = 'STRONGLY_MATCHING';
        
        // Base geometry deviations (z-scores)
        let deltaOrbit = 0.0, deltaChin = 0.0, deltaJaw = 0.0, deltaCheek = 0.0, deltaSymm = 1.0;
        // Textures
        let tSilicone = 0.02, tSpecular = 0.35, tLbp = 0.45, tFrangi = 0.85, tWrinkleNasolabial = 0.1, tWrinkleForehead = 0.1, tSubsurface = 0.15;

        const flags: string[] = [];

        // Build Era specific models
        if (eraId === 'ERA_1_BASELINE') {
          // Stable reference period
          deltaOrbit = (rand() - 0.5) * 0.8;
          deltaChin = (rand() - 0.5) * 0.7;
          deltaJaw = (rand() - 0.5) * 0.6;
          deltaCheek = (rand() - 0.5) * 0.5;
          deltaSymm = 0.95 + rand() * 0.05;

          // Natural skin progression
          tWrinkleForehead = 0.05 + ((year - 1999) / 25) * 0.15;
          tWrinkleNasolabial = 0.08 + ((year - 1999) / 25) * 0.12;
          tSpecular = 0.55 - ((year - 1999) / 25) * 0.15;
          tLbp = 0.40 + ((year - 1999) / 25) * 0.10;
          tFrangi = 0.90 - ((year - 1999) / 25) * 0.15;
          tSilicone = 0.00 + rand() * 0.05;
          tSubsurface = 0.10 + rand() * 0.08;

          h0 = 0.85 + rand() * 0.13;
          h1 = 0.05 + rand() * 0.07;
          h2 = 1.0 - h0 - h1;
          dominantHypothesis = 'H0';
          fuzzyLabel = h0 > 0.93 ? 'STRONGLY_MATCHING' : 'CONSISTENT';
        } 
        else if (eraId === 'ERA_2_EARLY') {
          // Starting alterations
          deltaOrbit = (rand() - 0.5) * 1.5;
          deltaChin = 0.5 + rand() * 1.2;
          deltaJaw = (rand() - 0.5) * 1.5;
          deltaCheek = (rand() - 0.5) * 1.2;
          deltaSymm = 0.90 + rand() * 0.08;

          tWrinkleForehead = 0.22 - (rand() * 0.08); // Slight smoothing
          tWrinkleNasolabial = 0.20 + rand() * 0.10;
          tSpecular = 0.45 + rand() * 0.15; // Shinier specular (injectables)
          tLbp = 0.52 + rand() * 0.08;
          tFrangi = 0.70 + rand() * 0.08;
          tSilicone = 0.08 + rand() * 0.12;
          tSubsurface = 0.18 + rand() * 0.12;

          h0 = 0.55 + rand() * 0.20;
          h1 = 0.30 + rand() * 0.15;
          h2 = 1.0 - h0 - h1;
          dominantHypothesis = 'H0';
          fuzzyLabel = h1 > 0.35 ? 'WEAK_EVIDENCE' : 'CONSISTENT';

          if (rand() < 0.05) {
            flags.push('EXIF_DATE_ANOMALY');
          }
        } 
        else if (eraId === 'ERA_3_UDMURT') {
          // High Bone deviation, "Udmurt" mask suspicions
          deltaOrbit = 2.2 + rand() * 1.6; // High Orbits depth!
          deltaChin = 2.5 + rand() * 1.8;  // High Chin projection!
          deltaJaw = 0.5 + rand() * 1.5;
          deltaCheek = 1.8 + rand() * 1.9;
          deltaSymm = 0.85 + rand() * 0.10;

          tWrinkleForehead = 0.11 + rand() * 0.09; // Drastic decrease (botox)
          tWrinkleNasolabial = 0.15 + rand() * 0.08;
          tSpecular = 0.68 + rand() * 0.18; // Very shiny skin
          tLbp = 0.70 + rand() * 0.15;
          tFrangi = 0.50 + rand() * 0.15;
          tSilicone = 0.38 + rand() * 0.25; // Silicone probability spikes!
          tSubsurface = 0.45 + rand() * 0.20;

          h0 = 0.15 + rand() * 0.15;
          h1 = 0.55 + rand() * 0.20;
          h2 = 1.0 - h0 - h1;
          dominantHypothesis = 'H1';
          fuzzyLabel = rand() < 0.4 ? 'SUSPICIOUS_TEXTURE' : 'GEOMETRIC_MISMATCH';

          // Critical markers based on math
          if (deltaOrbit > 3.0 || deltaChin > 3.2) {
            flags.push('IDENTITY_ANOMALY');
          }
          if (rand() < 0.15) {
            flags.push('TEXTURE_SPIKE');
          }
          if (rand() < 0.08) {
            flags.push('IMPOSSIBLE_SHORT');
            flags.push('TEMPORAL_IMPOSSIBILITY');
          }
        } 
        else if (eraId === 'ERA_4_TRANSITION') {
          // Great turbulence and chaotic transitions
          deltaOrbit = 1.0 + rand() * 2.5;
          deltaChin = 1.2 + rand() * 2.5;
          deltaJaw = 1.5 + rand() * 2.5;
          deltaCheek = 1.0 + rand() * 2.5;
          deltaSymm = 0.80 + rand() * 0.15;

          tWrinkleForehead = 0.15 + rand() * 0.20;
          tWrinkleNasolabial = 0.20 + rand() * 0.15;
          tSpecular = 0.50 + rand() * 0.25;
          tLbp = 0.60 + rand() * 0.20;
          tFrangi = 0.60 + rand() * 0.20;
          tSilicone = 0.20 + rand() * 0.20;
          tSubsurface = 0.30 + rand() * 0.15;

          h1 = 0.40 + rand() * 0.25;
          h0 = 0.25 + rand() * 0.25;
          h2 = 1.0 - h0 - h1;
          dominantHypothesis = h1 > h2 ? (h1 > h0 ? 'H1' : 'H0') : (h2 > h0 ? 'H2' : 'H0');
          fuzzyLabel = 'WEAK_EVIDENCE';
          
          flags.push('TRANSITION');

          // Local recurrence/return to baseline
          if (rand() < 0.18) {
            h0 = 0.72;
            h1 = 0.18;
            h2 = 0.10;
            dominantHypothesis = 'H0';
            fuzzyLabel = 'CONSISTENT';
            flags.push('RETURN_TO_BASELINE');
          }
        } 
        else {
          // ERA_5_VASILICH (2023-10 to 2026): The current dominant cluster
          deltaOrbit = 3.2 + rand() * 1.1;  // Totally distinct osteology
          deltaChin = 3.8 + rand() * 0.9;
          deltaJaw = 2.9 + rand() * 1.2;
          deltaCheek = 3.4 + rand() * 1.0;
          deltaSymm = 0.92 + rand() * 0.05;

          tWrinkleForehead = 0.09 + rand() * 0.06; // Rejuvenation skin
          tWrinkleNasolabial = 0.12 + rand() * 0.05;
          tSpecular = 0.75 + rand() * 0.12; 
          tLbp = 0.72 + rand() * 0.08;
          tFrangi = 0.42 + rand() * 0.08;
          tSilicone = 0.52 + rand() * 0.22; // High silicone mask signal
          tSubsurface = 0.54 + rand() * 0.16;

          h0 = 0.02 + rand() * 0.06;
          h1 = 0.30 + rand() * 0.15;
          h2 = 1.0 - h0 - h1; // Identity swap dominates!
          dominantHypothesis = h2 > h1 ? 'H2' : 'H1';
          fuzzyLabel = h2 > 0.55 ? 'IDENTITY_ANOMALY' : 'GEOMETRIC_MISMATCH';

          if (rand() < 0.12) {
            flags.push('TEXTURE_SPIKE');
          }
          if (rand() < 0.10) {
            flags.push('TEMPORAL_IMPOSSIBILITY');
          }
        }

        // Apply fallback if quality is very low
        if (qOverall < 0.35) {
          fuzzyLabel = 'INSUFFICIENT_DATA';
        }

        // Calculate visual age based on requested parameters
        // visual_age = 45.0 + wrinkle_forehead * 40.0 + wrinkle_nasolabial * 35.0 + spot_density * 25.0 + lbp_entropy * 15.0 + gloss * (-10.0) + wrinkle_mix * 18.0
        const spot_density = (tLbp * 0.6) + (tSilicone * 0.4);
        const wrinkle_mix = (tWrinkleForehead + tWrinkleNasolabial) / 2;
        let visualAge = 45.0 
                        + (tWrinkleForehead * 40.0) 
                        + (tWrinkleNasolabial * 35.0) 
                        + (spot_density * 25.0) 
                        + (tLbp * 15.0) 
                        + (tSpecular * (-10.0)) 
                        + (wrinkle_mix * 18.0);
        
        // Refine visual age to match era context
        if (eraId === 'ERA_1_BASELINE') {
          // Normal aging
          visualAge = calendarAge + (rand() * 4 - 2);
        } else if (eraId === 'ERA_5_VASILICH') {
          // Drastic artificial rejuvenation
          visualAge = calendarAge - 15.0 - (rand() * 5); // Subject looks 15-20 years younger than actual calendar age (under-the-mask phenomenon)
        }

        // Build coordinate arrays for face mesh overlays
        const meshVertices = generateFaceMesh(eraId, rand);

        // Save
        const photo: Photo = {
          id: `FSC_${String(photoIndex).padStart(5, '0')}`,
          date: dateStr,
          year,
          month,
          day,
          poseBucket,
          quality: {
            overallScore: Math.round(qOverall * 100) / 100,
            blur: Math.round(qBlur * 100) / 100,
            noise: Math.round(qNoise * 100) / 100,
          },
          exifYear: flags.includes('EXIF_DATE_ANOMALY') ? year - 15 : year,
          isHidden: false,
          dominantHypothesis,
          posteriors: {
            H0: Math.round(h0 * 100) / 100,
            H1: Math.round(h1 * 100) / 100,
            H2: Math.round(h2 * 100) / 100,
          },
          fuzzyLabel,
          confidence: Math.round((0.55 + rand() * 0.4) * 100) / 100,
          geometry: {
            geometry_score: Math.round(((deltaOrbit + deltaChin + deltaJaw) / 3) * 100) / 100,
            orbit_depth: Math.round(deltaOrbit * 100) / 100,
            orbit_fossa: Math.round((deltaOrbit * 0.8 + rand() * 0.4) * 100) / 100,
            chin_projection: Math.round(deltaChin * 100) / 100,
            gonial_angle: Math.round((2.0 + deltaChin * 0.5 + rand() * 0.3) * 100) / 100,
            jaw_width: Math.round(deltaJaw * 100) / 100,
            bigonial: Math.round((deltaJaw * 0.9 + rand() * 0.2) * 100) / 100,
            mandibular_body: Math.round((deltaJaw * 1.1 + rand() * 0.3) * 100) / 100,
            ramus_height: Math.round(deltaCheek * 100) / 100,
            zygomatic_arch: Math.round((deltaCheek * 1.2 + rand() * 0.4) * 100) / 100,
            symmetry_score: Math.round(deltaSymm * 100) / 100,
            pose_yaw_deg: Math.round((poseBucket === 'frontal_0' ? (rand() - 0.5) * 4 : poseBucket.includes('15') ? 15 + (rand() - 0.5) * 5 : poseBucket.includes('30') ? 30 + (rand() - 0.5) * 5 : 65 + (rand() - 0.5) * 10) * 100) / 100,
          },
          texture: {
            texture_silicone_prob: Math.round(tSilicone * 100) / 100,
            texture_specular_gloss: Math.round(tSpecular * 100) / 100,
            texture_lbp_complexity: Math.round(tLbp * 100) / 100,
            texture_frangi_vessel: Math.round(tFrangi * 100) / 100,
            texture_wrinkle_forehead: Math.round(tWrinkleForehead * 100) / 100,
            texture_wrinkle_nasolabial: Math.round(tWrinkleNasolabial * 100) / 100,
            texture_subsurface_scatter_proxy: Math.round(tSubsurface * 100) / 100,
          },
          flags,
          visualAge: Math.round(visualAge * 10) / 10,
          calendarAge: Math.round(calendarAge * 10) / 10
        };

        // Inject custom properties if clicked
        (photo as any).meshVertices = meshVertices;

        photos.push(photo);
        photoIndex++;
    }
  });

  // Sort photos chronologically by date
  return photos.sort((a, b) => a.date.localeCompare(b.date));
}

// Generate an exciting set of 106 physical landmark paths on the face based on the ERA model
function generateFaceMesh(eraId: string, rand: () => number): [number, number, string][] {
  // Let's generate points corresponding to orbits, cheeks, chin, jaw etc.
  const points: [number, number, string][] = [];

  // 1. Forehead points (zone_forehead)
  for (let idx = 0; idx < 12; idx++) {
    const x = 50 + 35 * Math.cos((Math.PI * idx) / 11 - Math.PI);
    const y = 30 - 15 * Math.sin((Math.PI * idx) / 11) + (rand() * 1.5);
    points.push([Math.round(x), Math.round(y), 'forehead']);
  }

  // 2. Left eye and orbit (zone_left_orbit)
  const isModified = eraId === 'ERA_3_UDMURT' || eraId === 'ERA_5_VASILICH';
  const orbitDelta = isModified ? 3 : 0;

  for (let idx = 0; idx < 8; idx++) {
    const angle = (Math.PI * 2 * idx) / 8;
    const x = 35 + (6 + orbitDelta * 0.4) * Math.cos(angle);
    const y = 45 + (4 + orbitDelta * 0.2) * Math.sin(angle);
    points.push([Math.round(x), Math.round(y), 'left_orbit']);
  }

  // 3. Right eye and orbit (zone_right_orbit)
  for (let idx = 0; idx < 8; idx++) {
    const angle = (Math.PI * 2 * idx) / 8;
    const x = 65 + (6 + orbitDelta * 0.4) * Math.cos(angle);
    const y = 45 + (4 + orbitDelta * 0.2) * Math.sin(angle);
    points.push([Math.round(x), Math.round(y), 'right_orbit']);
  }

  // 4. Nose bridge and tip (nose)
  points.push([50, 40, 'nose']);
  points.push([50, 48, 'nose']);
  points.push([50, 56, 'nose']);
  points.push([44, 58, 'nose_base']);
  points.push([50, 59, 'nose_base']);
  points.push([56, 58, 'nose_base']);

  // 5. Left and Right Cheekbones (zygomatic_arch)
  const cheekShift = isModified ? 4.5 : 0;
  points.push([22 - cheekShift * 0.5, 52, 'left_cheek']);
  points.push([26 - cheekShift * 0.3, 58, 'left_cheek']);
  points.push([78 + cheekShift * 0.5, 52, 'right_cheek']);
  points.push([74 + cheekShift * 0.3, 58, 'right_cheek']);

  // 6. Lips / Mouth (mouth - excluded in some tabs but visualizable)
  for (let idx = 0; idx < 12; idx++) {
    const angle = (Math.PI * 2 * idx) / 12;
    const x = 50 + 12 * Math.cos(angle);
    const y = 68 + 6 * Math.sin(angle);
    points.push([Math.round(x), Math.round(y), 'mouth']);
  }

  // 7. Chin / Jaw silhouette (gonial_angle & chin_projection)
  const chinShift = isModified ? 6.0 : 0;
  const jawOut = isModified ? 4.0 : 0;

  // Face bottom edge loop (17 points total)
  const boneAnatomyCoords: [number, number, string][] = [
    [18, 42, 'jaw_rim'], [19, 50, 'jaw_rim'], [21, 58, 'jaw_rim'], [24, 66, 'jaw_rim'],
    [28, 74 + jawOut * 0.2, 'gonial_angle'], [33, 81 + jawOut * 0.4, 'gonial_angle'],
    [39, 87 + chinShift * 0.3, 'chin'], [44, 91 + chinShift * 0.6, 'chin'],
    [50, 93 + chinShift * 0.8, 'chin'], // Center chin tip
    [56, 91 + chinShift * 0.6, 'chin'], [61, 87 + chinShift * 0.3, 'chin'],
    [67, 81 + jawOut * 0.4, 'gonial_angle'], [72, 74 + jawOut * 0.2, 'gonial_angle'],
    [76, 66, 'jaw_rim'], [79, 58, 'jaw_rim'], [81, 50, 'jaw_rim'], [82, 42, 'jaw_rim']
  ];
  
  points.push(...boneAnatomyCoords);

  return points;
}
