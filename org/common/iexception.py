from .ienums import BaseEnum


class IException(Exception):
    def __init__(self, code: int = -1, message: str = '', error: BaseEnum = None):
        if error is not None:
            super().__init__(error.desc)
            self.code = error.code
            self.message = error.desc
        else:
            super().__init__(message)
            self.code = code
            self.message = message
