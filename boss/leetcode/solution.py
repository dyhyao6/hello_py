from functools import reduce

if __name__=="""__main__""":
    nums = [1,2,3,4,5]
    res = reduce(lambda x,y:x * y ,nums)
    print(res)