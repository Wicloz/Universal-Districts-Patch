import re
import tempfile
import zipfile
import glob
import os
import shutil
from distutils.dir_util import copy_tree


########
# VARS #
########

stellaris_folder = r'D:\Game Libraries\Windows - Steam\steamapps\common\Stellaris'
workshop_folder = r'D:\Game Libraries\Windows - Steam\steamapps\workshop\content\281990'
mods_folder = r'C:\Users\wdboer\Documents\Paradox Interactive\Stellaris\mod'

gai_mod_id = '1584133829'
other_mod_ids = [
    '1100284147',
    '1532624807',
    '1596737403',
    '1624127196',
    '727000451',
    '819148835',
    '1604391033',
    '1653766038',
    '1311725711',
    '1597596692',
    '1603330813',
    '1681075379',
    # '1639764264',
    # '1640486360',
    # '1611227475',
]
other_build_restrictions = [
    {'NOT': [{'is_planet_class': ['= pc_dyson_swarm']}]},
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


def copytree(src, dst, symlinks=False, ignore=None):
    if not os.path.exists(dst):
        os.makedirs(dst)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copytree(s, d, symlinks, ignore)
        else:
            if not os.path.exists(d) or os.stat(s).st_mtime - os.stat(d).st_mtime > 1:
                shutil.copy2(s, d)


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
        copy = self.copy()
        if key in copy:
            del copy[key]
        return copy


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
                value = sign + ' ' + value.strip('\'"`')
        if key == 'OR' and len(value.keys()) == 1 and list(value.keys())[0] == 'has_valid_civic' and len(value[list(value.keys())[0]]) <= 1:
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

    for output_file in output_files:
        for district_name, district in output_file[1].items():
            if not district_name.startswith('@'):
                for key in ['triggered_planet_modifier', 'triggered_desc', 'ai_resource_production']:
                    for modifier in district[0].get_list(key):
                        modifier.ensure({'vanilla': [{'NOR': [{}]}]})

    files_overwritten.append('udp_extra_districts.txt')
    output_files.append(('udp_extra_districts.txt', StellarisDict()))

    ##################################
    # apply extra build restrictions #
    ##################################

    for output_file in output_files:
        for district_name, district in output_file[1].items():
            if not district_name.startswith('@'):
                for title in ['show_on_uncolonized', 'potential']:
                    for other_build_restriction in other_build_restrictions:
                        district[0].get_single(title).ensure(other_build_restriction)

    #############################
    # merge ai weights from gai #
    #############################

    gai_folder = extract_mod(gai_mod_id)
    gai_files = [
        (os.path.basename(file_path), parse_file(file_path))
        for file_path in glob.glob(gai_folder + '/common/districts/*')
    ]
    shutil.rmtree(gai_folder)

    for output_file in output_files:
        for gai_file in gai_files:
            if output_file[0] == gai_file[0]:
                break
        else:
            continue
        for district_name in output_file[1]:
            if not district_name.startswith('@'):

                stellaris_ai = output_file[1].get_single(district_name).get_single('ai_weight')
                gai_ai = gai_file[1].get_single(district_name).get_single('ai_weight')
                combined_ai = StellarisDict({'weight': ['= 0'], 'modifier': []})

                if stellaris_ai.get_single('weight') != '= 0':
                    combined_ai.ensure({'modifier': [{
                        'weight': stellaris_ai['weight'],
                        'NOT': [{'has_global_flag': ['= gai_enabled_flag']}],
                    }]})

                if gai_ai.get_single('weight') != '= 0':
                    combined_ai.ensure({'modifier': [{
                        'weight': gai_ai['weight'],
                        'has_global_flag': ['= gai_enabled_flag'],
                    }]})

                for modifier in stellaris_ai.get_list('modifier'):
                    modifier.ensure({'NOT': [{'has_global_flag': ['= gai_enabled_flag']}]})
                    combined_ai.ensure({'modifier': [modifier]})

                for modifier in gai_ai.get_list('modifier'):
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
            for events in mod_file.values():
                for event in events:
                    if type(event) is not str:
                        for effect in event.get_list('immediate'):
                            if 'set_global_flag' in effect and mod_flag is None:
                                mod_flag = effect['set_global_flag'][0].replace('= ', '')
        shutil.rmtree(mod_folder)

        # save certain added districts
        for district_name, district in mod_districts.items():
            for output_file in output_files:
                if district_name in output_file[1]:
                    break
            else:
                for output_file in output_files:
                    if output_file[0] == 'udp_extra_districts.txt':
                        for title in ['show_on_uncolonized', 'potential']:
                            assert mod_flag is not None
                            district.get_single(title).ensure({'has_global_flag': ['= ' + mod_flag]})
                        output_file[1].ensure({district_name: [district]})
                        break

        # disable removed districts
        for output_file in output_files:
            if output_file[0] in mod_file_names:
                for district_name, district in output_file[1].items():
                    if not district_name.startswith('@') and district_name not in mod_districts:
                        for title in ['show_on_uncolonized', 'potential']:
                            assert mod_flag is not None
                            district[0].get_single(title).ensure({'NOT': [{'has_global_flag': ['= ' + mod_flag]}]})

        # merge build restrictions
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for title in ['show_on_uncolonized', 'potential', 'allow']:
                        for key, values in mod_district.get_single(title).items():
                            for value in values:
                                if key != 'does_spawn_housing_districts' and value not in district[0].get_single(title).get_list(key):
                                    if key == 'OR':
                                        for or_value in district[0].get_single(title).get_list(key):
                                            for planet in or_value.get_list('is_planet_class'):
                                                if planet not in value.get_list('is_planet_class'):
                                                    assert mod_flag is not None
                                                    value.ensure({'NOT': [{'has_global_flag': ['= ' + mod_flag]}]})
                                                    break
                                    district[0].get_single(title).ensure({key: [value]})

        # merge triggered modifiers and descriptions
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for key in ['triggered_planet_modifier', 'triggered_desc', 'ai_resource_production']:
                        trigger_key = 'potential' if key == 'triggered_planet_modifier' else 'trigger'

                        for value in mod_district.get_list(key):
                            if value not in [item.copy_without('vanilla') for item in district[0].get_list(key)]:
                                if trigger_key not in value or \
                                        value.get_single(trigger_key) in [item.get_single(trigger_key) for item in district[0].get_list(key)]:
                                    if trigger_key not in value:
                                        value.ensure({trigger_key: [{}]})
                                    assert mod_flag is not None
                                    value.get_single(trigger_key).ensure({'has_global_flag': ['= ' + mod_flag]})
                                district[0].ensure({key: [value]})

                        for value in district[0].get_list(key):
                            if 'vanilla' in value and value.copy_without('vanilla') not in mod_district.get_list(key):
                                assert mod_flag is not None
                                value.get_single('vanilla').get_single('NOR').ensure({'has_global_flag': ['= ' + mod_flag]})

        # merge normal modifiers
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    merge_modifier = True

                    if 'planet_modifier' in district[0]:
                        if (mod_district.get_single('planet_modifier') == district[0].get_single('planet_modifier')) or \
                                (district_name == 'district_nexus' and mod_district.get_single('planet_modifier') == {'planet_housing_add': ['= 5']}):
                            merge_modifier = False
                        else:
                            district[0].ensure({'triggered_planet_modifier': [{
                                'default': [{'NOR': [{}]}],
                                'modifier': [district[0].get_single('planet_modifier')],
                            }]})
                            del district[0]['planet_modifier']
                    else:
                        for modifier in district[0].get_list('triggered_planet_modifier'):
                            if 'default' in modifier:
                                if (mod_district.get_single('planet_modifier') == modifier.get_single('modifier')) or \
                                        (district_name == 'district_nexus' and mod_district.get_single('planet_modifier') == {'planet_housing_add': ['= 5']}):
                                    merge_modifier = False
                                break
                        else:
                            merge_modifier = False

                    if merge_modifier:
                        if 'planet_modifier' in mod_district:
                            assert mod_flag is not None
                            district[0].ensure({'triggered_planet_modifier': [{
                                'potential': [{'has_global_flag': ['= ' + mod_flag]}],
                                'modifier': [mod_district.get_single('planet_modifier')],
                            }]})
                        for modifier in district[0].get_list('triggered_planet_modifier'):
                            if 'default' in modifier:
                                assert mod_flag is not None
                                modifier.get_single('default').get_single('NOR').ensure({'has_global_flag': ['= ' + mod_flag]})
                                break

        # merge upkeep and production
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for title in ['upkeep', 'produces']:
                        for value in mod_district.get_single('resources').get_list(title):
                            if value not in district[0].get_single('resources').get_list(title):
                                if 'trigger' not in value:
                                    assert mod_flag is not None
                                    value.ensure({'trigger': [{'has_global_flag': ['= ' + mod_flag]}]})
                                district[0].get_single('resources').ensure({title: [value]})

        # merge district conversions
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for value in mod_district.get_single('convert_to'):
                        if value != district_name and value not in district[0].get_single('convert_to'):
                            district[0].get_single('convert_to').ensure({value: []})

    ################################
    # fix OR in build restrictions #
    ################################

    for output_file in output_files:
        for district_name, district in output_file[1].items():
            if not district_name.startswith('@'):
                for title in ['show_on_uncolonized', 'potential', 'allow']:
                    for or_block in district[0].get_single(title).get_list('OR'):
                        for key, values in or_block.items():
                            for value in values:
                                if value in district[0].get_single(title).get_list(key):
                                    district[0].get_single(title).get_list(key).remove(value)
                                    if len(district[0].get_single(title).get_list(key)) == 0:
                                        del district[0].get_single(title)[key]

    ###########################
    # convert temporary flags #
    ###########################

    for output_file in output_files:
        for district_name, district in output_file[1].items():
            if not district_name.startswith('@'):
                for key in ['triggered_planet_modifier', 'triggered_desc', 'ai_resource_production']:
                    trigger_key = 'potential' if key == 'triggered_planet_modifier' else 'trigger'
                    for modifier in district[0].get_list(key):
                        for flag in ['default', 'vanilla']:
                            if flag in modifier:
                                if len(modifier.get_single(flag).get_single('NOR').keys()) > 0:
                                    if trigger_key not in modifier:
                                        modifier.ensure({trigger_key: [{}]})
                                    modifier.get_single(trigger_key).ensure(modifier.get_single(flag))
                                del modifier[flag]

    #############################
    # uncap district generation #
    #############################

    for output_file in output_files:
        for district_name in output_file[1]:
            if not district_name.startswith('@'):
                if 'min_for_deposits_on_planet' in output_file[1].get_single(district_name):
                    output_file[1][district_name][0]['min_for_deposits_on_planet'] = ['= 0']
                if 'max_for_deposits_on_planet' in output_file[1].get_single(district_name):
                    output_file[1][district_name][0]['max_for_deposits_on_planet'] = ['= 999']

    #########################
    # save all output files #
    #########################

    shutil.rmtree('../Mod', True)
    os.makedirs('../Mod/!!!!Universal Districts Patch/common/districts')

    for output_file in output_files:
        write_data(output_file[1], '../Mod/!!!!Universal Districts Patch/common/districts/' + output_file[0])
        files_overwritten.remove(output_file[0])

    for file_overwritten in files_overwritten:
        open('../Mod/!!!!Universal Districts Patch/common/districts/' + file_overwritten, 'w').close()

    shutil.rmtree(mods_folder + '/!!!!Universal Districts Patch', True)
    shutil.rmtree(mods_folder + '/!!!!Universal Districts Patch.mod', True)

    for folder in ['../Mod', '../Skeleton']:
        for item in os.listdir(folder):
            source = folder + '/' + item
            destination = mods_folder + '/' + item
            if os.path.isdir(source):
                copy_tree(source, destination)
            else:
                shutil.copy(source, destination)
