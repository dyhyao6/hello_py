

def args_kwargs(*args, **kwargs):
    print(args)
    print(kwargs)


if __name__=='__main__':
    # l = [x * x for x in range(10)]
    # print(l)
    # g = (x * x for x in range(10))
    # print(g)

    args_kwargs(1, 2, 3, name='bob', age=25)




    def data_reader(data):
        for item in data:
            print(f"Read: {item}")
            yield item


    def data_filter(gen):
        for item in gen:
            if item > 15:
                print(f"Filter: {item}")
                yield item * 2


    def data_sink(gen):
        result = []
        for item in gen:
            result.append(item)
        return result


    pipeline = data_sink(data_filter(data_reader([10, 20, 30])))
    print(pipeline)