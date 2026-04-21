"""Pass 2 — binary classifier (PRD §8.1). distilBERT fine-tune or keyword fallback."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..settings import SignalSettings, get_settings

if TYPE_CHECKING:
    pass

_PROBLEM_HINTS = re.compile(
    r"\b("
    r"is there a tool|i wish|looking for|how do you|anyone know|"
    r"workaround|painful|broken|struggling|waste.*time|costs?\s*(us|\$)|"
    r"spreadsheet|manual|fax|prior auth|scheduling|ehr|emr|workflow"
    r")\b",
    re.I,
)


@dataclass
class ClassifierResult:
    is_problem_signal: bool
    confidence: float


class ProblemSignalClassifier:
    """Fine-tuned distilBERT when SIGNAL_CLASSIFIER_MODEL_PATH is set; else keyword heuristic."""

    def __init__(self, settings: SignalSettings | None = None) -> None:
        self.settings = settings or get_settings()
        self._pipeline = None
        path = self.settings.classifier_model_path
        if path:
            p = Path(path).expanduser()
            if p.is_dir():
                try:
                    from transformers import pipeline  # type: ignore[import-untyped]

                    self._pipeline = pipeline(
                        "text-classification",
                        model=str(p),
                        tokenizer=str(p),
                        truncation=True,
                        max_length=512,
                        device=-1,
                    )
                except Exception:
                    self._pipeline = None

    def predict(self, text: str) -> ClassifierResult:
        if self._pipeline is not None:
            try:
                out = self._pipeline(text[:2000])[0]
                label = str(out.get("label", "")).upper()
                score = float(out.get("score", 0.5))
                # Expect LABEL_1 / POSITIVE / PROBLEM = True
                positive = any(
                    x in label for x in ("LABEL_1", "POSITIVE", "PROBLEM", "TRUE", "1")
                ) or (label.startswith("LABEL") and "0" not in label and "NOT" not in label)
                if "NEG" in label or "LABEL_0" in label or "NOT" in label:
                    positive = False
                return ClassifierResult(is_problem_signal=positive, confidence=score)
            except Exception:
                pass

        # Keyword fallback (better than unconditional True for evals)
        t = text.strip()
        if len(t) < 25:
            return ClassifierResult(is_problem_signal=False, confidence=0.9)
        if _PROBLEM_HINTS.search(t):
            return ClassifierResult(is_problem_signal=True, confidence=0.72)
        return ClassifierResult(is_problem_signal=False, confidence=0.65)
