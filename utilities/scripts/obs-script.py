import obspython as obs

import urllib.request
import urllib.error
import requests
from ctypes import *
from ctypes.util import find_library
from contextlib import contextmanager, ExitStack

obslib = CDLL(find_library("obs"))

url         = ""
team_list_path = ""
team_list = []
contest_start_time = None

SCENE_NAME = "Team View"
VLC_SOURCE_ID = "vlc_source"

# ------------------------------------------------------------
# Helper functions

def wrap(funcname, restype, argtypes):
    """Simplify wrapping ctypes functions in obsffi"""
    func = getattr(obslib, funcname)
    func.restype = restype
    func.argtypes = argtypes
    globals()["g_" + funcname] = func
    return func

# ------------------------------------------------------------

def get_clock_text():
    return "00:00:01"


def update_clock():
    for scene in obs.obs_frontend_get_scenes():
        scene_source = scene
        scene = obs.obs_scene_from_source(scene)

        # Get clock text source
        # items = obs.obs_scene_enum_items(scene)
        # print([obs.obs_source_get_name(obs.obs_sceneitem_get_source(item)) for item in items])
        clock_text_source = obs.obs_sceneitem_get_source(obs.obs_scene_find_source_recursive(scene, "clock_text"))
        print(clock_text_source)

        # Get clock text source settings
        if clock_text_source:
            settings = obs.obs_source_get_settings(clock_text_source)
            obs.obs_data_set_string(settings, "text", get_clock_text())
            obs.obs_source_update(clock_text_source, settings)
            obs.obs_data_release(settings)
            obs.obs_source_release(clock_text_source)


def print_source_settings(source):
    settings = obs.obs_source_get_settings(source)
    psettings = obs.obs_source_get_private_settings(source)
    dsettings = obs.obs_data_get_defaults(settings)
    pdsettings = obs.obs_data_get_defaults(psettings)
    print("[---------- settings ----------")
    print(obs.obs_data_get_json(settings))
    print("---------- private_settings ----------")
    print(obs.obs_data_get_json(psettings))
    print("---------- default settings for this source type ----------")
    print(obs.obs_data_get_json(dsettings))
    print("---------- default private settings for this source type ----------")
    print(obs.obs_data_get_json(pdsettings))


def generate_clock_bar():
    scenes = obs.obs_frontend_get_scenes()

    for scene in scenes:
        scene_source = scene
        scene = obs.obs_scene_from_source(scene)

        # Delete all clock bar items
        items = obs.obs_scene_enum_items(scene)
        for item in items:
            source = obs.obs_sceneitem_get_source(item)
            if 'clock_bar' in obs.obs_source_get_name(source):
                obs.obs_sceneitem_remove(item)
                obs.obs_source_release(source)

        # # Make a rectangle of width 1920 and height 1080
        clock_rect = obs.obs_source_create_private("color_source", "clock_rect", None)

        # Set default width and height
        settings = obs.obs_source_get_settings(clock_rect)
        obs.obs_data_set_int(settings, "width", 280)
        obs.obs_data_set_int(settings, "height", 60)
        obs.obs_data_set_int(settings, "color", 0xAA0000FF)
        obs.obs_source_update(clock_rect, settings)
        obs.obs_data_release(settings)

        # Make a clock from browser source with file path to clock.html
        clock_text_source = obs.obs_source_create_private("browser_source", "clock", None)
        # Set default width and height
        settings = obs.obs_source_get_settings(clock_text_source)
        obs.obs_data_set_int(settings, "width", 280)
        obs.obs_data_set_int(settings, "height", 60)
        # Set url to local file path clock.html
        print_source_settings(clock_text_source)
        obs.obs_data_set_string(settings, "url", "file://./clock.html")
        obs.obs_source_update(clock_text_source, settings)
        obs.obs_data_release(settings)

        clock_rect_sceneitem = obs.obs_scene_add(scene, clock_rect)
        clock_text_sceneitem = obs.obs_scene_add(scene, clock_text_source)

        pos = obs.vec2()
        pos.x = 96
        pos.y = 926
        obs.obs_sceneitem_set_pos(clock_rect_sceneitem, pos)

        # obs.obs_sceneitem_set_bounds_type(clock_rect_sceneitem, obs.OBS_BOUNDS_SCALE_INNER)
        # obs.obs_sceneitem_set_alignment(clock_rect_sceneitem, 0)
        pos = obs.vec2()
        pos.x = 24
        pos.y = 4
        obs.obs_sceneitem_set_pos(clock_text_sceneitem, pos)

        info_bar_group = obs.obs_scene_add_group(scene, "clock_bar_%s" % obs.obs_source_get_name(scene_source).lower())
        obs.obs_sceneitem_group_add_item(info_bar_group, clock_rect_sceneitem)
        obs.obs_sceneitem_group_add_item(info_bar_group, clock_text_sceneitem)

        obs.obs_source_release(clock_rect)
        obs.obs_source_release(clock_text_source)


