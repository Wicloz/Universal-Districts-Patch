import re
import tempfile
import zipfile
import glob
import os
import shutil


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


def extract_mod(mod_id):
    folder = tempfile.TemporaryDirectory().name
    with zipfile.ZipFile(glob.glob(workshop_folder + '/' + mod_id + '/*.zip')[0], 'r') as mod:
        mod.extractall(folder)
    return folder


if __name__ == '__main__':
    ########################
    # load stellaris files #
    ########################

    stellaris_files = [parse_file(stellaris_folder + '/' + file) for file in district_files]

    #############################
    # merge ai weights from gai #
    #############################

    gai_folder = extract_mod(gai_mod_id)
    gai_files = [parse_file(gai_folder + '/' + file) for file in district_files]
    shutil.rmtree(gai_folder)

    for stellaris_file, gai_file in zip(stellaris_files, gai_files):
        for district in stellaris_file:
            if not district.startswith('@'):
                stellaris_ai = stellaris_file.safe_get(district).safe_get('ai_weight')
                gai_ai = gai_file.safe_get(district).safe_get('ai_weight')
                combined_ai = StellarisDict({'weight': ['= 0'], 'modifier': []})

                if stellaris_ai.safe_get('weight') != '= 0':
                    combined_ai.ensure({'modifier': [{
                        'weight': stellaris_ai['weight'],
                        'NOT': [{'has_global_flag': ['= gai_enabled_flag']}],
                    }]})

                if gai_ai.safe_get('weight') != '= 0':
                    combined_ai.ensure({'modifier': [{
                        'weight': gai_ai['weight'],
                        'has_global_flag': ['= gai_enabled_flag'],
                    }]})

                for modifier in stellaris_ai.safe_get('modifier', True):
                    modifier.ensure({'NOT': [{'has_global_flag': ['= gai_enabled_flag']}]})
                    combined_ai.ensure({'modifier': [modifier]})

                for modifier in gai_ai.safe_get('modifier', True):
                    modifier.ensure({'has_global_flag': ['= gai_enabled_flag']})
                    combined_ai.ensure({'modifier': [modifier]})

                stellaris_file[district][0]['ai_weight'] = [combined_ai]

    ########################
    # save stellaris files #
    ########################

    for stellaris_file, district_file in zip(stellaris_files, district_files):
        write_data(stellaris_file, './' + os.path.basename(district_file))
