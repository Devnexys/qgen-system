"""
topic_detector.py
-----------------
Zero-shot topic classification using facebook/bart-large-mnli.
Falls back to keyword-based detection for speed/offline use.
"""

import logging
from typing import List, Dict, Optional
import re

logger = logging.getLogger(__name__)

_classifier = None
TOPIC_MODEL = "facebook/bart-large-mnli"

CANDIDATE_TOPICS = [
    "Science", "History", "Technology", "Mathematics",
    "Literature", "Geography", "Politics", "Biology",
    "Physics", "Chemistry", "Economics", "Philosophy", "General Knowledge"
]

# Keyword-based fallback map
KEYWORD_MAP = {
    "Science": ["experiment", "hypothesis", "atom", "molecule", "element", "compound",
                 "theory", "observation", "laboratory", "scientist"],
    "History": ["war", "empire", "king", "queen", "century", "civilization", "ancient",
                 "revolution", "dynasty", "historian", "treaty", "battle"],
    "Technology": ["computer", "software", "internet", "digital", "algorithm", "robot",
                    "artificial intelligence", "machine", "network", "programming"],
    "Mathematics": ["equation", "theorem", "proof", "number", "function", "calculus",
                     "geometry", "algebra", "probability", "statistics"],
    "Literature": ["novel", "poem", "author", "character", "plot", "theme", "metaphor",
                    "Shakespeare", "fiction", "narrative", "prose"],
    "Geography": ["continent", "ocean", "mountain", "river", "country", "capital",
                   "latitude", "longitude", "climate", "ecosystem"],
    "Biology": ["cell", "DNA", "organism", "species", "evolution", "ecosystem",
                  "photosynthesis", "gene", "protein", "chromosome"],
    "Physics": ["force", "energy", "velocity", "mass", "gravity", "quantum",
                  "electron", "proton", "wave", "electromagnetic"],
    "Chemistry": ["reaction", "acid", "base", "compound", "periodic table",
                   "bond", "catalyst", "oxidation", "polymer", "solution"],
    "Economics": ["market", "supply", "demand", "GDP", "inflation", "trade",
                   "currency", "investment", "economy", "fiscal"],
}


def load_classifier():
    """Lazy-load the zero-shot classification pipeline."""
    global _classifier
    if _classifier is None:
        try:
            from transformers import pipeline
            logger.info(f"Loading topic classifier '{TOPIC_MODEL}'...")
            _classifier = pipeline(
                "zero-shot-classification",
                model=TOPIC_MODEL,
                device=-1
            )
            logger.info("Topic classifier loaded")
        except Exception as e:
            logger.warning(f"Could not load topic model: {e}. Using keyword fallback.")
            _classifier = None
    return _classifier


def keyword_detect_topic(text: str) -> str:
    """Keyword-based topic detection as fallback."""
    text_lower = text.lower()
    scores = {}
    for topic, keywords in KEYWORD_MAP.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        scores[topic] = score

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "General Knowledge"


def detect_topic(text: str, use_model: bool = True) -> Dict[str, any]:
    """
    Detect the topic/subject of the text.
    
    Args:
        text: The full input text (or a representative sample)
        use_model: Use BART zero-shot model if True, keyword-based if False

    Returns:
        dict with 'topic' (str) and 'scores' (dict of topic->score)
    """
    # Use first 1000 chars as representative sample
    sample = text[:1000]

    if use_model:
        classifier = load_classifier()
        if classifier is not None:
            try:
                result = classifier(sample, CANDIDATE_TOPICS, multi_label=False)
                scores = dict(zip(result["labels"], result["scores"]))
                return {
                    "topic": result["labels"][0],
                    "scores": {k: round(v, 3) for k, v in scores.items()}
                }
            except Exception as e:
                logger.warning(f"Zero-shot classification failed: {e}")

    # Fallback to keyword-based
    topic = keyword_detect_topic(text)
    return {"topic": topic, "scores": {topic: 1.0}}


def generate_explanation(mcq: Dict) -> str:
    """
    Generate a human-readable explanation for the correct answer.
    Uses the source sentence as the primary evidence.
    
    Args:
        mcq: MCQ dict with 'answer', 'source_sentence', 'question'

    Returns:
        Explanation string
    """
    answer = mcq.get("answer", "")
    source = mcq.get("source_sentence", "")
    entity_type = mcq.get("entity_type", "")

    if not source:
        return f'The correct answer is "{answer}".'

    # Find where the answer appears in the source
    if answer.lower() in source.lower():
        explanation = (
            f'The correct answer is "{answer}". '
            f'This is supported by the following passage: "{source}"'
        )
    else:
        explanation = (
            f'The correct answer is "{answer}". '
            f'Based on the content: "{source}"'
        )

    return explanation
