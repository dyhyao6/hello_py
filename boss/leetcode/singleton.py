from functools import reduce


class Singleton(object):
    def __new__(cls, *args, **kw):
        if not hasattr(cls, '_instance'):
            orig = super(Singleton, cls)
            cls._instance = orig.__new__(cls, *args, **kw)
        return cls._instance


if __name__ == """__main__""":
    nums = [1, 2, 3, 4, 5]
    res = reduce(lambda x, y: x * y, nums)
    print(res)
