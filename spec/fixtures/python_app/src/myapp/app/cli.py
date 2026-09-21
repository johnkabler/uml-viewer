import importlib

from ..domain.models import Book
from .loan import issue


def main():
    importlib.import_module("myapp.domain.repo")
    return issue(None, "1")
