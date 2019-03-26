import re


########
# VARS #
########

stellaris_folder = r'D:\Game Libraries\Windows - Steam\steamapps\common\Stellaris'
workshop_folder = r'D:\Game Libraries\Windows - Steam\steamapps\workshop\content\281990'

gai_mod_id = '1584133829'

district_files = [
    '/common/districts/00_urban_districts.txt',
    '/common/districts/01_arcology_districts.txt',
    '/common/districts/02_rural_districts.txt',
    '/common/districts/03_habitat_districts.txt',
]

########
# VARS #
########


class StellarisDict(dict):
    def ensure(self, data):
        for key, values in data.items():
            if key not in self:
                self[key] = []
            for value in values:
                self[key].append(value)

    def safe_get(self, key, always_list=False):
        if key not in self:
            return []
        elif not always_list and len(self[key]) == 1:
            return self[key][0]
        else:
            return self[key]


def parse_file(path):
    with open(path, 'r') as file:
        text = ''
        for line in file.readlines():
            line = line.split('#', 1)[0]
            for sign in ['=', '>', '<', '{', '}']:
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

    data = StellarisDict()
    while True:
        key = tokens.pop()
        if key == '}':
            return data
        sign = tokens.pop()
        if sign not in ['=', '>', '<', '>=', '<=']:
            tokens.append(sign)
            value = None
        else:
            value = parse_object(tokens)
            if type(value) is str:
                value = sign + ' ' + value
        if key not in data.keys():
            data[key] = list()
        if value is not None:
            data[key].append(value)


def write_data(data, path):
    with open(path, 'w') as file:
        write_object(data, file, 0)


def write_object(data, file, level):
    if type(data) is str:
        file.write(' ' + data + '\n')
        return

    if level > 0:
        file.write(' = {\n')
    for key, values in data.items():
        if len(values) == 0:
            write_tabs(level, file)
            file.write(key + '\n')
        for value in values:
            write_tabs(level, file)
            file.write(key)
            write_object(value, file, level + 1)
    if level > 0:
        write_tabs(level - 1, file)
        file.write('}\n')


def write_tabs(count, file):
    for _ in range(count):
        file.write('\t')


if __name__ == '__main__':
    parsed = parse_file(r'in.txt')
    write_data(parsed, r'out.txt')
    print(parsed)
