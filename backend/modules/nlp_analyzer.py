"""
nlp_analyzer.py
---------------
spaCy-based NLP analysis: NER, POS tagging, key concept extraction,
and candidate answer identification for question generation.
"""

import logging
import spacy
from typing import List, Dict, Any, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

_nlp = None


def get_nlp():
    global _nlp
    if _nlp is None:
        _nlp = spacy.load("en_core_web_sm")
    return _nlp


# Entity types that make good answer candidates
PRIORITY_ENTITY_TYPES = {
    "PERSON", "ORG", "GPE", "LOC", "DATE", "TIME",
    "NORP", "PRODUCT", "EVENT", "WORK_OF_ART", "LAW",
    "QUANTITY", "PERCENT", "MONEY", "CARDINAL", "ORDINAL"
}


def extract_entities(doc) -> List[Dict[str, str]]:
    """Extract named entities from a spaCy doc."""
    entities = []
    seen = set()
    for ent in doc.ents:
        if ent.label_ in PRIORITY_ENTITY_TYPES and ent.text not in seen:
            entities.append({
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char
            })
            seen.add(ent.text)
    return entities


def extract_noun_chunks(doc) -> List[str]:
    """Extract meaningful noun phrases (chunks) as key concept candidates."""
    chunks = []
    seen = set()
    for chunk in doc.noun_chunks:
        # Filter short or pronoun-only chunks
        text = chunk.text.strip()
        if len(text) > 2 and chunk.root.pos_ != "PRON" and text.lower() not in seen:
            chunks.append(text)
            seen.add(text.lower())
    return chunks


def extract_svo_triples(doc) -> List[Tuple[str, str, str]]:
    """
    Extract Subject-Verb-Object triples for conceptual question generation.
    Returns list of (subject, verb, object) tuples.
    """
    triples = []
    for token in doc:
        if token.dep_ == "ROOT" and token.pos_ == "VERB":
            subjects = [t.text for t in token.children if t.dep_ in ("nsubj", "nsubjpass")]
            objects = [t.text for t in token.children if t.dep_ in ("dobj", "pobj", "attr")]
            if subjects and objects:
                triples.append((subjects[0], token.lemma_, objects[0]))
    return triples


def score_sentence_richness(entities: List, chunks: List, triples: List) -> float:
    """
    Score a sentence based on its informational richness.
    Higher score = better candidate for question generation.
    """
    score = 0.0
    score += min(len(entities) * 0.3, 0.9)   # NEs contribute up to 0.9
    score += min(len(chunks) * 0.1, 0.5)      # Noun chunks up to 0.5
    score += min(len(triples) * 0.2, 0.4)     # SVO triples up to 0.4
    return round(min(score, 2.0), 2)


def analyze_sentences(sentences: List[str]) -> List[Dict[str, Any]]:
    """
    Run full NLP analysis on a list of sentences.
    
    Returns:
        List of analysis dicts, each containing:
        - sentence: original text
        - entities: list of named entities
        - noun_chunks: list of noun phrases
        - svo_triples: list of (S, V, O) tuples
        - richness_score: float
        - best_answer: best candidate answer for QG
    """
    nlp = get_nlp()
    analyzed = []

    for sent_text in sentences:
        doc = nlp(sent_text)
        entities = extract_entities(doc)
        chunks = extract_noun_chunks(doc)
        triples = extract_svo_triples(doc)
        richness = score_sentence_richness(entities, chunks, triples)

        # Identify best answer candidate:
        # Priority: named entity > noun chunk > object from SVO
        best_answer = None
        if entities:
            # Prefer highest-priority entity types
            for ent in entities:
                if ent["label"] in ("PERSON", "ORG", "GPE", "DATE", "EVENT"):
                    best_answer = ent["text"]
                    break
            if not best_answer:
                best_answer = entities[0]["text"]
        elif triples:
            best_answer = triples[0][2]  # object of SVO
        elif chunks:
            best_answer = chunks[0]

        analyzed.append({
            "sentence": sent_text,
            "entities": entities,
            "noun_chunks": chunks,
            "svo_triples": triples,
            "richness_score": richness,
            "best_answer": best_answer
        })

    # Sort by richness descending
    analyzed.sort(key=lambda x: x["richness_score"], reverse=True)
    logger.info(f"NLP analysis complete: {len(analyzed)} sentences analyzed")
    return analyzed


def get_entity_type_map(analyzed_sentences: List[Dict]) -> Dict[str, List[str]]:
    """
    Build a map of entity_type -> [all entity texts found in document].
    Used for distractor generation.
    """
    type_map = defaultdict(set)
    for item in analyzed_sentences:
        for ent in item["entities"]:
            type_map[ent["label"]].add(ent["text"])
    return {k: list(v) for k, v in type_map.items()}
