import obspython as obs
from pathlib import Path

NO_SOURCE_SELECTED = "--No Source Selected--"

slideshow_update_signals = [
    "media_next",
    "media_previous",
    "media_restart",
    "save", # Only for compatibility with OBS 28 that uses the OBS 29 image-source.dll
    "update",
]

slideshow_weak_source = None
text_weak_source = None
slideshow_source_name = ""
text_source_name = ""

def frontend_event_cb(event):
    if (event == obs.OBS_FRONTEND_EVENT_FINISHED_LOADING or
        event == obs.OBS_FRONTEND_EVENT_SCENE_COLLECTION_CHANGED):
        # Scripts are loaded before the sources are loaded, so force update after load
        script_update(None)
        obs.remove_current_callback()

def is_slideshow_source(source):
    return source and obs.obs_source_get_id(source) == "slideshow"

def is_text_source(source):
    if not source:
        return False
    return (obs.obs_source_get_unversioned_id(source) == "text_gdiplus" or
            obs.obs_source_get_unversioned_id(source) == "text_ft2_source")

def get_slideshow_current_index(slideshow_source):
    """Use the source proc handler to get the current index of the image slideshow,
    because the `cur_index` in the source settings is not updated when the next slide is shown
    but rather only when the source is saved."""
    ph = obs.obs_source_get_proc_handler(slideshow_source)
    cd = obs.calldata_create()
    obs.proc_handler_call(ph, "current_index", cd)
    current_index = obs.calldata_int(cd, "current_index")
    obs.calldata_destroy(cd)
    return current_index

def script_description():
    return ("Updates the selected text source with the file name of the currently shown image in the selected image slide show source."
            "<br>Due to scripting limitations, if you rename the sources that are selected, you have to reselect them.")

def refresh_lists(props, prop):
    slideshow_src_list = obs.obs_properties_get(props, "slideshow_src")
    text_src_list = obs.obs_properties_get(props, "text_src")
    obs.obs_property_list_clear(slideshow_src_list)
    obs.obs_property_list_clear(text_src_list)

    sources = obs.obs_enum_sources()
    slideshow_sources = [NO_SOURCE_SELECTED]
    text_sources = [NO_SOURCE_SELECTED]
    for source in sources:
        if is_slideshow_source(source):
            slideshow_sources.append(obs.obs_source_get_name(source))
        elif is_text_source(source):
            text_sources.append(obs.obs_source_get_name(source))
    obs.source_list_release(sources)

    for	source_name in slideshow_sources:
        obs.obs_property_list_add_string(slideshow_src_list, source_name, source_name)
    for source_name in text_sources:
        obs.obs_property_list_add_string(text_src_list, source_name, source_name)

    return True # Refresh properties

def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_list(props, "slideshow_src", "Image Slideshow Source", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_properties_add_list(props, "text_src", "Text Source", obs.OBS_COMBO_TYPE_LIST, obs.OBS_COMBO_FORMAT_STRING)
    obs.obs_properties_add_button(props, "refresh_list", "Refresh Source Lists", refresh_lists)

    refresh_lists(props, None)

    return props

def script_update(settings):
    global slideshow_weak_source
    global text_weak_source
    global slideshow_source_name
    global text_source_name

    new_slideshow_source_name = ""
    if settings: # If settings is None, the update is forced by `frontend_event_cb`
        new_slideshow_source_name = obs.obs_data_get_string(settings, "slideshow_src")
        text_source_name = obs.obs_data_get_string(settings, "text_src")

    # Disconnect previous callbacks
    if new_slideshow_source_name and new_slideshow_source_name != slideshow_source_name:
        slideshow_source = obs.obs_weak_source_get_source(slideshow_weak_source)
        if slideshow_source:
            slideshow_sh = obs.obs_source_get_signal_handler(slideshow_source)
            for signal in slideshow_update_signals:
                obs.signal_handler_disconnect(slideshow_sh, signal, sync_text)
            obs.obs_source_release(slideshow_source)
        slideshow_source_name = new_slideshow_source_name

    obs.obs_weak_source_release(slideshow_weak_source)
    obs.obs_weak_source_release(text_weak_source)
    slideshow_weak_source = None
    text_weak_source = None

    if (slideshow_source_name == NO_SOURCE_SELECTED or
        text_source_name == NO_SOURCE_SELECTED):
        return

    slideshow_source = obs.obs_get_source_by_name(slideshow_source_name)
    text_source = obs.obs_get_source_by_name(text_source_name)

    if is_slideshow_source(slideshow_source) and is_text_source(text_source):
        slideshow_sh = obs.obs_source_get_signal_handler(slideshow_source)
        text_source_sh = obs.obs_source_get_signal_handler(text_source)
        for signal in slideshow_update_signals:
            obs.signal_handler_connect(slideshow_sh, signal, sync_text)

        # Weak references let us keep a reference in a global variable, without
        # preventing the source from being destroyed.
        slideshow_weak_source = obs.obs_source_get_weak_source(slideshow_source)
        text_weak_source = obs.obs_source_get_weak_source(text_source)
    obs.obs_source_release(slideshow_source)
    obs.obs_source_release(text_source)

    sync_text()

def script_load(settings):
    obs.obs_frontend_add_event_callback(frontend_event_cb)

def script_unload():
    obs.obs_weak_source_release(slideshow_weak_source)
    obs.obs_weak_source_release(text_weak_source)

def sync_text(calldata=None):
    global slideshow_weak_source
    global text_weak_source

    slideshow_source = obs.obs_weak_source_get_source(slideshow_weak_source)
    text_source = obs.obs_weak_source_get_source(text_weak_source)
    if not slideshow_source or not text_source:
        obs.obs_source_release(slideshow_source)
        obs.obs_source_release(text_source)
        return

    slideshow_source_settings = obs.obs_source_get_settings(slideshow_source)
    files_array = obs.obs_data_get_array(slideshow_source_settings, "files")
    current_index = get_slideshow_current_index(slideshow_source)
    item_data = obs.obs_data_array_item(files_array, current_index)
    file_path = obs.obs_data_get_string(item_data, "value")
    obs.obs_data_release(item_data)
    obs.obs_data_array_release(files_array)
    obs.obs_data_release(slideshow_source_settings)

    if file_path:
        stripped_file_name = Path(file_path).stem

        new_settings = obs.obs_data_create()
        obs.obs_data_set_string(new_settings, "text", stripped_file_name)
        obs.obs_source_update(text_source, new_settings)

        obs.obs_data_release(new_settings)

    obs.obs_source_release(slideshow_source)
    obs.obs_source_release(text_source)
