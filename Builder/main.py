import glob
import os
import shutil
import requests
from distutils.dir_util import copy_tree
from bs4 import BeautifulSoup
from tools import StellarisDict, parse_file, write_data, extract_mod

########
# VARS #
########

stellaris_folder = r'D:\Game Libraries\Windows - Steam\steamapps\common\Stellaris'
workshop_folder = r'D:\Game Libraries\Windows - Steam\steamapps\workshop\content\281990'
mods_folder = r'C:\Users\wdboer\Documents\Paradox Interactive\Stellaris\mod'

collection_url = 'https://steamcommunity.com/workshop/filedetails/?id=1642766902'
ai_mod_count = 2
working_mod_count = 21

other_build_restrictions = [
    {'NOT': [{'is_planet_class': ['= pc_dyson_swarm']}]},
    {'NOT': [{'has_planet_flag': ['= xvcv_machinedlcmod_planet']}]},
]

########
# VARS #
########

mod_collection = []

district_files_overwritten = []
districts_overwritten = []
district_output_files = []

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
    for item in soup.find_all('div', 'collectionItem')[1:1+ai_mod_count+working_mod_count]:
        link = item.find('div', 'collectionItemDetails').find('a')
        mod_collection.append([
            link.get('href').rsplit('=', 1)[-1],
            link.text.strip('!~').split(' :: ')[-1]
                .split('2')[0].split(' : ')[0].split('(')[0].split('-')[0].split('[')[0].split(' for ')[0]
                .strip(),
            None, False,
        ])

    ########################
    # load stellaris files #
    ########################

    district_files_overwritten.extend(os.listdir(stellaris_folder + '/common/districts'))
    for file_name in district_files_overwritten:
        parsed = parse_file(stellaris_folder + '/common/districts/' + file_name)
        district_output_files.append((file_name, parsed))
        for district_name in parsed:
            districts_overwritten.append(district_name)

    for output_file in district_output_files:
        for district_name, district in output_file[1].items():
            for key in ['triggered_planet_modifier', 'triggered_desc', 'ai_resource_production']:
                for modifier in district[0].get_list(key):
                    modifier.ensure({'vanilla': [{'NOR': [{}]}]})

    district_files_overwritten.append('udp_extra_districts.txt')
    district_output_files.append(('udp_extra_districts.txt', StellarisDict()))

    ##################################
    # apply extra build restrictions #
    ##################################

    for output_file in district_output_files:
        for district_name, district in output_file[1].items():
            for title in ['show_on_uncolonized', 'potential']:
                for other_build_restriction in other_build_restrictions:
                    district[0].get_single(title).ensure(other_build_restriction)

    ###################
    # auto patch mods #
    ###################

    for i, other_mod in enumerate(mod_collection):
        print(other_mod)

        # load mod data
        try:
            mod_folder = extract_mod(workshop_folder, other_mod[0])
        except IndexError:
            print('Skipping mod with id: ' + other_mod[0])
            continue
        mod_file_names = os.listdir(mod_folder + '/common/districts')
        mod_districts = {}
        for mod_file_name in mod_file_names:
            mod_file = parse_file(mod_folder + '/common/districts/' + mod_file_name)
            if mod_file_name not in district_files_overwritten:
                for district_name in districts_overwritten:
                    if district_name in mod_file:
                        district_files_overwritten.append(mod_file_name)
                        break
            if mod_file_name in district_files_overwritten:
                for district_name, district in mod_file.items():
                    mod_districts[district_name] = district[0]
                    districts_overwritten.append(district_name)
        for mod_file_path in glob.glob(mod_folder + '/events/*'):
            mod_file = parse_file(mod_file_path)
            for events in mod_file.values():
                for event in events:
                    if type(event) is not str:
                        for effect in event.get_list('immediate'):
                            if effect.has_single('IF'):
                                effect = effect.get_single('IF')
                            if 'set_global_flag' in effect and other_mod[2] is None:
                                other_mod[2] = effect['set_global_flag'][0].replace('= ', '')
                                for other_build_restriction in other_build_restrictions:
                                    for value in other_build_restriction.get_values():
                                        if effect['set_global_flag'][0] == value:
                                            other_mod[3] = True
        shutil.rmtree(mod_folder)

        # save certain added districts
        for district_name, district in mod_districts.items():
            for output_file in district_output_files:
                if district_name in output_file[1]:
                    break
            else:
                for output_file in district_output_files:
                    if output_file[0] == 'udp_extra_districts.txt':
                        for title in ['show_on_uncolonized', 'potential']:
                            use_mod_flag(other_mod)
                            district.get_single(title).ensure({'has_global_flag': ['= ' + other_mod[2]]})
                        output_file[1].ensure({district_name: [district]})
                        break

        # disable removed districts
        for output_file in district_output_files:
            if output_file[0] in mod_file_names:
                for district_name, district in output_file[1].items():
                    if district_name not in mod_districts:
                        for title in ['show_on_uncolonized', 'potential']:
                            use_mod_flag(other_mod)
                            district[0].get_single(title).ensure({'NOT': [{'has_global_flag': ['= ' + other_mod[2]]}]})

        # merge ai behaviours for ai mods
        if i < ai_mod_count:
            for output_file in district_output_files:
                for district_name, district in output_file[1].items():
                    if district_name in mod_districts:
                        mod_district = mod_districts[district_name]
                        use_mod_flag(other_mod)

                        current_ai = district[0].get_single('ai_weight')
                        new_ai = mod_district.get_single('ai_weight')
                        combined_ai = StellarisDict({'weight': ['= 0'], 'modifier': []})

                        if current_ai.get_single('weight') != '= 0':
                            combined_ai.ensure({'modifier': [{
                                'weight': current_ai['weight'],
                                'NOT': [{'has_global_flag': ['= ' + other_mod[2]]}],
                            }]})
                        if new_ai.get_single('weight') != '= 0':
                            combined_ai.ensure({'modifier': [{
                                'weight': new_ai['weight'],
                                'has_global_flag': ['= ' + other_mod[2]],
                            }]})

                        for modifier in current_ai.get_list('modifier'):
                            mod_flag_set = False
                            for item in modifier.get_list('has_global_flag'):
                                for mod in mod_collection:
                                    if item.replace('= ', '') == mod[2]:
                                        mod_flag_set = True
                            if not mod_flag_set:
                                modifier.ensure({'NOT': [{'has_global_flag': ['= ' + other_mod[2]]}]})
                            combined_ai.ensure({'modifier': [modifier]})
                        for modifier in new_ai.get_list('modifier'):
                            modifier.ensure({'has_global_flag': ['= ' + other_mod[2]]})
                            combined_ai.ensure({'modifier': [modifier]})

                        district[0]['ai_weight'] = [combined_ai]

        # merge build restrictions
        for output_file in district_output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for title in ['show_on_uncolonized', 'potential', 'allow']:
                        for key, values in mod_district.get_single(title).items():
                            for value in values:
                                if key == 'has_deposit' or (isinstance(value, StellarisDict) and 'has_deposit' in value.get_keys()) \
                                        or (key == 'has_planet_flag' and output_file[0] == '04_ringworld_districts.txt'):
                                    use_mod_flag(other_mod)
                                    value = {'NOT': [{'has_global_flag': ['= ' + other_mod[2]]}], key: [value]}
                                    key = 'OR'
                                merged = False
                                if key == 'OR' and set(value.keys()) == {'is_planet_class'}:
                                    if 'uncapped' in district_name:
                                        value['is_planet_class'] = [x for x in value['is_planet_class'] if x != '= pc_ringworld_habitable']
                                    for block in district[0].get_single(title).get_list(key):
                                        if set(block.keys()) == {'is_planet_class'}:
                                            block['is_planet_class'] = block['is_planet_class'] + \
                                                                       [x for x in value['is_planet_class'] if x not in block['is_planet_class']]
                                            merged = True
                                if not merged and key != 'does_spawn_housing_districts' and value not in district[0].get_single(title).get_list(key):
                                    district[0].get_single(title).ensure({key: [value]})

        # merge triggered modifiers and descriptions
        for output_file in district_output_files:
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

                        for old_modifier in district[0].get_list(key):
                            if 'vanilla' in old_modifier:
                                for new_modifier in mod_district.get_list(key):
                                    if old_modifier.copy_without(trigger_key).copy_without('vanilla') == new_modifier.copy_without(trigger_key) and \
                                            new_modifier.get_single(trigger_key).get_single('owner').get_single('AND').has_single('NOT') and \
                                            old_modifier.get_single(trigger_key).get_single('owner') == \
                                            new_modifier.get_single(trigger_key).get_single('owner').get_single('AND').copy_without('NOT'):
                                        old_modifier.get_single('vanilla').ensure({'delete': []})
                                        break
                                else:
                                    if old_modifier.copy_without('vanilla') not in mod_district.get_list(key):
                                        use_mod_flag(other_mod)
                                        old_modifier.get_single('vanilla').get_single('NOR').ensure({'has_global_flag': ['= ' + other_mod[2]]})

        # merge normal modifiers
        for output_file in district_output_files:
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

        # merge resources
        for output_file in district_output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for title in ['cost', 'upkeep', 'produces']:
                        for value in mod_district.get_single('resources').get_list(title):
                            if value not in district[0].get_single('resources').get_list(title):
                                if 'trigger' not in value:
                                    use_mod_flag(other_mod)
                                    value.ensure({'trigger': [{'has_global_flag': ['= ' + other_mod[2]]}]})
                                elif value.get_single('trigger').get_single('owner').has_single('NOT'):
                                    district[0].get_single('resources').get_list(title).remove(value.copy_without('trigger'))
                                district[0].get_single('resources').ensure({title: [value]})

        # merge district conversions
        for output_file in district_output_files:
            for district_name, district in output_file[1].items():
                if district_name in mod_districts:
                    mod_district = mod_districts[district_name]
                    for value in mod_district.get_single('convert_to'):
                        if value != district_name and value not in district[0].get_single('convert_to'):
                            district[0].get_single('convert_to').ensure({value: []})

    ################################
    # fix OR in build restrictions #
    ################################

    for output_file in district_output_files:
        for district_name, district in output_file[1].items():
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

    for output_file in district_output_files:
        for district_name, district in output_file[1].items():
            for key in ['triggered_planet_modifier', 'triggered_desc', 'ai_resource_production']:
                trigger_key = 'potential' if key == 'triggered_planet_modifier' else 'trigger'
                i = 0
                while i < len(district[0].get_list(key)):
                    modifier = district[0].get_list(key)[i]
                    for flag in ['default', 'vanilla']:
                        if flag in modifier:
                            if 'delete' in modifier.get_single(flag):
                                district[0].get_list(key).remove(modifier)
                                i -= 1
                                break
                            if len(modifier.get_single(flag).get_single('NOR').keys()) > 0:
                                if trigger_key not in modifier:
                                    modifier.ensure({trigger_key: [{}]})
                                modifier.get_single(trigger_key).ensure(modifier.get_single(flag))
                            del modifier[flag]
                    i += 1

    #############################
    # uncap district generation #
    #############################

    for output_file in district_output_files:
        for district_name in output_file[1]:
            if 'min_for_deposits_on_planet' in output_file[1].get_single(district_name):
                output_file[1][district_name][0]['min_for_deposits_on_planet'] = ['= 0']
            if 'max_for_deposits_on_planet' in output_file[1].get_single(district_name):
                output_file[1][district_name][0]['max_for_deposits_on_planet'] = ['= 999']

    #########################
    # save all output files #
    #########################

    shutil.rmtree('../Mod', True)
    os.makedirs('../Mod/!!!!Universal Districts Patch/common/districts')

    for output_file in district_output_files:
        write_data(output_file[1], '../Mod/!!!!Universal Districts Patch/common/districts/' + output_file[0])
        district_files_overwritten.remove(output_file[0])

    for file_overwritten in district_files_overwritten:
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

    for other_mod in mod_collection:
        print('- [url=https://steamcommunity.com/sharedfiles/filedetails/?id=' + other_mod[0] + '] ' + other_mod[1] + ' [/url]', end='')
        if other_mod[3]:
            print(' (' + other_mod[2] + ')', end='')
        print()
