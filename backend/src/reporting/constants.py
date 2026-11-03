DEFAULT_WINDOW_DAYS = 30
MIN_WINDOW_DAYS = 1
MAX_WINDOW_DAYS = 730  # ~2 years — generous, but still a bound, so an unbounded window can't force a full-table scan
MAX_REPORT_RANGE_DAYS = 366  # profit-loss takes explicit dates, not a window — one year (incl. leap) is the widest allowed span
