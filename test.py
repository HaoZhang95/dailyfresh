import random
import string


def generate_random_str():
    """
    生成一个指定长度的随机字符串
    """
    list = []
    for i in range(500):
        # res = (''.join(random.choice(string.ascii_lowercase) for _ in range(3))) + 'cloud.com'
        res = 'music' + (''.join(random.choice(string.ascii_lowercase) for _ in range(2))) + '.com'
        if res not in list:
            list.append(res)

    with open('test.txt', 'w') as f:
        for temp in list:
            f.write(temp + '\n')


def compare():
    with open('test.txt', 'r') as f:
        res = f.read()
        list1 = res.split('\n')

    # for temp in list1:
    #     if list1.count(temp) != 1:
    #         print(temp)
    # print(list1.count('mks.com'))

    with open('test2.txt', 'r') as f:
        res = f.read()
        list2 = res.split('\n')

    print(list1)
    print(list2)
    result = []

    for temp in list1:
        if temp not in list2:
            result.append(temp)

    print(result)
    print(len(result))


if __name__ == '__main__':
    generate_random_str()
    # compare()