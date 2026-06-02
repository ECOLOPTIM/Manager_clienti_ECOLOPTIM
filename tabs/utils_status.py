def format_status(status: str) -> str:
    s = str(status or "").upper().strip()

    if s == "CONTRACTAT":
        return "🟣 CONTRACTAT"
    if s == "PROGRAMAT":
        return "🔵 PROGRAMAT"
    if s == "EXECUTAT":
        return "🟢 EXECUTAT"
    if s == "FINALIZAT":
        return "✅ FINALIZAT"
    if s in ("ÎNCHIS", "INCHIS"):
        return "⚫ ÎNCHIS"
    return "🟡 OFERTAT"