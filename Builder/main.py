import shlex
import tempfile
import zipfile
import glob
import os
import shutil
import requests
from distutils.dir_util import copy_tree
from bs4 import BeautifulSoup

########
# VARS #
########

stellaris_folder = r'D:\Game Libraries\Windows - Steam\steamapps\common\Stellaris'
workshop_folder = r'D:\Game Libraries\Windows - Steam\steamapps\workshop\content\281990'
mods_folder = r'C:\Users\wdboer\Documents\Paradox Interactive\Stellaris\mod'

gai_mod_id = '1584133829'
collection_url = 'https://steamcommunity.com/workshop/filedetails/?id=1642766902'
ignore_start_mods = 1
ignore_end_mods = 2

other_build_restrictions = [
    {'NOT': [{'is_planet_class': ['= pc_dyson_swarm']}]},
    {'NAND': [{
        'is_planet_class': ['= pc_ringworld_habitable'],
        'OR': [{'has_global_flag': ['= ringworld_districts_v2', '= lrsk_megastrcutre_district_rework_mod_active']}],
    }]},
]

########
# VARS #
########

other_mods = []
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

    def get_values(self):
        for values in self.values():
            for value in values:
                if isinstance(value, StellarisDict):
                    yield from value.get_values()
                else:
                    yield value


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
        if (key == 'OR' or key == 'AND') and len(value.keys()) == 1 and len(value[list(value.keys())[0]]) <= 1:
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


def use_mod_flag(mod):
    assert mod[2] is not None
    mod[3] = True


if __name__ == '__main__':
    ####################################
    # convert extra build restrictions #
    ####################################

    for i in range(len(other_build_restrictions)):
        other_build_restrictions[i] = StellarisDict().ensure(other_build_restrictions[i])

    ####################################
    # get collection of patchable mods #
    ####################################

    soup = BeautifulSoup(requests.get(collection_url).text, 'html.parser')
    for item in soup.find_all('div', 'collectionItem')[ignore_start_mods:-ignore_end_mods]:
        link = item.find('div', 'collectionItemDetails').find('a')
        other_mods.append([
            link.get('href').rsplit('=', 1)[-1],
            link.text.strip('!~').replace('PJs :: ', '').split('2')[0].split(' : ')[0].split('(')[0].split('-')[0].split('[')[0].strip(),
            None, False,
        ])

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

    for other_mod in other_mods:

        # load mod data
        try:
            mod_folder = extract_mod(other_mod[0])
        except IndexError:
            print('Skipping mod with id: ' + other_mod[0])
            continue
        mod_file_names = os.listdir(mod_folder + '/common/districts')
        mod_districts = {}
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
                            if 'set_global_flag' in effect and other_mod[2] is None:
                                other_mod[2] = effect['set_global_flag'][0].replace('= ', '')
                                if effect['set_global_flag'][0] == '= gai_enabled_flag':
                                    other_mod[3] = True
                                else:
                                    for other_build_restriction in other_build_restrictions:
                                        for value in other_build_restriction.get_values():
                                            if effect['set_global_flag'][0] == value:
                                                other_mod[3] = True
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
                            use_mod_flag(other_mod)
                            district.get_single(title).ensure({'has_global_flag': ['= ' + other_mod[2]]})
                        output_file[1].ensure({district_name: [district]})
                        break

        # disable removed districts
        for output_file in output_files:
            if output_file[0] in mod_file_names:
                for district_name, district in output_file[1].items():
                    if not district_name.startswith('@') and district_name not in mod_districts:
                        for title in ['show_on_uncolonized', 'potential']:
                            use_mod_flag(other_mod)
                            district[0].get_single(title).ensure({'NOT': [{'has_global_flag': ['= ' + other_mod[2]]}]})

        # merge build restrictions
        for output_file in output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for title in ['show_on_uncolonized', 'potential', 'allow']:
                        for key, values in mod_district.get_single(title).items():
                            for value in values:
                                merged = False
                                if key == 'OR' and set(value.keys()) == {'is_planet_class'}:
                                    for block in district[0].get_single(title).get_list(key):
                                        if set(block.keys()) == {'is_planet_class'}:
                                            block['is_planet_class'] = block['is_planet_class'] + \
                                                                       [x for x in value['is_planet_class'] if x not in block['is_planet_class']]
                                            merged = True
                                if not merged and key != 'does_spawn_housing_districts' and value not in district[0].get_single(title).get_list(key):
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
                                must_add_flag = trigger_key not in value or \
                                                value.get_single(trigger_key) in [item.get_single(trigger_key) for item in district[0].get_list(key)]
                                if not must_add_flag and \
                                        set(value.get_single(trigger_key).keys()) == {'exists', 'owner'} and \
                                        value.get_single(trigger_key).get_single('exists') == '= owner' and \
                                        len(value.get_single(trigger_key).get_list('owner')) == 1 and \
                                        set(value.get_single(trigger_key).get_single('owner').keys()).issubset({
                                            'is_regular_empire',
                                            'is_gestalt',
                                            'is_machine_empire',
                                            'is_hive_empire',
                                            'is_fallen_empire',
                                            'is_fallen_empire_spiritualist',
                                            'is_mechanical_empire',
                                        }):
                                    must_add_flag = True
                                if must_add_flag:
                                    if trigger_key not in value:
                                        value.ensure({trigger_key: [{}]})
                                    use_mod_flag(other_mod)
                                    value.get_single(trigger_key).ensure({'has_global_flag': ['= ' + other_mod[2]]})
                                district[0].ensure({key: [value]})

                        for value in district[0].get_list(key):
                            if 'vanilla' in value and value.copy_without('vanilla') not in mod_district.get_list(key):
                                use_mod_flag(other_mod)
                                value.get_single('vanilla').get_single('NOR').ensure({'has_global_flag': ['= ' + other_mod[2]]})

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
                            use_mod_flag(other_mod)
                            district[0].ensure({'triggered_planet_modifier': [{
                                'potential': [{'has_global_flag': ['= ' + other_mod[2]]}],
                                'modifier': [mod_district.get_single('planet_modifier')],
                            }]})
                        for modifier in district[0].get_list('triggered_planet_modifier'):
                            if 'default' in modifier:
                                use_mod_flag(other_mod)
                                modifier.get_single('default').get_single('NOR').ensure({'has_global_flag': ['= ' + other_mod[2]]})
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
                                    use_mod_flag(other_mod)
                                    value.ensure({'trigger': [{'has_global_flag': ['= ' + other_mod[2]]}]})
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
                    for block in district[0].get_single(title).get_list('OR'):
                        for key, values in block.items():
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

    #########################
    # create new patch list #
    #########################

    for other_mod in other_mods:
        print('- [url=https://steamcommunity.com/sharedfiles/filedetails/?id=' + other_mod[0] + '] ' + other_mod[1] + ' [/url]', end='')
        if other_mod[3]:
            print(' (' + other_mod[2] + ')', end='')
        print()
