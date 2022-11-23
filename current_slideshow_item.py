import obspython as obs
import time

from pathlib import Path

LOOP_INTERVAL = 200
NO_SOURCE_SELECTED = "--No Source Selected--"
slideshow_source_name = ""
text_source_name = ""

def script_description():
    return "Updates the selected text source with the file name of the currently shown image in the selected image slide show source"

def script_properties():
    props = obs.obs_properties_create()
    slideshow_src_list = obs.obs_properties_add_list(props, "slideshow_src", "Image Slideshow Source", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    text_src_list = obs.obs_properties_add_list(props, "text_src", "Text Source", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)

    sources = obs.obs_enum_sources()
    slideshow_sources = [NO_SOURCE_SELECTED]
    text_sources = [NO_SOURCE_SELECTED]
    for source in sources:
        if obs.obs_source_get_unversioned_id(source) == "slideshow":
            slideshow_sources.append(obs.obs_source_get_name(source))
        elif (obs.obs_source_get_unversioned_id(source) == "text_gdiplus" or
            obs.obs_source_get_unversioned_id(source) == "text_ft2_source"):
            text_sources.append(obs.obs_source_get_name(source))
    obs.source_list_release(sources)

    for	source_name in slideshow_sources:
        obs.obs_property_list_add_string(slideshow_src_list, source_name, source_name)
    for source_name in text_sources:
        obs.obs_property_list_add_string(text_src_list, source_name, source_name)

    return props

def script_update(settings):
    global slideshow_source_name
    global text_source_name
    slideshow_source_name = obs.obs_data_get_string(settings, "slideshow_src")
    text_source_name = obs.obs_data_get_string(settings, "text_src")

    if not slideshow_source_name or not text_source_name:
        obs.timer_remove(sync_text)
    else:
        obs.timer_remove(sync_text)
        obs.timer_add(sync_text, LOOP_INTERVAL)

def script_load(settings):
    obs.timer_add(sync_text, LOOP_INTERVAL)

def script_unload():
    obs.timer_remove(sync_text)

def sync_text():
    global slideshow_source_name
    global text_source_name

    if (slideshow_source_name == NO_SOURCE_SELECTED or
        text_source_name == NO_SOURCE_SELECTED):
        return

    slideshow_source = obs.obs_get_source_by_name(slideshow_source_name)
    if not slideshow_source or obs.obs_source_get_id(slideshow_source) != "slideshow":
        obs.obs_source_release(slideshow_source)
        return

    text_source = obs.obs_get_source_by_name(text_source_name)
    if (not text_source or
        not (
            obs.obs_source_get_unversioned_id(text_source) == "text_gdiplus" or
            obs.obs_source_get_unversioned_id(text_source) == "text_ft2_source"
            )
        ):
        obs.obs_source_release(text_source)
        return

    slideshow_source_settings = obs.obs_source_get_settings(slideshow_source)
    files_array = obs.obs_data_get_array(slideshow_source_settings, "files")
    ph = obs.obs_source_get_proc_handler(slideshow_source)
    cd = obs.calldata_create()
    obs.proc_handler_call(ph, "current_index", cd)
    obs.proc_handler_call(ph, "total_files", cd)
    current_index = obs.calldata_int(cd, "current_index")
    obs.calldata_destroy(cd)

    item_data = obs.obs_data_array_item(files_array, current_index)
    if item_data:
        file_path = obs.obs_data_get_string(item_data, "value")
    else:
        file_path = None
    obs.obs_data_release(item_data)
    obs.obs_data_array_release(files_array)

    if file_path:
        stripped_file_name = Path(file_path).stem

        new_settings = obs.obs_data_create()
        obs.obs_data_set_string(new_settings, "text", stripped_file_name)
        obs.obs_source_update(text_source, new_settings)

        obs.obs_data_release(new_settings)

    obs.obs_source_release(text_source)
    obs.obs_source_release(slideshow_source)
