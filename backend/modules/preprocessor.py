"""
preprocessor.py
---------------
Intelligent text preprocessing: noise removal, sentence filtering,
and extraction of only factual declarative sentences suitable for QG.
"""

import re
import logging
import spacy
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Load spaCy model (lazy-loaded)
_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        try:
            _nlp = spacy.load("en_core_web_sm")
            logger.info("spaCy model loaded successfully")
        except OSError:
            raise RuntimeError(
                "spaCy model 'en_core_web_sm' not found. "
                "Run: python -m spacy download en_core_web_sm"
            )
    return _nlp


# Patterns to identify and remove noise
NOISE_PATTERNS = [
    r"^\s*page\s+\d+\s*$",           # page numbers
    r"^\s*\d+\s*$",                   # standalone numbers
    r"^\s*[-–—]+\s*$",               # separator lines
    r"www\.\S+",                      # URLs
    r"http[s]?://\S+",               # URLs
    r"\S+@\S+\.\S+",                 # email addresses
    r"^\s*copyright.*$",             # copyright lines
    r"^\s*all rights reserved.*$",   # legal disclaimers
    r"^\s*table of contents.*$",     # TOC headers
    r"^\s*figure\s+\d+.*$",         # figure captions
    r"^\s*table\s+\d+.*$",          # table captions
]

# Imperative/instruction verbs that signal non-factual sentences
INSTRUCTION_STARTERS = {
    "note", "notice", "remember", "consider", "think", "look", "see",
    "refer", "check", "ensure", "make", "find", "calculate", "solve",
    "write", "read", "describe", "explain", "discuss", "list", "identify",
    "define", "compare", "analyze", "evaluate", "apply", "draw", "match",
    "fill", "complete", "answer", "choose", "select", "state", "mention",
    "give", "provide", "show", "demonstrate", "prove", "derive",
}


def clean_text(text: str) -> str:
    """Remove obvious noise patterns from raw text."""
    lines = text.split("\n")
    cleaned = []
    for line in lines:
        # Remove lines matching noise patterns
        skip = False
        for pattern in NOISE_PATTERNS:
            if re.search(pattern, line, re.IGNORECASE):
                skip = True
                break
        if not skip and line.strip():
            cleaned.append(line.strip())
    return " ".join(cleaned)


def is_declarative_factual(sent) -> Tuple[bool, str]:
    """
    Check if a spaCy sentence is a factual declarative sentence.
    
    Returns:
        (bool, reason) - True if suitable for QG, False with reason if not
    """
    text = sent.text.strip()

    # Too short or too long
    words = [t for t in sent if not t.is_space and not t.is_punct]
    if len(words) < 6:
        return False, "too short"
    if len(words) > 80:
        return False, "too long"

    # Questions (ends with ?) — not suitable
    if text.endswith("?"):
        return False, "interrogative"

    # Commands/imperatives — check first token
    first_token = next((t for t in sent if not t.is_space and not t.is_punct), None)
    if first_token:
        if first_token.tag_ == "VB" and first_token.lemma_.lower() in INSTRUCTION_STARTERS:
            return False, "imperative/instruction"
        if first_token.lower_ in INSTRUCTION_STARTERS and first_token.tag_ in ("VB", "VBP"):
            return False, "imperative/instruction"

    # Incomplete sentences (no root verb)
    has_root_verb = any(t.dep_ == "ROOT" and t.pos_ == "VERB" for t in sent)
    if not has_root_verb:
        return False, "no root verb"

    # Has a subject
    has_subject = any(t.dep_ in ("nsubj", "nsubjpass", "csubj") for t in sent)
    if not has_subject:
        return False, "no subject"

    # Avoid sentences that are mostly numbers/bullets
    alpha_words = [t for t in words if t.is_alpha]
    if len(alpha_words) < 4:
        return False, "insufficient alpha tokens"

    return True, "ok"


def segment_and_filter_sentences(text: str) -> List[str]:
    """
    Use spaCy to segment text into sentences and filter for factual declaratives.
    
    Returns:
        List of valid sentence strings
    """
    nlp = get_nlp()
    # Process in chunks to avoid memory issues with very long text
    max_chars = 100_000
    all_valid = []

    chunks = [text[i:i + max_chars] for i in range(0, len(text), max_chars)]
    for chunk in chunks:
        doc = nlp(chunk)
        for sent in doc.sents:
            is_valid, reason = is_declarative_factual(sent)
            if is_valid:
                all_valid.append(sent.text.strip())
            else:
                logger.debug(f"Filtered sentence ({reason}): {sent.text[:60]}...")

    logger.info(f"Sentence filtering: {len(all_valid)} valid sentences retained")
    return all_valid


def preprocess(raw_text: str) -> List[str]:
    """
    Full preprocessing pipeline.
    
    Args:
        raw_text: Raw input text from any source

    Returns:
        List of clean, factual, declarative sentences ready for QG
    """
    if not raw_text or not raw_text.strip():
        raise ValueError("Input text is empty")

    logger.info(f"Starting preprocessing: {len(raw_text)} characters")
    cleaned = clean_text(raw_text)
    sentences = segment_and_filter_sentences(cleaned)

    if not sentences:
        raise ValueError("No valid sentences found after preprocessing. "
                         "Ensure the text contains factual, declarative content.")

    return sentences
