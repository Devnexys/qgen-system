"""
difficulty.py
-------------
Classifies questions into difficulty levels based on:
- Question type (recall vs. application)
- Answer complexity
- Source sentence complexity (Flesch-Kincaid proxy)
"""

import re
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)


def syllable_count(word: str) -> int:
    """Simple syllable counter (approximation)."""
    word = word.lower().strip(".,;:")
    word = re.sub(r"[^a-z]", "", word)
    if not word:
        return 0
    count = len(re.findall(r"[aeiou]+", word))
    if word.endswith("e") and count > 1:
        count -= 1
    return max(1, count)


def flesch_kincaid_grade(text: str) -> float:
    """Approximate Flesch-Kincaid Grade Level for a sentence."""
    words = text.split()
    sentences = max(len(re.findall(r"[.!?]+", text)), 1)
    num_words = max(len(words), 1)
    num_syllables = sum(syllable_count(w) for w in words)

    # FK Grade: 0.39 * (words/sentences) + 11.8 * (syllables/words) - 15.59
    grade = 0.39 * (num_words / sentences) + 11.8 * (num_syllables / num_words) - 15.59
    return round(max(0.0, grade), 2)


# Question words that signal simpler recall questions
RECALL_WORDS = {"who", "what", "when", "where", "which"}
APPLICATION_WORDS = {"how", "why", "explain", "describe", "compare", "analyze"}


def classify_difficulty(mcq: Dict[str, Any], requested_difficulty: str = "medium") -> str:
    """
    Determine the effective difficulty level of an MCQ.
    
    Logic:
    - If user requested a difficulty, bias toward it
    - Easy: simple recall (who/what/where), short answer, low FK grade
    - Medium: some relationship understanding needed
    - Hard: multi-concept, high FK grade, application-style question
    
    Returns:
        'easy' | 'medium' | 'hard'
    """
    question = mcq.get("question", "").lower()
    source = mcq.get("source_sentence", "")
    fk_grade = flesch_kincaid_grade(source)

    # Base classification from question type
    first_word = question.strip().split()[0] if question.strip() else ""

    if first_word in RECALL_WORDS and fk_grade < 8:
        detected = "easy"
    elif first_word in APPLICATION_WORDS or fk_grade > 12:
        detected = "hard"
    else:
        detected = "medium"

    # Blend with requested difficulty
    if requested_difficulty == "easy":
        return "easy" if detected in ("easy", "medium") else "medium"
    elif requested_difficulty == "hard":
        return "hard" if detected in ("hard", "medium") else "medium"
    else:
        return detected


def filter_by_difficulty(
    mcqs: list,
    requested_difficulty: str,
    num_questions: int
) -> list:
    """
    Filter and sort MCQs to match the requested difficulty.
    If not enough of the exact difficulty exist, fills with closest.
    """
    # Classify each
    for mcq in mcqs:
        mcq["difficulty"] = classify_difficulty(mcq, requested_difficulty)

    # Sort: exact match first, then by confidence
    exact = [m for m in mcqs if m["difficulty"] == requested_difficulty]
    others = [m for m in mcqs if m["difficulty"] != requested_difficulty]

    combined = (
        sorted(exact, key=lambda x: x.get("confidence_score", 0), reverse=True) +
        sorted(others, key=lambda x: x.get("confidence_score", 0), reverse=True)
    )

    return combined[:num_questions]
