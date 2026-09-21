import os
from myapp.domain.repo import Repo
from myapp.domain.models import Book


class LoanRepo(Repo):
    def get(self, isbn):
        if isbn:
            return isbn
        return None


def issue(repo, isbn):
    return repo.get(isbn)


def _audit(msg):
    return msg
