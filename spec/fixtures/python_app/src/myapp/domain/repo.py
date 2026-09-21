from abc import ABC, abstractmethod


class Repo(ABC):
    @abstractmethod
    def get(self, isbn):
        raise NotImplementedError
