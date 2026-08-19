"""
distractor_gen.py
-----------------
Generates high-quality, contextually plausible distractors for MCQs using:
1. Same-entity-type substitution from the document's NE pool
2. WordNet semantic siblings (hypernym-based siblings)
3. spaCy word vectors (cosine similarity)
4. Fallback: plausible random from entity pool
"""

import random
import logging
from typing import List, Dict, Any, Optional

import spacy
import nltk
from nltk.corpus import wordnet as wn

logger = logging.getLogger(__name__)

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


def ensure_nltk_data():
    """Download required NLTK data silently."""
    for resource in ["wordnet", "omw-1.4"]:
        try:
            nltk.data.find(f"corpora/{resource}")
        except LookupError:
            nltk.download(resource, quiet=True)


ensure_nltk_data()


def get_wordnet_siblings(word: str, max_siblings: int = 10) -> List[str]:
    """
    Get semantically related words via WordNet hypernym → sibling paths.
    These are plausible alternatives (same semantic category).
    """
    siblings = set()
    synsets = wn.synsets(word.replace(" ", "_"))

    for synset in synsets[:3]:  # check first 3 senses
        for hypernym in synset.hypernyms():
            for sibling in hypernym.hyponyms():
                for lemma in sibling.lemma_names():
                    text = lemma.replace("_", " ")
                    if text.lower() != word.lower():
                        siblings.add(text)
            if len(siblings) >= max_siblings:
                break

    return list(siblings)[:max_siblings]


def get_vector_similar(word: str, candidates: List[str], top_k: int = 5) -> List[str]:
    """
    Find most similar candidates to `word` using spaCy word vectors.
    Falls back to returning candidates as-is if vectors aren't available.
    """
    nlp = get_nlp()
    try:
        word_doc = nlp(word)
        if not word_doc.has_vector or not word_doc[0].has_vector:
            return candidates[:top_k]

        scored = []
        for cand in candidates:
            cand_doc = nlp(cand)
            if cand_doc.has_vector:
                sim = word_doc.similarity(cand_doc)
                if sim < 0.99:  # exclude near-identical
                    scored.append((cand, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [c for c, _ in scored[:top_k]]
    except Exception as e:
        logger.debug(f"Vector similarity failed for '{word}': {e}")
        return candidates[:top_k]


def get_entity_pool_distractors(
    answer: str,
    entity_type: Optional[str],
    entity_type_map: Dict[str, List[str]],
    max_count: int = 8
) -> List[str]:
    """Get distractors from the same entity type pool found in the document."""
    if not entity_type or entity_type not in entity_type_map:
        # Use any entity pool
        all_entities = []
        for entities in entity_type_map.values():
            all_entities.extend(entities)
        pool = [e for e in all_entities if e.lower() != answer.lower()]
    else:
        pool = [e for e in entity_type_map[entity_type] if e.lower() != answer.lower()]

    random.shuffle(pool)
    return pool[:max_count]


def generate_distractors(
    answer: str,
    entity_type: Optional[str],
    entity_type_map: Dict[str, List[str]],
    source_sentence: str,
    num_distractors: int = 3
) -> List[str]:
    """
    Generate `num_distractors` high-quality distractors for an answer.
    
    Strategy (priority order):
    1. Document entity pool (same type)
    2. WordNet semantic siblings
    3. Vector-similar candidates
    4. Generic fallback labels

    Args:
        answer: The correct answer string
        entity_type: spaCy NER label (e.g., "PERSON", "GPE")
        entity_type_map: Full map from nlp_analyzer.get_entity_type_map()
        source_sentence: Original sentence (for context)
        num_distractors: Number of distractors to produce

    Returns:
        List of `num_distractors` distinct, non-answer strings
    """
    distractor_pool = []

    # 1. Same-entity-type from document
    entity_distractors = get_entity_pool_distractors(
        answer, entity_type, entity_type_map, max_count=12
    )
    distractor_pool.extend(entity_distractors)

    # 2. WordNet siblings
    wordnet_distractors = get_wordnet_siblings(answer, max_siblings=10)
    distractor_pool.extend(wordnet_distractors)

    # 3. Vector similarity ranking of pool
    if distractor_pool:
        distractor_pool = get_vector_similar(answer, distractor_pool, top_k=15)

    # Remove answer from pool (case-insensitive) and deduplicate
    seen = {answer.lower()}
    final = []
    for d in distractor_pool:
        d_clean = d.strip()
        if d_clean.lower() not in seen and len(d_clean) > 1:
            final.append(d_clean)
            seen.add(d_clean.lower())

    # 4. Fallback: generic plausible-sounding options based on entity type
    if len(final) < num_distractors:
        fallbacks = _fallback_distractors(answer, entity_type)
        for fb in fallbacks:
            if fb.lower() not in seen and len(final) < num_distractors:
                final.append(fb)
                seen.add(fb.lower())

    # Final trim and shuffle
    random.shuffle(final)
    return final[:num_distractors]


def _fallback_distractors(answer: str, entity_type: Optional[str]) -> List[str]:
    """Generate generic fallback distractors when all other methods fail."""
    type_fallbacks = {
        "PERSON": ["Alexander the Great", "Marie Curie", "Isaac Newton", "Charles Darwin"],
        "GPE": ["France", "Japan", "Brazil", "Egypt"],
        "ORG": ["United Nations", "World Bank", "NATO", "WHO"],
        "DATE": ["18th century", "1945", "Ancient times", "Medieval period"],
        "LOC": ["North Pole", "Amazon Basin", "Pacific Ocean", "Himalayan range"],
        "QUANTITY": ["100 units", "50 percent", "1000 kilometers", "25 degrees"],
        "PRODUCT": ["Model T", "iPhone", "Penicillin", "Steam engine"],
    }
    defaults = ["None of the above", "All of the above", "Cannot be determined", "Not mentioned"]
    return type_fallbacks.get(entity_type, defaults)
