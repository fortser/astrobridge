"""Declarative provider registry. Custom TAP services need no Python code."""
from copy import deepcopy

from .config import validate_url
from .errors import BridgeError

BUILTINS = {
    "gaia": {"label": "ESA Gaia", "kind": "tap", "url": "https://gea.esac.esa.int/tap-server/tap", "table": "gaiadr3.gaia_source", "ra_column": "ra", "dec_column": "dec", "columns": "source_id,ra,dec,parallax,parallax_error,pmra,pmdec,phot_g_mean_mag,ruwe", "release": "Gaia DR3"},
    "simbad": {"label": "CDS SIMBAD", "kind": "tap", "resolver": "simbad", "url": "https://simbad.cds.unistra.fr/simbad/sim-tap", "table": "basic", "ra_column": "ra", "dec_column": "dec", "columns": "main_id,ra,dec,otype", "release": "live database"},
    "vizier": {"label": "CDS VizieR", "kind": "tap", "url": "https://tapvizier.cds.unistra.fr/TAPVizieR/tap", "release": "specify catalog/table"},
    "exoplanet": {"label": "NASA Exoplanet Archive", "kind": "tap", "url": "https://exoplanetarchive.ipac.caltech.edu/TAP", "table": "pscomppars", "ra_column": "ra", "dec_column": "dec", "columns": "pl_name,hostname,ra,dec,pl_orbper,pl_rade,pl_bmasse", "release": "live pscomppars (composite parameters)"},
    "heasarc": {"label": "NASA HEASARC", "kind": "tap", "url": "https://heasarc.gsfc.nasa.gov/xamin/vo/tap", "release": "specify catalog/table"},
    "irsa": {"label": "NASA/IPAC IRSA", "kind": "tap", "url": "https://irsa.ipac.caltech.edu/TAP", "release": "specify catalog/table"},
    "cadc": {"label": "Canadian Astronomy Data Centre", "kind": "tap", "url": "https://ws.cadc-ccda.hia-iha.nrc-cnrc.gc.ca/argus", "release": "specify collection"},
    "registry": {"label": "VO Registry (GAVO RegTAP)", "kind": "tap", "url": "https://dc.g-vo.org/tap", "release": "live registry"},
    "mast": {"label": "MAST observations & products", "kind": "mast", "url": "https://mast.stsci.edu/api/v0/invoke"},
    "horizons": {"label": "JPL Horizons", "kind": "horizons", "url": "https://ssd.jpl.nasa.gov/api/horizons.api"},
    "ads": {"label": "NASA ADS literature", "kind": "ads", "url": "https://api.adsabs.harvard.edu/v1/search/query", "auth_env": "ADS_TOKEN"},
    "crossref": {"label": "Crossref DOI metadata", "kind": "crossref", "url": "https://api.crossref.org/works"},
    "arxiv": {"label": "arXiv preprints", "kind": "arxiv", "url": "https://export.arxiv.org/api/query"},
}


def services(settings):
    result = deepcopy(BUILTINS)
    for name, config in settings.services.items():
        if not isinstance(config, dict):
            raise BridgeError("config", "Описание сервиса должно быть объектом.")
        merged = {**result.get(name, {}), **config}
        if not merged.get("kind") or not merged.get("url"):
            raise BridgeError("config", f"Сервис {name}: нужны kind и url.")
        validate_url(merged["url"])
        from .util import reject_secrets
        reject_secrets({"url": merged["url"]})
        result[name] = merged
    return result


def prop(kind, description, **kwargs):
    return {"type": kind, "description": description, **kwargs}


RA = prop("number", "ICRS right ascension, degrees", minimum=0, exclusiveMaximum=360)
DEC = prop("number", "ICRS declination, degrees", minimum=-90, maximum=90)
RADIUS = prop("number", "Cone radius, degrees", exclusiveMinimum=0, maximum=180)
TEXT = lambda description: prop("string", description, minLength=1)


def spec(required, properties, example):
    return {"type": "object", "additionalProperties": False, "required": required, "properties": properties, "example": example}


