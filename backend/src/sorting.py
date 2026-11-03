from typing import Literal

# The one sort choice the list screens offer: by date, either way. A shared type so the sales and
# purchasing list endpoints (and their "Other entries" lists) accept exactly the same values.
SortDirection = Literal["newest", "oldest"]


def date_ordering(date_column, id_column, sort: SortDirection):
    """ORDER BY terms for a date-sorted list. `id` breaks ties so rows on the same date keep a stable,
    predictable order (and paging never repeats or skips a row)."""
    if sort == "oldest":
        return (date_column.asc(), id_column.asc())
    return (date_column.desc(), id_column.desc())
