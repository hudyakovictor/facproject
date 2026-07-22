# 9 УГЛОВ — СХЕМА РАСПРЕДЕЛЕНИЯ И АНАЛИЗА
## Для журналиста-расследователя (двойники)

---

## 1. ВИЗУАЛЬНАЯ СХЕМА РАКУРСОВ НА ЛИЦЕ

```
                     ФРОНТ (frontal, yaw ≈ 0°)
                        ↑ верх (forehead, F00)
           ЛЕВЫЙ ПРОФИЛЬ      ПРАВЫЙ ПРОФИЛЬ
           (left_profile)      (right_profile)
                  \\        //
                   \\      //
                    \\    //
                     \\  //
                      \/
                  ПОДБОРОДОК (chin, CH)

                  ЛЕВАЯ СТОРОНА         ПРАВАЯ СТОРОНА
                  (left_deep/mid/light) (right_deep/mid/light)
```

---

## 2. КАК КАЖДЫЙ РАКУРС ВЛИЯЕТ НА ВИДИМОСТЬ ЗОН

### 2.1 Таблица видимости зон (`pose_policy.py`)

| Зона (A20) | Левый профиль | Левый глубокий | Левый средний | Левый лёгкий | Фронт | Правый лёгкий | Правый средний | Правый глубокий | Правый профиль |
|---|---|---|---|---|---|---|---|---|---|
| F00 (лоб) | limited | support | primary | primary | primary | primary | support | limited | exclude |
| BR_L (надбровная Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| BR_R (надбровная П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| OR_L (орбита Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| OR_R (орбита П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| NBT (нос) | support | support | primary | primary | primary | primary | primary | support | support |
| NW_L (крыло носа Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| NW_R (крыло носа П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| CB_L (скула Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| CB_R (скула П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| CS_L (щека Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| CS_R (щека П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| JW_L (челюсть Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| JW_R (челюсть П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| CH (подбородок) | support | support | primary | primary | primary | primary | primary | support | support |
| LZ_L (связка Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| LZ_R (связка П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| LO_L (орбит. связка Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| LO_R (орбит. связка П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| JA_L (угол челюсти Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| JA_R (угол челюсти П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |
| TP_L (висок Л) | primary | primary | primary | primary | primary | support | limited | exclude | exclude |
| TP_R (висок П) | exclude | exclude | support | support | primary | primary | primary | primary | primary |

---

## 3. МОРЩИННЫЕ ЗОНЫ (W14) — ПРИОРИТЕТ 100

```text
W14 содержит 14 фокусных масок морщин (priority 100):

FH_C  — горизонтальные лобные складки (центр)
FH_L  — горизонтальные лобные складки (лево)
FH_R  — горизонтальные лобные складки (право)
GL_V  — вертикальные межбровные складки
GL_H  — горизонтальные межбровные складки
CF_L  — гусиные лапки (лево)
CF_R  — гусиные лапки (право)
NL_L  — носогубная складка (лево)
NL_R  — носогубная складка (право)
MA_L  — линии марионетки (лево)
MA_R  — линии марионетки (право)
PO_U  — верхняя околоротовая зона
PO_L  — нижняя околоротовая зона (лево)
PO_R  — нижняя околоротовая зона (право)
```

### 3.1 Как морщины видны в разных ракурсах

Для каждого `pose_bin` морщинные зоны (`W14`) должны быть проверены:

```python
# Пример из pipeline.py:
ridge, sk, points, branches, wm = detect_wrinkles(
    crop, qm['quality_weight'],
    r.triangle_id, r.barycentric,
    triangles, surface_vertices, w14
)
```

**Важно для расследования:**
- **Горизонтальные лобные складки (`FH_C`, `FH_L`, `FH_R`)** должны быть видны во всех фронтальных и лёгких боковых фото.
- **Гусиные лапки (`CF_L`, `CF_R`)** видны лучше в боковых ракурсах (`left_light`, `right_light`).
- **Носогубные складки (`NL_L`, `NL_R`)** видны в профилях (`left_profile`, `right_profile`).
- **Межбровные (`GL_V`, `GL_H`)** лучше всего видны во фронтальном и лёгких поворотах.

---

## 4. КАК ПРОВЕРИТЬ НАЛОЖЕНИЕ ДВУХ ФОТО ОДНОГО РАКУРСА

### 4.1 Предлагаемый алгоритм проверки

```python
# Файл: PIPELINE_AUDIT/check_projection.py

def check_ideal_overlay_for_same_pose(photo_a_path, photo_b_path, pose_bin='frontal'):
    """
    Проверить, совпадают ли морщинные зоны для двух фото с одинаковым pose_bin
    но разным yaw (например, yaw_a = -5°, yaw_b = +3°).
    """
    # 1. Загрузить фото A и B
    # 2. Запустить stage1 для обоих
    # 3. Получить wrinkle_membership_w14 для A и B
    # 4. Применить геометрическую нормализацию (предлагается)
    # 5. Вычислить overlap (пересечение масок морщин)
    # 6. Вернуть overlap_score (0..1)
    pass
```

---

*Документ подготовлен для подготовки проекта. Он описывает, как 9 ракурсов влияют на видимость зон и морщин, и указывает на необходимость проверки наложения для сравнения фото с разным наклоном головы.*
