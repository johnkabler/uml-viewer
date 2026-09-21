import os
from typing import Protocol

from myapp.app.loan import LoanRepo


class Book(Protocol):
    def title(self) -> str:
        ...


def _hidden():
    return 1


def title_of(book):
    if book:
        return book.title()
    return ""