OPERATIONS = {
    "tap.query": spec(["query"], {"query": TEXT("Read-only ADQL SELECT"), "async": prop("boolean", "Submit and poll UWS job", default=False)}, {"query": "SELECT TOP 10 source_id,ra,dec FROM gaiadr3.gaia_source"}),
    "tap.tables": spec([], {"contains": prop("string", "Substring of table name or description")}, {"contains": "gaia"}),
    "tap.columns": spec(["table"], {"table": TEXT("Exact TAP_SCHEMA table_name")}, {"table": "gaiadr3.gaia_source"}),
    "tap.cone": spec(["ra", "dec", "radius"], {"ra": RA, "dec": DEC, "radius": RADIUS, "table": TEXT("ADQL table identifier, quoted if necessary"), "ra_column": TEXT("RA column in degrees"), "dec_column": TEXT("DEC column in degrees"), "columns": TEXT("Comma-separated identifiers or *"), "async": prop("boolean", "Use async TAP", default=False)}, {"ra": 56.75, "dec": 24.12, "radius": 0.05}),
    "simbad.resolve": spec(["name"], {"name": TEXT("SIMBAD object identifier")}, {"name": "M31"}),
    "mast.cone": spec(["ra", "dec", "radius"], {"ra": RA, "dec": DEC, "radius": RADIUS, "page": prop("integer", "One-based result page", minimum=1, default=1)}, {"ra": 10.6847, "dec": 41.269, "radius": 0.02}),
    "mast.search": spec(["filters"], {"filters": prop("array", "MAST filters: paramName, values (+ freeText)", minItems=1, items={"type": "object", "required": ["paramName", "values"], "properties": {"paramName": TEXT("MAST column"), "values": {"type": "array"}, "freeText": {"type": "string"}, "separator": {"type": "string"}}, "additionalProperties": False}), "page": prop("integer", "One-based result page", minimum=1, default=1)}, {"filters": [{"paramName": "obs_collection", "values": ["JWST"]}, {"paramName": "dataRights", "values": ["PUBLIC"]}]}),
    "mast.products": spec(["obsid"], {"obsid": TEXT("One obsid or comma-separated obsids (not obs_id)"), "page": prop("integer", "One-based result page", minimum=1, default=1)}, {"obsid": "1000033356"}),
    "horizons.query": spec(["target", "center", "start", "stop", "step", "time_scale", "kind"], {"target": TEXT("Horizons COMMAND, e.g. 499"), "center": TEXT("Horizons CENTER, e.g. 500@399"), "start": TEXT("Start calendar time"), "stop": TEXT("Stop calendar time"), "step": TEXT("Output step, e.g. 1d"), "time_scale": prop("string", "Explicit Horizons time scale", enum=["UT", "TT", "TDB"]), "kind": prop("string", "Ephemeris type", enum=["vectors", "ephemerides", "elements"]), "corrections": prop("string", "Vector corrections", enum=["NONE", "LT", "LT+S"], default="NONE"), "ref_plane": prop("string", "Reference plane", enum=["FRAME", "ECLIPTIC"], default="FRAME"), "quantities": TEXT("Observer quantity codes, e.g. 1,9,20,23")}, {"target": "499", "center": "500@399", "start": "2026-01-01", "stop": "2026-01-03", "step": "1d", "time_scale": "TDB", "kind": "vectors", "corrections": "NONE"}),
    "literature.search": spec(["query"], {"query": TEXT("ADS/arXiv native query or Crossref free text"), "offset": prop("integer", "Zero-based offset", minimum=0, default=0)}, {"query": "exoplanet atmosphere"}),
    "vo.sia": spec(["ra", "dec", "size"], {"ra": RA, "dec": DEC, "size": prop("number", "SIA 1 image field size, degrees", exclusiveMinimum=0, maximum=180)}, {"ra": 10.6847, "dec": 41.269, "size": 0.1}),
    "vo.ssa": spec(["ra", "dec", "diameter"], {"ra": RA, "dec": DEC, "diameter": prop("number", "SSA search diameter, degrees", exclusiveMinimum=0, maximum=180)}, {"ra": 10.6847, "dec": 41.269, "diameter": 0.1}),
    "download": spec(["url"], {"url": TEXT("Public HTTP(S) URL or mast: URI"), "filename": TEXT("Output basename only"), "max_mb": prop("number", "Download cap in MiB (cannot exceed config cap)", exclusiveMinimum=0)}, {"url": "mast:JWST/product/example_cal.fits", "filename": "observation.fits"}),
}

REQUEST_SCHEMA = {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", "additionalProperties": False,
                  "required": ["service", "operation", "params"], "properties": {
                      "service": TEXT("Provider registry key"), "operation": {"enum": list(OPERATIONS)},
                      "params": {"type": "object"}, "limit": prop("integer", "Maximum returned rows / page size", minimum=1, maximum=100000, default=1000),
                      "cache": prop("boolean", "Reuse fresh public result", default=True), "release": TEXT("User-supplied data release/provenance label")}}


def schema():
    result = deepcopy(REQUEST_SCHEMA)
    result["properties"]["operation"]["enum"] = list(OPERATIONS)
    result["allOf"] = [{"if": {"properties": {"operation": {"const": name}}}, "then": {"properties": {"params": value}}} for name, value in OPERATIONS.items()]
    return result


def supports(service, operation):
    kind = service["kind"]
    return (operation == "download" or (operation.startswith("tap.") and kind == "tap")
            or (operation == "simbad.resolve" and service.get("resolver") == "simbad")
            or (operation.startswith("mast.") and kind == "mast")
            or (operation == "horizons.query" and kind == "horizons")
            or (operation == "literature.search" and kind in {"ads", "arxiv", "crossref"})
            or (operation == "vo.sia" and kind == "sia") or (operation == "vo.ssa" and kind == "ssa")
            or kind in EXTENSION_KINDS.get(operation, set()))


EXTENSION_KINDS = {}


def register_operation(name, params_schema, kinds):
    """Register before Bridge construction/CLI main; works with register_handler."""
    OPERATIONS[name] = params_schema
    EXTENSION_KINDS[name] = set(kinds)
