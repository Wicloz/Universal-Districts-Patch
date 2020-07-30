import shlex
import tempfile
import zipfile
import glob


class StellarisDict(dict):
    def ensure(self, data):
        for key, values in data.items():
            if key not in self:
                self[key] = []
            for value in values:
                if type(value) is str:
                    self[key].append(value)
                else:
                    self[key].append(StellarisDict().ensure(value))
        return self

    def has_single(self, key):
        return key in self and len(self[key]) == 1

    def get_single(self, key):
        if key in self:
            assert len(self[key]) == 1
            return self[key][0]
        else:
            return StellarisDict()

    def get_list(self, key):
        if key not in self:
            return []
        else:
            return self[key]

    def copy_without(self, key):
        copy = StellarisDict(self.copy())
        if key in copy:
            del copy[key]
        return copy

    def get_values(self):
        for values in self.values():
            for value in values:
                if isinstance(value, StellarisDict):
                    yield from value.get_values()
                else:
                    yield value

    def get_keys(self):
        for key in self.keys():
            yield key
        for values in self.values():
            for value in values:
                if isinstance(value, StellarisDict):
                    yield from value.get_keys()


def parse_file(path):
    with open(path, 'r') as file:
        text = ''
        for line in file.readlines():
            line = line.split('#', 1)[0]
            for sign in ['=', '>', '<', '{', '}']:
                line = line.replace(sign, ' ' + sign + ' ')
            line = line.replace('<  =', '<=').replace('>  =', '>=')
            text += line + '\n'
        tokens = ['{'] + [item for item in shlex.split(text) if len(item.strip()) > 0] + ['}']
        tokens = list(reversed(tokens))
        return parse_object(tokens, {})


def parse_object(tokens, variables):
    token = tokens.pop()
    if token is not '{':
        return token

    data = StellarisDict()
    while True:
        key = tokens.pop()
        if key.upper() in ['IF', 'AND', 'OR', 'NOT', 'NOR', 'NAND']:
            key = key.upper()
        if key == '}':
            return data
        sign = tokens.pop()
        if sign not in ['=', '>', '<', '>=', '<=']:
            tokens.append(sign)
            value = None
        else:
            value = parse_object(tokens, variables.copy())
            if type(value) is str and not key.startswith('@'):
                if value in variables:
                    value = variables[value]
                value = sign + ' ' + value
        if (key == 'OR' or key == 'AND') and len(value.keys()) == 1 and len(value[list(value.keys())[0]]) <= 1:
            key = list(value.keys())[0]
            value = value[key][0] if len(value[key]) == 1 else None
        if key.startswith('@'):
            variables[key] = value
        else:
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


def extract_mod(workshop_folder, mod_id):
    folder = tempfile.TemporaryDirectory().name
    with zipfile.ZipFile(glob.glob(workshop_folder + '/' + mod_id + '/*.zip')[0], 'r') as mod:
        mod.extractall(folder)
    return folder
