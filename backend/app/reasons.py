"""Reason codes and Persian labels. The labels match index.html / Code.gs exactly."""

REASONS: dict[str, dict[str, str]] = {
    "lucky": {"label": "شانسی", "status": "correct"},
    "long_solution": {"label": "راه حل طولانی", "status": "correct"},
    "careless": {"label": "بی‌دقتی", "status": "wrong"},
    "knowledge_gap": {"label": "مشکل علمی", "status": "wrong"},
    "budget": {"label": "نرسیدن به بودجه‌بندی", "status": "blank"},
    "time": {"label": "کم آوردن زمان", "status": "blank"},
    "unsolved": {"label": "نتوانستم حل کنم", "status": "blank"},
}

NOTE_LABELS: dict[str, str] = {
    "from_scratch": "نیازمند مطالعه از صفر",
    "more_practice": "نیازمند تست بیشتر",
    "review": "نیازمند مرور",
}