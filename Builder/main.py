import re


def parse_file(path):
    with open(path, 'r') as file:
        text = ''
        for line in file.readlines():
            line = line.split('#', 1)[0]
            for sign in ['=', '>', '<']:
                line = line.replace(sign, ' ' + sign + ' ')
            line = line.replace('<  =', '<=').replace('>  =', '>=')
            text += line + '\n'
        tokens = ['{'] + re.split(r'\s+', text)[:-1] + ['}']
        tokens = list(reversed(tokens))
        return parse_object(tokens)


def parse_object(tokens):
    token = tokens.pop()
    if token is not '{':
        return token

    data = {}
    while True:
        key = tokens.pop()
        if key == '}':
            return data
        sign = tokens.pop()
        if sign not in ['=', '>', '<', '>=', '<=']:
            tokens.append(sign)
            value = ''
        else:
            value = parse_object(tokens)
            if type(value) is str:
                value = sign + ' ' + value
        if key not in data.keys():
            data[key] = list()
        data[key].append(value)


def write_data(data, path):
    with open(path, 'w') as file:
        write_object(data, file, 0)


def write_object(data, file, level):
    if type(data) is str:
        if len(data):
            file.write(' ' + data)
        file.write('\n')
        return

    if level > 0:
        file.write(' = {\n')
    for key, values in data.items():
        for value in values:
            for _ in range(level):
                file.write('\t')
            file.write(key)
            write_object(value, file, level + 1)
    if level > 0:
        for _ in range(level - 1):
            file.write('\t')
        file.write('}\n')


if __name__ == '__main__':
    parsed = parse_file(r'in.txt')
    write_data(parsed, r'out.txt')
    print(parsed)
