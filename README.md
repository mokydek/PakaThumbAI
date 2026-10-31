# PakaThumbAI

Локальный ИИ для генерации thumbnail'ов (YouTube 1280×720 и Roblox 1920×1080) на RTX 3050.

- **Генерация:** [ComfyUI](https://github.com/comfyanonymous/ComfyUI) + модель DreamShaper 8 (Stable Diffusion 1.5).
- **Обучение своего стиля:** LoRA через [kohya sd-scripts](https://github.com/kohya-ss/sd-scripts) (движок kohya_ss), уже настроено под 4–8 ГБ видеопамяти.

## Что нужно

- Windows 10/11, видеокарта NVIDIA (RTX 3050 4/6/8 ГБ).
- Драйвер NVIDIA **580 или новее** ([скачать](https://www.nvidia.com/drivers)).
- ~25 ГБ свободного места.

Python и Git ставить не надо: `install.bat` всё скачает сам.

## Установка

Дважды кликни **`install.bat`**. Скрипт:

1. проверит видеокарту и драйвер;
2. поставит [uv](https://github.com/astral-sh/uv) (он сам скачает нужный Python);
3. скачает ComfyUI 0.43.2 и sd-scripts 0.9.1 в папку `app`;
4. поставит PyTorch с CUDA для каждого;
5. скачает базовую модель DreamShaper 8 (~2 ГБ) в `models/checkpoints`;
6. проверит, что PyTorch видит видеокарту.

Если что-то оборвалось, просто запусти `install.bat` ещё раз: уже скачанное он пропустит.

## Генерация

**Через командную строку** (из папки проекта):

```bat
generate.bat "a hydraulic press crushing a giant watermelon, juice splash"
generate.bat "a scared roblox character running from a monster in a dark forest" --size roblox -n 6
```

| Параметр | Что делает | По умолчанию |
|---|---|---|
| `-n` | сколько вариантов | 4 |
| `--size` | `youtube` (1280×720) или `roblox` (1920×1080) | youtube |
| `--lora` | `auto` / `none` / имя файла из `models/loras` | auto |
| `--strength` | сила LoRA | 0.8 |
| `--seed` | зерно (одинаковое = одинаковая картинка) | случайное |
| `--steps` / `--cfg` | шаги и «послушность» промпту | 25 / 6.5 |
| `--negative` | что ещё убрать из картинки | — |
| `--style` | `default` (яркий), `horror` (тёмный хоррор), `none` | default |

Картинки сохраняются в папку **`outputs`**. Если ComfyUI не запущен, `generate.bat` сам поднимет его в фоне и оставит работать, поэтому следующие генерации идут быстрее. `train.bat` перед обучением сам закрывает ComfyUI, чтобы освободить видеопамять.

Промпт пиши **на английском**: модель понимает только его. Текст (надписи) на thumbnail лучше добавлять потом в редакторе: SD 1.5 рисует буквы криво, поэтому они убраны негативным промптом.

**Через браузер:** `start.bat` откроет ComfyUI. Перетащи в окно файл `workflows/thumbnail.json`, поменяй промпт в узле *Positive prompt* и нажми **Run**. Узел *Thumbnail LoRA* сначала выключен (фиолетовый): после обучения выдели его и нажми `Ctrl+B`, чтобы включить. Для Roblox поставь в узле *Final size* 1920×1080.

## Обучение своего стиля (LoRA)

1. Наполни папку **`dataset`** картинками в нужном стиле (png/jpg/webp). Два способа, можно вместе:
   - **`make_dataset.bat`** сам сгенерирует 120 картинок в стиле Roblox-thumbnails (40 сцен из `config/dataset_prompts.txt` по 3 варианта, на 3050 примерно 40–90 минут). Каждая сохраняется как `gen_001.png` + подпись `gen_001.txt`. Потом открой папку и удали неудачные вместе с их `.txt`: лучше оставить 40–60 хороших, чем 120 средних. Сцены можно менять и дописывать в том же файле. Параметры: `--per-prompt 2` (сколько вариантов на сцену), `--limit 10` (только первые 10 сцен).
   - Свои thumbnail'ы и скриншоты из своих игр: просто положи их в `dataset`.
2. Подписи по желанию: рядом с `img1.png` положи `img1.txt` с описанием на английском. Начинай подпись с `pakathumb thumbnail, ...`. Без подписи используется просто `pakathumb thumbnail`.
3. Запусти **`train.bat`**.

Готовая LoRA появится в `models/loras/pakathumb.safetensors`, промежуточные версии сохраняются каждые 2 эпохи (`pakathumb-000002.safetensors` и т.д.). Дальше `generate.bat` подключает её сам. Сравнить с промежуточной версией можно так: `--lora pakathumb-000006`.

Время: 30 картинок дают ~3000 шагов, на RTX 3050 это примерно 20–40 минут. На картах с 4 ГБ скрипт сам включает облегчённый режим (учится только U-Net, LoRA меньше).

Настройки обучения лежат в `config/train_lora.toml` и `config/dataset.toml`.

### Хоррор-LoRA (Roblox horror)

Отдельная LoRA `pakahorror` под хоррор-thumbnail'ы в roblox-стиле: тёмный кадр с одним источником света, бледный монстр крупно в кадре (выглядывает из-за двери, ползёт по коридору), зерно, виньетка, приглушённые цвета с красным акцентом. Без крови и жестокости.

```bat
app\ComfyUI\venv\Scripts\python.exe tools\make_dataset.py --prompts config\dataset_prompts_horror.txt --out dataset_horror --prefix hor
train.bat -Dataset dataset_horror -Name pakahorror
generate.bat "pale blocky roblox monster peeking from behind a door" --lora pakahorror --style horror
```

`--style horror` меняет стиль промпта на хоррор (по умолчанию стоит яркий `default`). Сцены и настройки стиля лежат в `config/dataset_prompts_horror.txt`: строки `prefix:`, `style:`, `negative:` в начале файла.

## Правила

- Для датасета бери **только свои** картинки или те, на которые у тебя есть права. Чужие thumbnail'ы и арты нельзя.
- Thumbnail'ы для Roblox должны соответствовать [Roblox Community Standards](https://about.roblox.com/community-standards): никакой крови, жестокости, 18+, обманных обещаний наград, логотипов и персонажей чужих брендов. Кровь/18+ уже в негативном промпте, но проверяй каждую картинку глазами перед загрузкой.

## Структура

```
install.bat / start.bat / generate.bat / make_dataset.bat / train.bat
scripts/              скрипты установки и обучения
tools/generate.py     генератор (работает через API ComfyUI)
tools/make_dataset.py генератор датасета для обучения
workflows/            схема генерации для ComfyUI (thumbnail.json - для браузера,
                      thumbnail_api.json - для generate.bat)
config/               настройки обучения, путей к моделям и сцены для датасета
dataset/              сюда картинки для обучения
models/checkpoints/   базовая модель
models/loras/         твои LoRA
outputs/              готовые thumbnail'ы
app/                  ComfyUI и sd-scripts (ставятся install.bat)
```
