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

def update_text():
    global url
    global interval
    global source_name

    source = obs.obs_get_source_by_name(source_name)
    if source is not None:
        try:
            with urllib.request.urlopen(url) as response:
                data = response.read()
                text = data.decode('utf-8')

                settings = obs.obs_data_create()
                obs.obs_data_set_string(settings, "text", text)
                obs.obs_source_update(source, settings)
                obs.obs_data_release(settings)

        except urllib.error.URLError as err:
            obs.script_log(obs.LOG_WARNING, "Error opening URL '" + url + "': " + err.reason)
            obs.remove_current_callback()

        obs.obs_source_release(source)


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
        # Create a group named "<team> group"
        group_name = team + " group"

        r = requests.get(f"{url}/user/{team}")
        if r.status_code != 200:
            print(f"Error getting user {team} info")
            continue
        ip = r.json()['ip_address']

        vlc_source = obs.obs_source_create_private("vlc_source", "%s source" % team, None)

        # Set vlc source playlist property to the team's playlist
        settings = obs.obs_source_get_settings(vlc_source)

        playlist_value = obs.obs_data_create()
        obs.obs_data_set_string(playlist_value, "value", f"http://{ip}:9090")
        obs.obs_data_set_bool(playlist_value, "selected", True)
        obs.obs_data_set_bool(playlist_value, "hidden", False)

        playlist_settings_array = obs.obs_data_array_create()
        obs.obs_data_array_push_back(playlist_settings_array, playlist_value)

        obs.obs_data_set_array(settings, "playlist", playlist_settings_array)

        # text_source = obs.obs_source_create_private("text_ft2_source_v2", "%s text" % team, None)
        # settings = obs.obs_source_get_settings(text_source)
        # obs.obs_data_set_string(settings, "text", team)

        group = obs.obs_scene_add_group(scene, group_name)
        obs.obs_sceneitem_group_add_item(group, obs.obs_scene_add(scene, vlc_source))
        # obs.obs_sceneitem_group_add_item(group, obs.obs_scene_add(scene, text_source))


        print(f"Added {team} to scene")


def debug(props, prop):
    global url
    global team_list

    for source in obs.obs_enum_sources():
        # print identifier and type of every source
        print(f"{obs.obs_source_get_name(source)}: {obs.obs_source_get_id(source)}")

    # Create a CFUNCTYPE of bool (*)(void *,obs_output_t *)

    # if obs.obs_enum_transition_types(0, byref(typename)):
    #     print(dir(typename))
    #     typename = typename.value

    # print("typename =", typename)

    # scene = obs.obs_scene_from_source(obs.obs_get_source_by_name(SCENE_NAME))
    # vlc_source = obs.obs_scene_find_source_recursive(scene, "backup1 group")
    # vlc_source = obs.obs_sceneitem_get_source(vlc_source)

    # print(obs.obs_source_is_hidden(vlc_source))

    # class obs_output_t(Structure):
    #     pass

    # class video_t(Structure):
    #     pass

    # class obs_encoder_t(Structure):
    #     pass

    # callback_t = CFUNCTYPE(c_bool, c_void_p, POINTER(obs_output_t))

    # g_obs_output_get_name = wrap("obs_output_get_name", c_char_p, [POINTER(obs_output_t)])
    # g_obs_output_set_preferred_size = \
    #     wrap("obs_output_set_preferred_size", None, [POINTER(obs_output_t), c_int, c_int])
    # g_obs_output_get_height = wrap("obs_output_get_height", c_uint32, [POINTER(obs_output_t)])
    # g_obs_output_get_video_encoder = \
    #     wrap("obs_output_get_video_encoder", POINTER(obs_encoder_t), [POINTER(obs_output_t)])
    # g_obs_output_video = wrap("obs_output_video", POINTER(video_t), [POINTER(obs_output_t)])


    # def callback(a, b):
    #     output = b.contents
    #     print(g_obs_output_get_name(output))
    #     if b"group" in g_obs_output_get_name(output):
    #         g_obs_output_set_preferred_size(output, 1920, 1080)
    #         print(g_obs_output_get_height(output))
    #         video = g_obs_output_get_video_encoder(output).contents
    #         print(video)
    #     return True

    # g_obs_enum_outputs = wrap("obs_enum_scenes", c_bool, [callback_t, c_void_p])
    # g_obs_enum_outputs(callback_t(callback), None)

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
        team_list = [team.replace("\n", "") for team in open(team_list_path, "r").readlines() if team.strip()]

def script_defaults(settings):
    obs.obs_data_set_default_int(settings, "interval", 30)

def script_properties():
    props = obs.obs_properties_create()

    obs.obs_properties_add_text(props, "url", "URL", obs.OBS_TEXT_DEFAULT)
    obs.obs_properties_add_path(props, "team_list_path", "Team List Path", obs.OBS_PATH_FILE,
                                "Text Files (*.txt)", None)

    obs.obs_properties_add_button(props, "button", "Generate scene", generate_scene)
    obs.obs_properties_add_button(props, "debug", "Debug", debug)
    return props
