"""Project-wide constants and paths."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
MODELS_DIR = PROJECT_ROOT / "models"
RESULTS_DIR = PROJECT_ROOT / "results"
DATABASE_PATH = DATA_DIR / "fil_ai.db"
TIMEZONE = "Asia/Riyadh"
INTENTS = ("new_task", "reschedule", "cancellation", "info_only")
INTENT_AR = {
    "new_task": "مهمة جديدة",
    "reschedule": "تغيير موعد",
    "cancellation": "إلغاء",
    "info_only": "معلومة فقط",
}
