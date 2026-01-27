# Smart Park View

Минималистичное веб-приложение для отслеживания занятых и свободных парковочных мест с использованием видео с топвью (вид сверху).

## Возможности

- Поддержка видеофайлов, веб-камеры и IP-потоков
- Интерактивная калибровка парковочных мест (рисование полигонов)
- Определение занятости в реальном времени с использованием OpenCV
- Минималистичный UI с темной темой (черный + зеленый акцент)
- Сохранение конфигурации в localStorage

## Технологии

**Frontend:**
- React 18 + TypeScript
- Vite
- Lucide React (иконки)
- HTML5 Video + Canvas

**Backend:**
- Python 3.10+
- Flask + Flask-CORS + Flask-Sock
- OpenCV для обработки видео
- Опционально: YOLOv8 для улучшенной детекции

## Установка и запуск

### 1. Backend

```bash
cd backend

# Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Запустить сервер
python app.py
```

Backend будет доступен на `http://localhost:5001`

### 2. Frontend

```bash
cd frontend

# Установить зависимости
npm install

# Запустить dev-сервер
npm run dev
```

Frontend будет доступен на `http://localhost:3000`

### 3. Тестовое видео

Положите тестовый видеофайл `1087118309-test.mp4` в папку `frontend/public/`

## Использование

1. Откройте `http://localhost:3000` в браузере
2. Выберите источник видео (файл, камера или поток)
3. Укажите количество парковочных мест
4. Нажмите "Начать калибровку"
5. Для каждого места нарисуйте полигон, кликая по углам
6. После калибровки начнется мониторинг в реальном времени

## Алгоритм детекции

Базовый детектор использует комбинацию методов:

1. **Edge Detection (Canny)** — анализ плотности границ в области
2. **Intensity Variance** — анализ текстуры (автомобили имеют более высокую вариацию)
3. **Background Subtraction** — выделение движущихся/новых объектов

Для более точной детекции можно использовать YOLO:

```bash
pip install ultralytics
```

И изменить в `detector.py` использование `YOLOParkingDetector` вместо `ParkingDetector`.

## Структура проекта

```
smart-park-view/
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── SetupScreen.tsx      # Экран настройки
│   │   │   ├── SidePanel.tsx        # Боковая панель статистики
│   │   │   ├── VideoPlayer.tsx      # Видеоплеер с canvas overlay
│   │   │   └── CalibrationOverlay.tsx
│   │   ├── hooks/
│   │   │   ├── useFullscreen.ts
│   │   │   └── useVideoProcessor.ts
│   │   ├── utils/
│   │   │   ├── storage.ts           # LocalStorage
│   │   │   └── geometry.ts          # Геометрические утилиты
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── styles/
│   │   │   └── index.css
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── public/
│       └── 1087118309-test.mp4      # Тестовое видео
├── backend/
│   ├── app.py                       # Flask сервер
│   ├── detector.py                  # Детектор занятости
│   └── requirements.txt
└── README.md
```

## API

### WebSocket `/ws`

Отправка кадра:
```json
{
  "type": "frame",
  "data": "data:image/jpeg;base64,...",
  "spots": [
    {
      "id": "spot-1",
      "polygon": [{"x": 100, "y": 100}, {"x": 200, "y": 100}, ...]
    }
  ]
}
```

Ответ:
```json
{
  "occupancyMap": {
    "spot-1": true,
    "spot-2": false
  }
}
```

## Лицензия

MIT
