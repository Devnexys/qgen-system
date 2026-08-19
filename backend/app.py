"""
app.py
------
FastAPI main application — orchestrates the full MCQ generation pipeline.

Endpoints:
  POST /api/generate   → generate MCQs from text
  POST /api/upload     → upload a file and generate MCQs
  GET  /api/export/csv → download CSV of last session
  GET  /api/export/pdf → download PDF of last session
  GET  /api/health     → health check
  GET  /               → serve frontend
"""

import os
import uuid
import json
import random
import logging
import tempfile
from typing import Optional, List
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import io

# --- Module imports ---
from modules.text_extractor import extract_text
from modules.preprocessor import preprocess
from modules.nlp_analyzer import analyze_sentences, get_entity_type_map
from modules.question_generator import generate_questions_for_sentences
from modules.distractor_gen import generate_distractors
from modules.validator import validate_mcqs
from modules.difficulty import filter_by_difficulty
from modules.topic_detector import detect_topic, generate_explanation
from modules.exporter import export_to_csv, export_to_pdf
from config import UPLOAD_DIR

# --- Logging setup ---

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("qgen.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)

# --- App init ---
app = FastAPI(
    title="AI Question Generation System",
    description="Transform educational content into high-quality MCQs",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Serve frontend static files
FRONTEND_DIR = Path(__file__).parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# In-memory session store (for export functionality)
# In production, replace with Redis or DB
session_store: dict = {}


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class GenerateRequest(BaseModel):
    text: str = Field(..., min_length=100, description="Input educational text")
    num_questions: int = Field(5, ge=1, le=20, description="Number of questions to generate")
    difficulty: str = Field("medium", description="Difficulty: easy | medium | hard")
    use_t5: bool = Field(True, description="Use T5 model for generation")


class MCQOption(BaseModel):
    label: str
    text: str
    is_correct: bool


class MCQResponse(BaseModel):
    id: int
    question: str
    options: List[str]
    correct_answer: str
    correct_option_label: str
    explanation: str
    source_sentence: str
    difficulty: str
    confidence_score: float
    generation_method: str
    topic: str


class GenerationResponse(BaseModel):
    session_id: str
    total_generated: int
    topic: str
    questions: List[MCQResponse]
    message: str


# ── Core Pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(
    raw_text: str,
    num_questions: int = 5,
    difficulty: str = "medium",
    use_t5: bool = True
) -> dict:
    """
    Execute the full MCQ generation pipeline.
    
    Steps:
    1. Preprocess → clean sentences
    2. NLP analysis → entity/concept extraction
    3. Question generation → T5 + rule-based
    4. Distractor generation → semantic/entity-based
    5. Validation → QA + grammar + dedup + scoring
    6. Difficulty filtering → match requested level
    7. Topic detection → categorize content
    8. Explanation generation → per question
    
    Returns dict with 'questions' list and 'topic'
    """
    logger.info(f"Pipeline start: {num_questions} questions, difficulty={difficulty}")

    # Step 1: Preprocess
    sentences = preprocess(raw_text)
    logger.info(f"Step 1 done: {len(sentences)} valid sentences")

    if len(sentences) < 3:
        raise HTTPException(
            status_code=422,
            detail="Insufficient valid content. Please provide more educational text (minimum ~200 words)."
        )

    # Step 2: NLP Analysis
    analyzed = analyze_sentences(sentences)
    entity_type_map = get_entity_type_map(analyzed)
    logger.info(f"Step 2 done: {len(analyzed)} analyzed, {len(entity_type_map)} entity types")

    # Step 3: Topic detection (use top sentences)
    sample_text = " ".join(sentences[:20])
    topic_result = detect_topic(sample_text, use_model=False)  # keyword fallback for speed
    topic = topic_result["topic"]
    logger.info(f"Step 3 done: topic={topic}")

    # Step 4: Generate questions
    raw_questions = generate_questions_for_sentences(
        analyzed_sentences=analyzed,
        num_questions=num_questions * 2,  # generate extra, then filter
        difficulty=difficulty,
        use_t5=use_t5
    )
    logger.info(f"Step 4 done: {len(raw_questions)} raw questions generated")

    # Step 5: Generate distractors for each question
    for q in raw_questions:
        distractors = generate_distractors(
            answer=q["answer"],
            entity_type=q.get("entity_type"),
            entity_type_map=entity_type_map,
            source_sentence=q["source_sentence"],
            num_distractors=3
        )
        q["distractors"] = distractors

    # Step 6: Validate
    validated = validate_mcqs(raw_questions, confidence_threshold=0.30)
    logger.info(f"Step 6 done: {len(validated)} validated questions")

    # Step 7: Difficulty filter
    final_mcqs = filter_by_difficulty(validated, difficulty, num_questions)
    logger.info(f"Step 7 done: {len(final_mcqs)} final MCQs")

    # Step 8: Build final MCQ objects (shuffle options, add explanations)
    result_questions = []
    for idx, mcq in enumerate(final_mcqs):
        answer = mcq["answer"]
        distractors = mcq.get("distractors", [])

        # Build 4 options: 1 correct + 3 distractors
        options = [answer] + distractors[:3]
        while len(options) < 4:
            options.append(f"Option {len(options) + 1}")

        random.shuffle(options)
        correct_label = "ABCD"[options.index(answer)]

        # Explanation
        mcq["topic"] = topic
        explanation = generate_explanation(mcq)

        result_questions.append({
            "id": idx + 1,
            "question": mcq["question"],
            "options": options,
            "correct_answer": answer,
            "correct_option_label": correct_label,
            "explanation": explanation,
            "source_sentence": mcq["source_sentence"],
            "difficulty": mcq.get("difficulty", difficulty),
            "confidence_score": mcq.get("confidence_score", 0.5),
            "generation_method": mcq.get("generation_method", "rule_based"),
            "topic": topic
        })

    logger.info(f"Pipeline complete: {len(result_questions)} questions ready")
    return {"questions": result_questions, "topic": topic}


# ── API Endpoints ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the frontend HTML."""
    index_path = FRONTEND_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Frontend not found. Serve frontend/index.html</h1>")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "ok",
        "service": "AI Question Generation System",
        "version": "1.0.0"
    }


