import obspython as obs
import urllib.request
import urllib.error
import requests
from contextlib import contextmanager, ExitStack

url         = ""
team_list_path = ""
team_list = []

SCENE_NAME = "Team View"
VLC_SOURCE_ID = "vlc_source"

# ------------------------------------------------------------
# Helper functions

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

        group = obs.obs_scene_add_group(scene, group_name)
        obs.obs_sceneitem_group_add_item(group, obs.obs_scene_add(scene, vlc_source))

        print(f"Added {team} to scene")


def debug(props, prop):
    global url
    global team_list

    scene = obs.obs_scene_from_source(obs.obs_get_source_by_name(SCENE_NAME))
    vlc_source = obs.obs_scene_find_source_recursive(scene, "final01 source")
    vlc_source = obs.obs_sceneitem_get_source(vlc_source)
    print(vlc_source)
    settings = obs.obs_source_get_settings(vlc_source)
    psettings = obs.obs_source_get_private_settings(vlc_source)
    dsettings = obs.obs_data_get_defaults(settings)
    pdsettings = obs.obs_data_get_defaults(psettings)

    playlist_value = obs.obs_data_create()
    obs.obs_data_set_string(playlist_value, "value", "http://")
    obs.obs_data_set_bool(playlist_value, "selected", False)
    obs.obs_data_set_bool(playlist_value, "hidden", False)

    print(obs.obs_data_array_push_back(obs.obs_data_get_array(settings, "playlist"), playlist_value))

    print("[---------- settings ----------")
    print(obs.obs_data_get_json(settings))
    # print("---------- private_settings ----------")
    # print(obs.obs_data_get_json(psettings))
    # print("---------- default settings for this source type ----------")
    # print(obs.obs_data_get_json(dsettings))
    # print("---------- default private settings for this source type ----------")
    # print(obs.obs_data_get_json(pdsettings))

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
