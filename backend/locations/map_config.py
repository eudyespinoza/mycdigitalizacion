from backoffice.integrations import resolved_configuration

OPENSTREETMAP_CONFIGURATION = {
    "provider": "openstreetmap",
    "google_maps_browser_key": "",
    "google_maps_map_id": "",
}


def resolve_map_configuration():
    configuration = resolved_configuration("geolocation")
    if not configuration or not configuration["enabled"]:
        return OPENSTREETMAP_CONFIGURATION.copy()
    public = configuration["public_config"]
    browser_key = str(configuration["secrets"].get("google_maps_browser_key") or "")
    if public.get("provider") != "google_maps" or not browser_key:
        return OPENSTREETMAP_CONFIGURATION.copy()
    return {
        "provider": "google_maps",
        "google_maps_browser_key": browser_key,
        "google_maps_map_id": str(public.get("google_maps_map_id") or ""),
    }