@app.post("/api/generate", response_model=GenerationResponse)
async def generate_from_text(request: GenerateRequest):
    """
    Generate MCQs from raw text input.
    """
    try:
        result = run_pipeline(
            raw_text=request.text,
            num_questions=request.num_questions,
            difficulty=request.difficulty,
            use_t5=request.use_t5
        )

        session_id = str(uuid.uuid4())[:8]
        session_store[session_id] = result["questions"]

        if not result["questions"]:
            return GenerationResponse(
                session_id=session_id,
                total_generated=0,
                topic=result["topic"],
                questions=[],
                message="No valid questions could be generated from the provided text. "
                         "Try providing more factual, declarative content."
            )

        return GenerationResponse(
            session_id=session_id,
            total_generated=len(result["questions"]),
            topic=result["topic"],
            questions=[MCQResponse(**q) for q in result["questions"]],
            message=f"Successfully generated {len(result['questions'])} questions"
        )

    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Generation error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Generation failed: {str(e)}")


@app.post("/api/upload", response_model=GenerationResponse)
async def generate_from_file(
    file: UploadFile = File(...),
    num_questions: int = Form(5),
    difficulty: str = Form("medium"),
    use_t5: bool = Form(True)
):
    """
    Upload a PDF, DOCX, or TXT file and generate MCQs.
    """
    allowed_types = {"pdf", "docx", "txt"}
    file_ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if file_ext not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: .{file_ext}. Allowed: {', '.join(allowed_types)}"
        )

    # Save uploaded file temporarily
    tmp_path = os.path.join(UPLOAD_DIR, f"{uuid.uuid4()}.{file_ext}")
    try:
        content = await file.read()
        with open(tmp_path, "wb") as f:
            f.write(content)
        logger.info(f"File uploaded: {file.filename} ({len(content)} bytes)")

        # Extract text
        raw_text = extract_text(tmp_path, file_ext)

        if not raw_text or len(raw_text.strip()) < 100:
            raise HTTPException(
                status_code=422,
                detail="Could not extract sufficient text from the file."
            )

        # Run pipeline
        result = run_pipeline(
            raw_text=raw_text,
            num_questions=num_questions,
            difficulty=difficulty,
            use_t5=use_t5
        )

        session_id = str(uuid.uuid4())[:8]
        session_store[session_id] = result["questions"]

        return GenerationResponse(
            session_id=session_id,
            total_generated=len(result["questions"]),
            topic=result["topic"],
            questions=[MCQResponse(**q) for q in result["questions"]],
            message=f"Generated {len(result['questions'])} questions from {file.filename}"
        )

    finally:
        # Clean up temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/api/export/csv/{session_id}")
async def export_csv(session_id: str):
    """Export questions from a session as CSV."""
    mcqs = session_store.get(session_id)
    if not mcqs:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    csv_bytes = export_to_csv(mcqs)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=mcqs_{session_id}.csv"}
    )


@app.get("/api/export/pdf/{session_id}")
async def export_pdf(session_id: str):
    """Export questions from a session as PDF."""
    mcqs = session_store.get(session_id)
    if not mcqs:
        raise HTTPException(status_code=404, detail="Session not found or expired")

    try:
        pdf_bytes = export_to_pdf(mcqs, title="AI-Generated MCQ Questions")
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=mcqs_{session_id}.pdf"}
        )
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
