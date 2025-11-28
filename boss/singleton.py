

class Singleton():
    def __new__(self, cls, *args, **kwargs):
        if not hasattr(cls,'_instance'):
            cls._instance = super(Singleton,cls).__new__(cls,*args,**kwargs)
        return cls._instance

class A(Singleton):
    a = 1

if __name__ == '__main__':
    print(A.a)
