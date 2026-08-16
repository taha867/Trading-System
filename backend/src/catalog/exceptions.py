from src.exceptions import NotFoundException


class ItemNotFound(NotFoundException):
    detail = "Item not found"
