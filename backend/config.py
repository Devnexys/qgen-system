import os

# Model Configurations
QG_MODEL_NAME = "valhalla/t5-base-qg-hl"
QA_MODEL_NAME = "deepset/roberta-base-squad2"
TOPIC_MODEL_NAME = "facebook/bart-large-mnli"
SPACY_MODEL = "en_core_web_sm"

# Generation Settings
DEFAULT_NUM_QUESTIONS = 5
MAX_CONTEXT_LENGTH = 512
SCORE_THRESHOLD = 0.6

# File Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
SAMPLE_DATA_DIR = os.path.join(BASE_DIR, "sample_data")

# Create directories if they don't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(SAMPLE_DATA_DIR, exist_ok=True)
