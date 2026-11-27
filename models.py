"""Клас Movie: один фільм зі списку.

Усередині програми фільм — це об'єкт Movie, а не словник.
Словники лишаються лише на межах: JSON (to_dict) і база даних (from_row).
"""


class Movie:
    """Один фільм: назва, рік, статус, оцінка і дата."""

    def __init__(self, title, year, status, rating=0, date="", movie_id=None):
        self.id = movie_id
        self.title = title
        self.year = int(year)        # тут, і тільки тут, рядок стає числом
        self.status = status
        self.rating = int(rating)    # 0 = ще не оцінено
        self.date = date

    def to_dict(self):
        """Для jsonify і для відповіді API."""
        return {"id": self.id, "title": self.title, "year": self.year,
                "status": self.status, "rating": self.rating, "date": self.date}

    @staticmethod
    def from_row(row):
        """З рядка бази (sqlite3.Row) в об'єкт Movie."""
        return Movie(row["title"], row["year"], row["status"],
                     row["rating"], row["date"], row["id"])

    def is_rated(self):
        """Чи має фільм оцінку (0 означає «ще не оцінено»)."""
        return self.rating > 0

    def __repr__(self):
        """Як фільм виглядає при print() і в повідомленнях pytest."""
        return f"Movie({self.title!r}, {self.year}, {self.status!r}, rating={self.rating})"
