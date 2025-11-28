def talk():
    # You can define a function on the fly in "talk" ...
    def whisper(word="yes"):
        return word.lower() + "..."

    # ... and use it right away!
    print(whisper())


def getTalk(kind="shout"):
    # We define functions on the fly
    def shout(word="yes"):
        return word.capitalize() + "!"

    def whisper(word="yes"):
        return word.lower() + "..."

    # Then we return one of them
    if kind == "shout":
        # We don't use "()", we are not calling the function,
        # we are returning the function object
        return shout
    else:
        return whisper


# Source - https://stackoverflow.com/a
# Posted by Bite code, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-07, License - CC BY-SA 4.0

# A decorator is a function that expects ANOTHER function as parameter
def my_shiny_new_decorator(a_function_to_decorate):
    # Inside, the decorator defines a function on the fly: the wrapper.
    # This function is going to be wrapped around the original function
    # so it can execute code before and after it.
    def the_wrapper_around_the_original_function():
        # Put here the code you want to be executed BEFORE the original function is called
        print("Before the function runs")

        # Call the function here (using parentheses)
        a_function_to_decorate()

        # Put here the code you want to be executed AFTER the original function is called
        print("After the function runs")

    # At this point, "a_function_to_decorate" HAS NEVER BEEN EXECUTED.
    # We return the wrapper function we have just created.
    # The wrapper contains the function and the code to execute before and after. It’s ready to use!
    return the_wrapper_around_the_original_function


# Now imagine you create a function you don't want to ever touch again.
def a_stand_alone_function():
    print("I am a stand alone function, don't you dare modify me")


@my_shiny_new_decorator
def another_stand_alone_function():
    print("Leave me alone")


def bread(func):
    def wrapper():
        print("<''''''>")
        func()
        print("<______>")

    return wrapper


def ingredients(func):
    def wrapper():
        print("#tomatoes#")
        func()
        print("~salad~")

    return wrapper


@bread
@ingredients
def sandwich(food="--ham--"):
    print(food)


# Taking decorators to the next level
# Source - https://stackoverflow.com/a
# Posted by Bite code, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-10, License - CC BY-SA 4.0

def method_friendly_decorator(method_to_decorate):
    def wrapper(self, lie):
        lie -= 3  # very friendly, decrease age even more :-)
        return method_to_decorate(self, lie)

    return wrapper


class Lucy(object):

    def __init__(self):
        self.age = 32

    @method_friendly_decorator
    def sayYourAge(self, lie):
        print("I am {0}, what did you think?".format(self.age + lie))


# Decorators are ORDINARY functions
def my_decorator(func):
    print("I am an ordinary function")

    def wrapper():
        print("I am function returned by the decorator")
        func()

    return wrapper


# Therefore, you can call it without any "@"

@my_decorator
def lazy_function():
    print("zzzzzzzz")


# Source - https://stackoverflow.com/a
# Posted by Bite code, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-10, License - CC BY-SA 4.0

def decorator_maker():
    print("I make decorators! I am executed only once: "
          "when you make me create a decorator.")

    def my_decorator(func):
        print("I am a decorator! I am executed only when you decorate a function.")

        def wrapped():
            print("I am the wrapper around the decorated function. "
                  "I am called when you call the decorated function. "
                  "As the wrapper, I return the RESULT of the decorated function.")
            return func()

        print("As the decorator, I return the wrapped function.")

        return wrapped

    print("As a decorator maker, I return a decorator")
    return my_decorator


@decorator_maker()
def decorated_function():
    print("I am the decorated function.")


# Source - https://stackoverflow.com/a
# Posted by Bite code, modified by community. See post 'Timeline' for change history
# Retrieved 2025-11-10, License - CC BY-SA 4.0

def benchmark(func):
    """
    A decorator that prints the time a function takes
    to execute.
    """
    import time
    def wrapper(*args, **kwargs):
        t = time.perf_counter()
        res = func(*args, **kwargs)
        print("{0} {1}".format(func.__name__, time.perf_counter() - t))
        return res

    return wrapper


def logging(func):
    """
    A decorator that logs the activity of the script.
    (it actually just prints it, but it could be logging!)
    """

    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        print("{0} {1} {2}".format(func.__name__, args, kwargs))
        return res

    return wrapper


def counter(func):
    """
    A decorator that counts and prints the number of times a function has been executed
    """

    def wrapper(*args, **kwargs):
        wrapper.count = wrapper.count + 1
        res = func(*args, **kwargs)
        print("{0} has been used: {1}x".format(func.__name__, wrapper.count))
        return res

    wrapper.count = 0
    return wrapper


@counter
@benchmark
@logging
def reverse_string(string):
    return str(reversed(string))


if __name__ == '__main__':
    # talk()
    # talk = getTalk()
    # print(talk)
    # print(talk())
    # print(getTalk(kind="whisper")())

    # a_stand_alone_function()

    # a_stand_alone_function_decorated = my_shiny_new_decorator(a_stand_alone_function)
    # a_stand_alone_function_decorated()

    # another_stand_alone_function()

    # sandwich = bread(ingredients(sandwich))

    # sandwich()

    # l = Lucy()
    # l.sayYourAge(-3)
    # outputs: I am 26, what did you think?

    # lazy_function()
    # decorated_function()
    print(reverse_string("Able was I ere I saw Elba"))
    print(reverse_string(
        "A man, a plan, a canoe, pasta, heros, rajahs, a coloratura, maps, snipe, percale, macaroni, a gag, a banana bag, a tan, a tag, a banana bag again (or a camel), a crepe, pins, Spam, a rut, a Rolo, cash, a jar, sore hats, a peon, a canal: Panama!"))
