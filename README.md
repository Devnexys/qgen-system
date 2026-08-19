# QGen AI — Intelligent Question Generation System

> Transform educational content into high-quality, exam-ready MCQs using T5, RoBERTa, spaCy, and a hybrid NLP pipeline.

---

## Features

- **Multi-format input**: PDF, DOCX, TXT, or raw text paste
- **AI-powered QG**: T5 transformer (valhalla/t5-base-qg-hl) with rule-based fallback
- **Smart distractors**: Entity substitution + WordNet siblings + spaCy vectors
- **Validation pipeline**: RoBERTa QA model re-verifies each answer
- **Confidence scoring**: Every question gets a 0–100% confidence score
- **Difficulty control**: Easy / Medium / Hard
- **Topic detection**: Auto-detects subject area (Science, History, Tech, etc.)
- **Export**: PDF (reportlab) and CSV
- **Quiz mode**: Interactive quiz with live scoring

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI + Uvicorn |
| NLP | spaCy `en_core_web_sm` |
| Question Generation | `valhalla/t5-base-qg-hl` (T5) |
| Answer Validation | `deepset/roberta-base-squad2` |
| Distractors | WordNet (NLTK) + spaCy vectors |
| PDF Parsing | pdfplumber |
| DOCX Parsing | python-docx |
| Export | reportlab (PDF) + csv stdlib |
| Frontend | Vanilla HTML/CSS/JS (Glassmorphism) |

---

## Project Structure

```
qgen-system/
├── backend/
│   ├── app.py                   # FastAPI main app
│   ├── config.py                # Configuration constants
│   ├── requirements.txt         # Python dependencies
│   ├── qgen.log                 # Auto-generated log file
│   ├── sample_data/
│   │   └── sample_text.txt      # Sample educational text
│   └── modules/
│       ├── text_extractor.py    # PDF/DOCX/TXT extraction
│       ├── preprocessor.py      # Text cleaning + sentence filtering
│       ├── nlp_analyzer.py      # spaCy NER, POS, SVO triples
│       ├── question_generator.py# T5 QG + rule-based templates
│       ├── distractor_gen.py    # Semantic distractor generation
│       ├── validator.py         # QA verification + dedup + scoring
│       ├── difficulty.py        # FK grade + question-type difficulty
│       ├── topic_detector.py    # BART zero-shot + keyword fallback
│       └── exporter.py          # PDF + CSV export
└── frontend/
    ├── index.html               # Single-page UI
    ├── css/style.css            # Dark glassmorphism design
    └── js/app.js                # Frontend logic
```

---

## Quick Start

### 1. Create Virtual Environment

```bash
cd qgen-system/backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Download spaCy Model

```bash
python -m spacy download en_core_web_sm
```

### 4. Pre-download ML Models (recommended — ~600MB)

```bash
python -c "
from transformers import T5Tokenizer, T5ForConditionalGeneration
from transformers import pipeline
T5Tokenizer.from_pretrained('valhalla/t5-base-qg-hl')
T5ForConditionalGeneration.from_pretrained('valhalla/t5-base-qg-hl')
pipeline('question-answering', model='deepset/roberta-base-squad2')
print('Models downloaded!')
"
```

### 5. Run the Server

```bash
cd backend
python app.py
```

Server starts at: **http://localhost:8000**

> Open your browser to `http://localhost:8000` to use the UI.

---

## API Reference

### `POST /api/generate`
Generate MCQs from raw text.

```json
{
  "text": "Your educational content...",
  "num_questions": 5,
  "difficulty": "medium",
  "use_t5": true
}
```

### `POST /api/upload`
Upload a file (multipart/form-data).

Fields: `file`, `num_questions`, `difficulty`, `use_t5`

### `GET /api/export/csv/{session_id}`
Download CSV export.

### `GET /api/export/pdf/{session_id}`
Download PDF export.

### `GET /api/health`
Health check.

---

## Testing with Sample Data

```bash
# Using curl
curl -X POST http://localhost:8000/api/generate \
  -H "Content-Type: application/json" \
  -d @- << 'EOF'
{
  "text": "The discovery of penicillin by Alexander Fleming in 1928 marked a revolutionary moment in medical history. Fleming noticed that a mold, Penicillium notatum, had contaminated one of his petri dishes and was killing the surrounding bacteria. Albert Einstein published his theory of special relativity in 1905, fundamentally changing our understanding of space, time, and energy. The famous equation E=mc² expresses the equivalence of mass and energy.",
  "num_questions": 3,
  "difficulty": "medium",
  "use_t5": false
}
EOF
```

Or use the **"Sample Text"** button in the UI.

---

## Performance Notes

| Setup | Speed per Question |
|-------|--------------------|
| GPU (CUDA) | ~0.5–1 sec |
| CPU (T5 enabled) | ~3–8 sec |
| CPU (T5 disabled, rule-based) | ~0.3 sec |

**Tip**: Toggle off "T5 Model" in the UI for faster generation using rule-based templates.

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `spacy model not found` | Run: `python -m spacy download en_core_web_sm` |
| `Port 8000 in use` | Change port in `app.py`: `uvicorn.run(..., port=8001)` |
| `reportlab not found` | Run: `pip install reportlab` |
| Slow first request | Models load lazily on first call; subsequent calls are faster |
| No questions generated | Ensure text is factual/declarative, not instructions or questions |

---

## License

MIT — for educational and research use.