def generate_scene(props, prop):
    global url
    global team_list

    # Get all scene name including deleted ones
    scenes = [obs.obs_source_get_name(scene) for scene in obs.obs_frontend_get_scenes()]

    if SCENE_NAME not in scenes:
        obs.obs_scene_create(SCENE_NAME)

    # Clear scene items
    scene = obs.obs_scene_from_source(obs.obs_get_source_by_name(SCENE_NAME))

    items = obs.obs_scene_enum_items(scene)

    for item in items:
        source = obs.obs_sceneitem_get_source(item)
        obs.obs_sceneitem_remove(item)
        # Remove source reference
        obs.obs_source_release(source)

    for team in team_list:
        team, team_name = team
        # Create a group named "<team> group"
        group_name = team + " group"

        r = requests.get(f"{url}/user/{team}")
        if r.status_code != 200:
            print(f"Error getting user {team} info")
            continue
        ip = r.json()['ip_address']

        group = obs.obs_scene_add_group(scene, group_name)

        # Set group source bound
        # obs.obs_sceneitem_set_bounds_type(group, obs.OBS_BOUNDS_SCALE_INNER)

        vlc_source = obs.obs_source_create_private("vlc_source", "%s_source" % team, None)

        # Set vlc source playlist property to the team's playlist
        settings = obs.obs_source_get_settings(vlc_source)

        playlist_value = obs.obs_data_create()
        obs.obs_data_set_string(playlist_value, "value", f"http://10.0.30.1:9090")
        obs.obs_data_set_bool(playlist_value, "selected", True)
        obs.obs_data_set_bool(playlist_value, "hidden", False)

        playlist_settings_array = obs.obs_data_array_create()
        obs.obs_data_array_push_back(playlist_settings_array, playlist_value)

        obs.obs_data_set_array(settings, "playlist", playlist_settings_array)
        obs.obs_data_release(playlist_value)
        obs.obs_data_array_release(playlist_settings_array)
        obs.obs_source_update(vlc_source, settings)
        obs.obs_data_release(settings)

        team_name_rect_source = obs.obs_source_create_private("color_source", "%s_name_rect" % team, None)
        settings = obs.obs_source_get_settings(team_name_rect_source)
        obs.obs_data_set_int(settings, "width", 800)
        obs.obs_data_set_int(settings, "height", 70)
        obs.obs_data_set_int(settings, "color", 0xCD0000FF)
        obs.obs_source_update(team_name_rect_source, settings)
        obs.obs_data_release(settings)

        team_name_text_source = obs.obs_source_create_private("text_ft2_source_v2", "%s_name_text" % team, None)
        settings = obs.obs_source_get_settings(team_name_text_source)
        obs.obs_data_set_string(settings, "text", "LIVE: %s" % team_name)
        obs.obs_data_set_int(settings, "color1", 0xFF006300)
        obs.obs_data_set_int(settings, "color2", 0xFF006300)
        font = obs.obs_data_create()
        obs.obs_data_set_string(font, "face", "courier new")
        obs.obs_data_set_int(font, "size", 40)
        # Get color from settings
        print_source_settings(team_name_text_source)
        obs.obs_data_set_obj(settings, "font", font)
        obs.obs_data_release(font)
        obs.obs_source_update(team_name_text_source, settings)
        obs.obs_data_release(settings)

        vlc_source_sceneitem = obs.obs_scene_add(scene, vlc_source)
        team_name_rect_sceneitem = obs.obs_scene_add(scene, team_name_rect_source)
        team_name_text_sceneitem = obs.obs_scene_add(scene, team_name_text_source)

        obs.obs_sceneitem_group_add_item(group, team_name_text_sceneitem)
        obs.obs_sceneitem_group_add_item(group, team_name_rect_sceneitem)
        obs.obs_sceneitem_group_add_item(group, vlc_source_sceneitem)

        obs.obs_sceneitem_set_bounds_type(vlc_source_sceneitem, obs.OBS_BOUNDS_SCALE_INNER)
        obs.obs_sceneitem_set_bounds_alignment(vlc_source_sceneitem, 0)
        bounds = obs.vec2()
        bounds.x = 1920
        bounds.y = 1080
        obs.obs_sceneitem_set_bounds(vlc_source_sceneitem, bounds)

        obs.obs_sceneitem_set_bounds_alignment(team_name_rect_sceneitem, 0)
        pos = obs.vec2()
        pos.x = 1120
        pos.y = 870
        obs.obs_sceneitem_set_pos(team_name_rect_sceneitem, pos)

        pos = obs.vec2()
        pos.x = 1128
        pos.y = 884
        obs.obs_sceneitem_set_pos(team_name_text_sceneitem, pos)

        obs.obs_source_release(vlc_source)

        print(f"Added {team} to scene")

    # Generate clock bar
    # generate_clock_bar()


def debug(props, prop):
    global url
    global team_list

    for source in obs.obs_enum_sources():
        # print identifier and type of every source
        print(f"{obs.obs_source_get_name(source)}: {obs.obs_source_get_id(source)}")

# ------------------------------------------------------------

def script_description():
    return "Generate a scene with the current team list."

def script_update(settings):
    global url
    global team_list_path
    global team_list

    url = obs.obs_data_get_string(settings, "url")
    team_list_path = obs.obs_data_get_string(settings, "team_list_path")

    if team_list_path:
        # import csv reader and read from team_list_path
        import csv
        csv_reader = csv.reader(open(team_list_path, 'r', encoding='utf-8'), dialect=csv.excel)
        team_list = [[row[0], row[1]] for row in csv_reader]

    del team_list[0]

    print(team_list)


def script_defaults(settings):
    obs.obs_data_set_default_int(settings, "interval", 30)

def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(props, "url", "URL", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_path(props, "team_list_path", "Team List Path", obs.OBS_PATH_FILE,
                                "CSV Files (*.csv)", None)

    obs.obs_properties_add_button(props, "button", "Generate scene", generate_scene)
    obs.obs_properties_add_button(props, "debug", "Debug", debug)
    return props
