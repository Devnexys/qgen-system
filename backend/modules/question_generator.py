"""
question_generator.py
---------------------
T5-based question generation using highlight-based prompting.
Falls back to rule-based templates for simple factual questions.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from transformers import T5ForConditionalGeneration, T5Tokenizer
import torch

logger = logging.getLogger(__name__)

# Lazy-loaded model globals
_qg_model = None
_qg_tokenizer = None

QG_MODEL_NAME = "valhalla/t5-base-qg-hl"
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def load_qg_model():
    """Load T5 QG model (lazy loading to avoid startup delay)."""
    global _qg_model, _qg_tokenizer
    if _qg_model is None:
        logger.info(f"Loading QG model '{QG_MODEL_NAME}' on {DEVICE}...")
        _qg_tokenizer = T5Tokenizer.from_pretrained(QG_MODEL_NAME)
        _qg_model = T5ForConditionalGeneration.from_pretrained(QG_MODEL_NAME)
        _qg_model.to(DEVICE)
        _qg_model.eval()
        logger.info("QG model loaded successfully")
    return _qg_model, _qg_tokenizer


def generate_question_t5(sentence: str, answer: str) -> Optional[str]:
    """
    Generate a question using T5 with highlight-based prompting.
    The answer span is highlighted using <hl> tokens.
    
    Args:
        sentence: Source sentence
        answer: The answer span to generate a question for

    Returns:
        Generated question string or None if generation fails
    """
    model, tokenizer = load_qg_model()

    # Highlight the answer in the sentence
    if answer.lower() in sentence.lower():
        # Case-insensitive replacement preserving original casing
        pattern = re.compile(re.escape(answer), re.IGNORECASE)
        highlighted = pattern.sub(f"<hl> {answer} <hl>", sentence, count=1)
    else:
        highlighted = f"<hl> {answer} <hl> {sentence}"

    input_text = f"generate question: {highlighted}"

    try:
        inputs = tokenizer(
            input_text,
            return_tensors="pt",
            max_length=512,
            truncation=True,
            padding="max_length"
        ).to(DEVICE)

        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=64,
                num_beams=4,
                no_repeat_ngram_size=2,
                early_stopping=True
            )

        question = tokenizer.decode(outputs[0], skip_special_tokens=True)

        # Validate generated question
        if not question or not question.strip().endswith("?"):
            question = question.strip()
            if question and not question.endswith("?"):
                question += "?"

        logger.debug(f"Generated: {question}")
        return question.strip() if question else None

    except Exception as e:
        logger.warning(f"T5 generation failed for answer '{answer}': {e}")
        return None


# ── Rule-based fallback templates ──────────────────────────────────────────────

ENTITY_QUESTION_TEMPLATES = {
    "PERSON": [
        "Who is {answer}?",
        "Who was {answer}?",
        "Who is referred to as {answer}?",
    ],
    "ORG": [
        "What is {answer}?",
        "Which organization is known as {answer}?",
    ],
    "GPE": [
        "Where is {answer} located?",
        "Which country/region is referred to as {answer}?",
    ],
    "LOC": [
        "Where is {answer}?",
        "Which location is referred to as {answer}?",
    ],
    "DATE": [
        "When did this event related to {answer} occur?",
        "What is significant about {answer}?",
    ],
    "EVENT": [
        "What is {answer}?",
        "When did {answer} occur?",
    ],
    "PRODUCT": [
        "What is {answer}?",
        "Which product is referred to as {answer}?",
    ],
    "QUANTITY": [
        "How much/many is {answer}?",
        "What quantity is referred to as {answer}?",
    ],
}

DEFAULT_TEMPLATES = [
    "What is {answer}?",
    "Which of the following best describes {answer}?",
    "What does {answer} refer to in this context?",
]


def generate_question_rule_based(answer: str, entity_type: str = None) -> str:
    """Generate a question using rule-based templates as fallback."""
    import random
    templates = ENTITY_QUESTION_TEMPLATES.get(entity_type, DEFAULT_TEMPLATES)
    template = random.choice(templates)
    return template.format(answer=answer)


def generate_questions_for_sentences(
    analyzed_sentences: List[Dict[str, Any]],
    num_questions: int = 5,
    difficulty: str = "medium",
    use_t5: bool = True
) -> List[Dict[str, Any]]:
    """
    Generate questions for a ranked list of analyzed sentences.
    
    Args:
        analyzed_sentences: Output from nlp_analyzer.analyze_sentences()
        num_questions: Target number of questions
        difficulty: 'easy' | 'medium' | 'hard'
        use_t5: Whether to use T5 model (False = rule-based only)

    Returns:
        List of question dicts with keys:
        - question, answer, source_sentence, entity_type,
          generation_method, difficulty
    """
    # Adjust how many sentences to try based on target (try 2x to account for failures)
    candidates = analyzed_sentences[:num_questions * 3]
    results = []

    for item in candidates:
        if len(results) >= num_questions:
            break

        sentence = item["sentence"]
        answer = item.get("best_answer")
        if not answer:
            continue

        # Get entity type if available
        entity_type = None
        for ent in item.get("entities", []):
            if ent["text"] == answer:
                entity_type = ent["label"]
                break

        # Try T5 first, fall back to rule-based
        question = None
        method = "rule_based"

        if use_t5:
            question = generate_question_t5(sentence, answer)
            if question:
                method = "t5"

        if not question:
            question = generate_question_rule_based(answer, entity_type)
            method = "rule_based"

        if question:
            results.append({
                "question": question,
                "answer": answer,
                "source_sentence": sentence,
                "entity_type": entity_type,
                "generation_method": method,
                "difficulty": difficulty,
                "richness_score": item.get("richness_score", 0.0)
            })

    logger.info(f"Generated {len(results)} raw questions")
    return results
