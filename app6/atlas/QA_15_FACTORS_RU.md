# QA атласа v4 по 15 факторам

**Итог: 99.2/100 — PASS**

| Фактор | Балл | Проверка |
|---|---:|---|
| 1. Полнота покрытия | 100.0 | assigned 69873/69873 |
| 2. Непересечение зон | 100.0 | one integer label per triangle |
| 3. Все 40 зон непустые | 100.0 | empty zones=0 |
| 4. Связность зон | 95.0 | single-component 38/40 |
| 5. Нет случайных микрозон | 100.0 | min non-small area 0.893% |
| 6. Нет чрезмерных зон | 100.0 | max area 6.735% |
| 7. Баланс основных зон | 92.8 | max/min(non-small)=7.54 |
| 8. Левая/правая симметрия | 99.9 | mean pair diff 0.09% |
| 9. Логика лба | 100.0 | center/left/right; temples separate |
| 10. Полный нос | 100.0 | nasion/dorsum/tip/ala/columella |
| 11. Зоны вокруг глаз | 100.0 | eyelids + infraorbital + zygomatic |
| 12. Носогубные и околоротовые | 100.0 | nasolabial/philtrum/mouth corners/below-lip |
| 13. Политика 9 ракурсов | 100.0 | all pose bins exported |
| 14. Машинный контракт | 100.0 | JSON + NPZ, no object dtype |
| 15. Чистый рендер + debug | 100.0 | clean map, legend, mesh debug |