"""
validator.py
------------
Validation pipeline for generated MCQs:
- QA-based answer verification (RoBERTa SQuAD2)
- Grammar check
- Deduplication (fuzzy matching)
- Confidence scoring
"""

import logging
import re
from typing import List, Dict, Any, Optional
from fuzzywuzzy import fuzz
from transformers import pipeline

logger = logging.getLogger(__name__)

_qa_pipeline = None
QA_MODEL = "deepset/roberta-base-squad2"


def load_qa_pipeline():
    """Load QA pipeline for answer verification."""
    global _qa_pipeline
    if _qa_pipeline is None:
        logger.info(f"Loading QA model '{QA_MODEL}'...")
        _qa_pipeline = pipeline(
            "question-answering",
            model=QA_MODEL,
            tokenizer=QA_MODEL,
            device=-1  # CPU; change to 0 for GPU
        )
        logger.info("QA model loaded")
    return _qa_pipeline


def verify_answer(question: str, answer: str, context: str) -> Dict[str, Any]:
    """
    Use RoBERTa QA model to verify that the correct answer is extractable
    from the source context given the question.
    
    Returns:
        dict with 'verified' (bool), 'predicted_answer', 'confidence' (float)
    """
    try:
        qa = load_qa_pipeline()
        result = qa(question=question, context=context)
        predicted = result["answer"].strip()
        confidence = float(result["score"])

        # Check if predicted answer overlaps significantly with correct answer
        overlap = fuzz.partial_ratio(predicted.lower(), answer.lower())
        verified = overlap >= 60 and confidence >= 0.3

        return {
            "verified": verified,
            "predicted_answer": predicted,
            "confidence": round(confidence, 3),
            "overlap_score": overlap
        }
    except Exception as e:
        logger.warning(f"QA verification failed: {e}")
        return {
            "verified": True,  # Don't reject on model failure
            "predicted_answer": answer,
            "confidence": 0.5,
            "overlap_score": 50
        }


def check_question_grammar(question: str) -> Dict[str, Any]:
    """
    Basic rule-based grammar checks for question quality.
    Returns dict with 'ok' (bool) and 'issues' (list of strings).
    """
    issues = []
    text = question.strip()

    # Must end with a question mark
    if not text.endswith("?"):
        issues.append("Missing question mark")

    # Must start with a capital letter
    if text and not text[0].isupper():
        issues.append("Doesn't start with capital letter")

    # Must be long enough
    words = text.split()
    if len(words) < 4:
        issues.append("Question too short")

    # Must not contain placeholder tokens
    bad_tokens = ["<hl>", "[MASK]", "[SEP]", "[CLS]", "generate question", "<extra_id"]
    for token in bad_tokens:
        if token in text:
            issues.append(f"Contains model artifact: {token}")

    # Should start with a question word or "Which/Who/What/When/Where/How/Why/Is/Are/Was/Were/Did/Does/Do/Can"
    question_starters = {
        "what", "which", "who", "whom", "whose", "when", "where", "why", "how",
        "is", "are", "was", "were", "did", "does", "do", "can", "could",
        "will", "would", "should", "has", "have", "had"
    }
    first_word = words[0].lower().rstrip("?") if words else ""
    if first_word not in question_starters:
        issues.append(f"Unusual question start: '{words[0]}'")

    return {"ok": len(issues) == 0, "issues": issues}


def is_duplicate(question: str, existing_questions: List[str], threshold: int = 85) -> bool:
    """
    Check if a question is a near-duplicate of any existing question.
    Uses fuzzy token sort ratio for robustness.
    """
    for existing in existing_questions:
        score = fuzz.token_sort_ratio(question.lower(), existing.lower())
        if score >= threshold:
            return True
    return False


def compute_confidence_score(
    qa_confidence: float,
    richness_score: float,
    grammar_ok: bool,
    generation_method: str,
    num_distractors: int
) -> float:
    """
    Compute an overall confidence score for the MCQ (0.0 to 1.0).
    
    Factors:
    - QA model confidence (40%)
    - NLP richness score (25%)
    - Grammar quality (15%)
    - Generation method (10%)
    - Distractor count (10%)
    """
    qa_weight = qa_confidence * 0.40
    richness_weight = min(richness_score / 2.0, 1.0) * 0.25
    grammar_weight = (1.0 if grammar_ok else 0.4) * 0.15
    method_weight = (0.9 if generation_method == "t5" else 0.6) * 0.10
    distractor_weight = (num_distractors / 3.0) * 0.10

    total = qa_weight + richness_weight + grammar_weight + method_weight + distractor_weight
    return round(min(total, 1.0), 3)


def validate_mcqs(
    raw_mcqs: List[Dict[str, Any]],
    confidence_threshold: float = 0.40
) -> List[Dict[str, Any]]:
    """
    Full validation pipeline for a list of raw MCQs.
    
    Args:
        raw_mcqs: List of MCQ dicts from question_generator
        confidence_threshold: Minimum confidence to accept a question

    Returns:
        List of validated, scored MCQ dicts with 'confidence_score' added
    """
    validated = []
    accepted_questions = []

    for mcq in raw_mcqs:
        question = mcq.get("question", "").strip()
        answer = mcq.get("answer", "").strip()
        context = mcq.get("source_sentence", "")
        distractors = mcq.get("distractors", [])

        if not question or not answer:
            logger.debug("Skipping MCQ: missing question or answer")
            continue

        # 1. Grammar check
        grammar_result = check_question_grammar(question)
        if not grammar_result["ok"] and any(
            issue.startswith("Contains model artifact") or
            issue == "Question too short"
            for issue in grammar_result["issues"]
        ):
            logger.debug(f"Grammar rejection: {grammar_result['issues']} | Q: {question}")
            continue

        # 2. Duplicate check
        if is_duplicate(question, accepted_questions):
            logger.debug(f"Duplicate question rejected: {question}")
            continue

        # 3. QA verification
        qa_result = verify_answer(question, answer, context)

        # 4. Compute confidence
        confidence = compute_confidence_score(
            qa_confidence=qa_result["confidence"],
            richness_score=mcq.get("richness_score", 0.5),
            grammar_ok=grammar_result["ok"],
            generation_method=mcq.get("generation_method", "rule_based"),
            num_distractors=len(distractors)
        )

        if confidence < confidence_threshold:
            logger.debug(f"Low confidence ({confidence:.2f}) rejected: {question}")
            continue

        accepted_questions.append(question)

        validated.append({
            **mcq,
            "confidence_score": confidence,
            "grammar_issues": grammar_result["issues"],
            "qa_verified": qa_result["verified"],
            "qa_predicted": qa_result["predicted_answer"],
        })

    logger.info(f"Validation: {len(validated)}/{len(raw_mcqs)} MCQs passed")
    return validated
