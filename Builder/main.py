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
other_mod_ids = [
    # '1100284147',
    # '1532624807',
    # '1596737403',
    # '1624127196',
    # '1640486360',
    # '727000451',
    # '819148835',
    # '1604391033',
    # '1653766038',
    # '1311725711',
    # '1597596692',
    # '1603330813',
    # '1681075379',
    # '1611227475',
]

########
# VARS #
########

files_overwritten = []
districts_overwritten = []
output_files = []

########
# VARS #
########


class StellarisDict(dict):
    def ensure(self, data):
        for key, values in data.items():
            if key not in self:
                self[key] = []
            self[key].extend(values)

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
        tokens = ['{'] + [item for item in re.split(r'\s+', text) if len(item.strip()) > 0] + ['}']
        tokens = list(reversed(tokens))
        return parse_object(tokens)


def parse_object(tokens):
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
            value = parse_object(tokens)
            if type(value) is str:
                value = sign + ' ' + value
        if key == 'OR' and len(value.keys()) == 1 and len(value[list(value.keys())[0]]) <= 1:
            key = list(value.keys())[0]
            value = value[key][0] if len(value[key]) == 1 else None
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

    files_overwritten.extend(os.listdir(stellaris_folder + '/common/districts'))
    for file_name in files_overwritten:
        parsed = parse_file(stellaris_folder + '/common/districts/' + file_name)
        output_files.append((file_name, parsed))
        for district_name in parsed:
            if not district_name.startswith('@'):
                districts_overwritten.append(district_name)

    files_overwritten.append('udp_extra_districts.txt')
    output_files.append(('udp_extra_districts.txt', StellarisDict()))

    #############################
    # merge ai weights from gai #
    #############################

    gai_folder = extract_mod(gai_mod_id)
    gai_files = [(os.path.basename(file_path), parse_file(file_path)) for file_path in glob.glob(gai_folder + '/common/districts/*')]
    shutil.rmtree(gai_folder)

    for output_file in output_files:
        for gai_file in gai_files:
            if output_file[0] == gai_file[0]:
                break
        else:
            continue
        for district_name in output_file[1]:
            if not district_name.startswith('@'):

                stellaris_ai = output_file[1].safe_get(district_name).safe_get('ai_weight')
                gai_ai = gai_file[1].safe_get(district_name).safe_get('ai_weight')
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

                output_file[1][district_name][0]['ai_weight'] = [combined_ai]

    ###################
    # auto patch mods #
    ###################

    for other_mod_id in other_mod_ids:

        # load mod data
        try:
            mod_folder = extract_mod(other_mod_id)
        except IndexError:
            print('Skipping mod with id: ' + other_mod_id)
            continue
        mod_file_names = os.listdir(mod_folder + '/common/districts')
        mod_districts = {}
        mod_flag = None
        for mod_file_name in mod_file_names:
            mod_file = parse_file(mod_folder + '/common/districts/' + mod_file_name)
            if mod_file_name not in files_overwritten:
                for district_name in districts_overwritten:
                    if district_name in mod_file:
                        files_overwritten.append(mod_file_name)
                        break
            if mod_file_name in files_overwritten:
                for district_name, district in mod_file.items():
                    if not district_name.startswith('@'):
                        mod_districts[district_name] = district[0]
                        districts_overwritten.append(district_name)
        for mod_file_path in glob.glob(mod_folder + '/events/*'):
            mod_file = parse_file(mod_file_path)
            for event in mod_file.safe_get('event', True):
                for effect in event.safe_get('immediate', True):
                    if 'set_global_flag' in effect:
                        mod_flag = effect['set_global_flag'][0].replace('= ', '')
                        break
                else:
                    break
            else:
                break
        shutil.rmtree(mod_folder)

        # save certain added districts
        for district_name, district in mod_districts.items():
            for output_file in output_files:
                if district_name in output_file[1]:
                    break
            else:
                for output_file in output_files:
                    if output_file[0] == 'udp_extra_districts.txt':
                        output_file[1].ensure({district_name: [district]})
                        break

        # disable removed districts
        for output_file in output_files:
            if output_file[0] in mod_file_names:
                for district_name, district in output_file[1].items():
                    if not district_name.startswith('@') and district_name not in mod_districts:
                        for title in ['show_on_uncolonized', 'potential']:
                            assert mod_flag is not None
                            district[0].safe_get(title).ensure({'NOT': [{'has_global_flag': ['= ' + mod_flag]}]})

        # merge build restrictions
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for title in ['show_on_uncolonized', 'potential']:
                        for key, values in mod_district.safe_get(title).items():
                            for value in values:
                                if value not in district[0].safe_get(title).safe_get(key, True):
                                    district[0].safe_get(title).ensure({key: [value]})

        # merge triggered modifiers and descriptions
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for key in ['triggered_planet_modifier', 'triggered_desc']:
                        for value in mod_district.safe_get(key, True):
                            if value not in district[0].safe_get(key, True):
                                district[0].ensure({key: [value]})

    #############################
    # uncap district generation #
    #############################

    for output_file in output_files:
        for district_name in output_file[1]:
            if not district_name.startswith('@'):
                if 'min_for_deposits_on_planet' in output_file[1].safe_get(district_name):
                    output_file[1][district_name][0]['min_for_deposits_on_planet'] = ['= 0']
                if 'max_for_deposits_on_planet' in output_file[1].safe_get(district_name):
                    output_file[1][district_name][0]['max_for_deposits_on_planet'] = ['= 999']

    #########################
    # save all output files #
    #########################

    for output_file in output_files:
        write_data(output_file[1], './testing/mod/' + output_file[0])
        files_overwritten.remove(output_file[0])

    for file_overwritten in files_overwritten:
        open('./testing/mod/' + file_overwritten, 'w').close()