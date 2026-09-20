def parse_float(text: str) -> float:
    """Return a float from a string."""

    text = text.strip().replace(',', '.')

    try:
        return float(text)
    except ValueError:
        pass

    if text.casefold() == 'infinity':
        return float('inf')

    return 0
