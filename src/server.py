#!/usr/bin/env python2.7
# -*- coding: utf-8 -*-

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
#                                                                       #
#   MapServer REST API is a python wrapper around MapServer which       #
#   allows to manipulate a mapfile in a RESTFul way. It has been        #
#   developped to match as close as possible the way the GeoServer      #
#   REST API acts.                                                      #
#                                                                       #
#   Copyright (C) 2011-2013 Neogeo Technologies.                        #
#                                                                       #
#   This file is part of MapServer Rest API.                            #
#                                                                       #
#   MapServer Rest API is free software: you can redistribute it        #
#   and/or modify it under the terms of the GNU General Public License  #
#   as published by the Free Software Foundation, either version 3 of   #
#   the License, or (at your option) any later version.                 #
#                                                                       #
#   MapServer Rest API is distributed in the hope that it will be       #
#   useful, but WITHOUT ANY WARRANTY; without even the implied warranty #
#   of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the     #
#   GNU General Public License for more details.                        #
#                                                                       #
# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #

import web
import json
import urlparse

import mralogs
import logging

import mapfile

import webapp
from webapp import HTTPCompatible, urlmap, get_data

import tools
from tools import get_mapfile, get_mapfile_workspace, get_config, href

from pyxml import Entries

import os.path

mralogs.setup(get_config("logging")["level"], get_config("logging")["file"],
              get_config("logging")["format"])

class index(object):
    def GET(self, format):
        return "This is MRA."


class mapfiles(object):
    @HTTPCompatible()
    def GET(self, format):
        mapfiles = []
        for path in tools.get_mapfile_paths():
            try:
                mf = mapfile.Mapfile(path)
            except IOError, OSError:
                continue
            filename = mf.filename.replace(".map", "")
            mapfiles.append({
                "map_name": mf.ms.name,
                "map_full_path": mf.path,

                "workspaces": href("%s/maps/%s/workspaces.%s" % (web.ctx.home, filename, format)),
                "layers": href("%s/maps/%s/layers.%s" % (web.ctx.home, filename, format)),
                "layergroups": href("%s/maps/%s/layergroups.%s" % (web.ctx.home, filename, format)),
                "styles": href("%s/maps/%s/styles.%s" % (web.ctx.home, filename, format)),
                "map_file": href("%s/maps/%s.%s" % (web.ctx.home, filename, format)),

                "wms_capabilities": href("%smap=%s&REQUEST=GetCapabilities&VERSION=%s&SERVICE=WMS" % (
                            get_config("mapserver")["url"], mf.path, get_config("mapserver")["wms_version"])),
                "wfs_capabilities": href("%smap=%s&REQUEST=GetCapabilities&VERSION=%s&SERVICE=WFS" % (
                            get_config("mapserver")["url"], mf.path, get_config("mapserver")["wfs_version"])),
                "wcs_capabilities": href("%smap=%s&REQUEST=GetCapabilities&VERSION=%s&SERVICE=WCS" % (
                            get_config("mapserver")["url"], mf.path, get_config("mapserver")["wcs_version"])),
              })

        return {"mapfiles": mapfiles}

    def POST(self, map_name):
        data = get_data()

        # TODO: Create mapfile
        raise NotImplemented()
        webapp.Created("%s/maps/%s" % (web.ctx.home, map_name))


class named_mapfile(object):
    @HTTPCompatible(authorize=["map"], default="html")
    def GET(self, map_name, format, *args, **kwargs):

        mf = get_mapfile(map_name)
        with open(mf.path, "r") as f:
            data = f.read()
        return {"mapfile": data} if format != "map" else data


class workspaces(object):
    @HTTPCompatible()
    def GET(self, map_name, format, *args, **kwargs):
        mf = get_mapfile(map_name)
        return {"workspaces": [{
                    "name": ws.name,
                    "href": "%s/maps/%s/workspaces/%s.%s" % (web.ctx.home, map_name, ws.name, format)
                    } for ws in mf.iter_workspaces()]
                }


class workspace(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)
        return {"workspace": ({
                    "name": ws.name,
                    "dataStores":
                        href("%s/maps/%s/workspaces/%s/datastores.%s" % (web.ctx.home, map_name, ws.name, format)),
                    "coverageStores":
                        href("%s/maps/%s/workspaces/%s/coveragestores.%s" % (web.ctx.home, map_name, ws.name, format)),
                    "wmsStores":
                        href("%s/maps/%s/workspaces/%s/wmsstores.%s" % (web.ctx.home, map_name, ws.name, format))
                    })
                }


class datastores(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, format, *args, **kwargs):
        mf, ws = get_mapfile_workspace(map_name, ws_name)
        return {"datastores": [{
                    "name": ds_name,
                    "href": "%s/maps/%s/workspaces/%s/datastores/%s.%s" % (
                        web.ctx.home, map_name, ws.name, ds_name, format)
                    } for ds_name in ws.iter_datastore_names()]
                }

    def POST(self, map_name, ws_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="datastore", mandatory=["name", "connectionParameters"])
        ds_name = data.pop("name")

        with webapp.mightConflict("datastore", workspace=ws_name):
            ws.create_datastore(ds_name, data)
        ws.save()

        webapp.Created("%s/maps/%s/workspaces/%s/datastores/%s" % (
                web.ctx.home, map_name, ws_name, ds_name))


class datastore(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, ds_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        with webapp.mightNotFound("datastore", workspace=ws_name):
            info = ws.get_datastore_info(ds_name)
        info["href"] = "%s/maps/%s/workspaces/%s/datastores/%s/featuretypes.%s" % (
            web.ctx.home, map_name, ws.name, ds_name, format)
        info["ConnectionParameters"] = Entries(info["ConnectionParameters"], tag_name="entry", key_name="key")
        return {"datastore": info}

    def PUT(self, map_name, ws_name, ds_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="datastore", mandatory=["name", "connectionParameters"], forbidden=["href"])
        if ds_name != data.pop("name"):
            raise webapp.Forbidden("Can't change the name of a datastore.")

        with webapp.mightNotFound("datastore", workspace=ws_name):
            ws.update_datastore(ds_name, data)
        ws.save()

    def DELETE(self, map_name, ws_name, ds_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        with webapp.mightNotFound("datastore", workspace=ws_name):
            ws.delete_datastore(ds_name)
        ws.save()


class featuretypes(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, ds_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)
        return {"featuretypes": [{
                    "name": ft.name,
                    "href": "%s/maps/%s/workspaces/%s/datastores/%s/featuretypes/%s.%s" % (
                        web.ctx.home, map_name, ws.name, ds_name, ft.name, format)
                    } for ft in ws.iter_featuretypes(ds_name)]
                }

    def POST(self, map_name, ws_name, ds_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="featuretype", mandatory=["name"])
        with webapp.mightConflict("featuretype", datastore=ds_name):
            ws.create_featuretype(data["name"], ds_name, data)
        ws.save()

        webapp.Created("%s/maps/%s/workspaces/%s/datastores/%s/featuretypes/%s.%s" % (
                web.ctx.home, map_name, ws.name, ds_name, data["name"], format))


class featuretype(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, ds_name, ft_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)
        with webapp.mightNotFound("featuretype", datastore=ds_name):
            ft = ws.get_featuretype(ft_name, ds_name)

        ds = ws.get_datastore(ds_name)
        with webapp.mightNotFound("datastore entry", datastore=ds_name):
            dsft = ds[ft_name]

        extent = dsft.get_extent()
        latlon_extent = dsft.get_latlon_extent()

        return {"featuretype": ({
                    "name": ft.name,
                    "nativeName": ft.name,
                    "namespace": {
                        "name": map_name,
                        "href": "%s/maps/%s/namespaces/%s.%s" % (web.ctx.home, map_name, ws_name, format)
                        },
                    "title": ft.get_metadata("title", ft.name),
                    "abstract": ft.get_metadata("abstract", None),
                    "keywords": ft.get_metadata("keywords", []),
                    "srs": dsft.get_projection(),
                    "nativeCRS": dsft.get_native(),
                    "attributes": [{
                            "name": f.get_name(),
                            "minOccurs": 0 if f.is_nullable() else 1,
                            "maxOccurs": 1,
                            "nillable": f.is_nullable(),
                            "binding": f.get_type_name(),
                            "length": f.get_width(),
                            } for f in dsft.iterfields()],
                    "nativeBoundingBox": {
                        "minx": extent.minX(),
                        "miny": extent.minY(),
                        "maxx": extent.maxX(),
                        "maxy": extent.maxY(),
                        },
                    "latLonBoundingBox": {
                        "minx": latlon_extent.minX(),
                        "miny": latlon_extent.minY(),
                        "maxx": latlon_extent.maxX(),
                        "maxy": latlon_extent.maxY(),
                        "crs": "EPSG:4326",
                        },
                    "projectionPolicy": None,
                    "enabled": True,
                    "store": {
                        "name": ds_name,
                        "href": "%s/maps/%s/workspaces/%s/datastores/%s.%s" % (
                            web.ctx.home, map_name, ws_name, ds_name, format)
                        },
                    "maxFeatures": 0,
                    "numDecimals": 0,
                    })
                }

    def PUT(self, map_name, ws_name, ds_name, ft_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="featuretype", mandatory=["name"])
        if ft_name != data["name"]:
            raise webapp.Forbidden("Can't change the name of a featuretype.")

        with webapp.mightNotFound("featuretype", datastore=ds_name):
            ws.update_featuretype(ft_name, ds_name, data)
        ws.save()

    def DELETE(self, map_name, ws_name, ds_name, ft_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        with webapp.mightNotFound("featuretype", datastore=ds_name):
            ws.delete_featuretype(ft_name, ds_name)
        ws.save()


class coveragestores(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        return {"coveragestores": [{
                    "name": cs_name,
                    "href": "%s/maps/%s/workspaces/%s/coveragestores/%s.%s" % (
                        web.ctx.home, map_name, ws.name, cs_name, format)
                    } for cs_name in ws.iter_coveragestore_names()]
                }

    def POST(self, map_name, ws_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="coveragestore", mandatory=["name", "connectionParameters"])
        cs_name = data.pop("name")

        with webapp.mightConflict("coveragestore", workspace=ws_name):
            ws.create_coveragestore(cs_name, data)
        ws.save()

        webapp.Created("%s/maps/%s/workspaces/%s/coveragestores/%s" % (
                web.ctx.home, map_name, ws_name, cs_name))


class coveragestore(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, cs_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        info = ws.get_coveragestore_info(cs_name)
        info["href"] = "%s/maps/%s/workspaces/%s/coveragestores/%s/coverages.%s" % (
            web.ctx.home, map_name, ws.name, cs_name, format)
        info["ConnectionParameters"] = Entries(info["ConnectionParameters"], tag_name="entry", key_name="key")
        return {"coveragestore": info}

    def PUT(self, map_name, ws_name, cs_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="coveragestore", mandatory=["name", "type", "connectionParameters"], forbidden=["href"])
        if cs_name != data.pop("name"):
            raise webapp.Forbidden("Can't change the name of a coveragestore.")

        with webapp.mightNotFound("coveragestore", workspace=ws_name):
            ws.update_coveragestore(cs_name, data)
        ws.save()

    def DELETE(self, map_name, ws_name, cs_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        with webapp.mightNotFound("coveragestore", workspace=ws_name):
            ws.delete_coveragestore(cs_name)
        ws.save()


class coverages(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, cs_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)
        return {"coverages": [{
                    "name": c.name,
                    "href": "%s/maps/%s/workspaces/%s/coveragestores/%s/coverages/%s.%s" % (
                        web.ctx.home, map_name, ws.name, cs_name, c.name, format)
                    } for c in ws.iter_coverages(cs_name)]
                }

    def POST(self, map_name, ws_name, cs_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="coverage", mandatory=["name"])

        with webapp.mightConflict("coverage", coveragestore=cs_name):
            ws.create_coverage(data["name"], cs_name, data)
        ws.save()

        webapp.Created("%s/maps/%s/workspaces/%s/coveragestores/%s/coverages/%s.%s" % (
                web.ctx.home, map_name, ws.name, cs_name, data["name"], format))


class coverage(object):
    @HTTPCompatible()
    def GET(self, map_name, ws_name, cs_name, c_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)
        c = ws.get_coverage(c_name, cs_name)

        with webapp.mightNotFound("coveragestore", workspace=ws_name):
            cs = ws.get_coveragestore(cs_name)

        extent = cs.get_extent()
        latlon_extent = cs.get_latlon_extent()

        return {"coverage": ({
                    "name": c.name,
                    "nativeName": c.name,
                    "namespace": {
                        "name": map_name,
                        "href": "%s/maps/%s/namespaces/%s.%s" % (web.ctx.home, map_name, ws_name, format)
                        },
                    "title": c.get_metadata("title", c.name),
                    "abstract": c.get_metadata("abstract", None),
                    "keywords": c.get_metadata("keywords", []),
                    "srs": cs.get_projection(),
                    "nativeBoundingBox": {
                        "minx": extent.minX(),
                        "miny": extent.minY(),
                        "maxx": extent.maxX(),
                        "maxy": extent.maxY(),
                        },
                    "latLonBoundingBox":{
                        "minx": latlon_extent.minX(),
                        "miny": latlon_extent.minY(),
                        "maxx": latlon_extent.maxX(),
                        "maxy": latlon_extent.maxY(),
                        "crs": "EPSG:4326"
                        },
                    "projectionPolicy": None,
                    "enabled": True,
                    "store": {
                        "name": cs_name,
                        "href": "%s/maps/%s/workspaces/%s/coveragestores/%s.%s" % (
                            web.ctx.home, map_name, ws_name, cs_name, format)
                        }
                    })
                }

    def PUT(self, map_name, ws_name, cs_name, c_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        data = get_data(name="coverage", mandatory=["name"])
        if c_name != data["name"]:
            raise webapp.Forbidden("Can't change the name of a coverage.")

        with webapp.mightNotFound("coverage", coveragestore=cs_name):
            ws.update_coverage(c_name, cs_name, data)
        ws.save()

    def DELETE(self, map_name, ws_name, cs_name, c_name, format):
        mf, ws = get_mapfile_workspace(map_name, ws_name)

        with webapp.mightNotFound("coverage", coveragestore=cs_name):
            ws.delete_coverage(c_name, cs_name)
        ws.save()


class files(object):

    def PUT(self, map_name, ws_name, st_type, st_name, f_type, format):
        import zipfile

        mf, ws = get_mapfile_workspace(map_name, ws_name)

        # TODO: According to geoserv's examples we might have to handle
        # directories as well as files, in that case we want to upload
        # all the files from the directory.

        # Lets first try to get the file.
        if f_type == "file":
            # Check if zip or not...
            data = web.data()
        elif f_type == "url":
            raise NotImplemented()
        elif f_type == "external":
            raise NotImplemented()

        # Now we make sure the store exists.
        with webapp.mightNotFound(message="Store {exception} does not exist "
                                  "and automatic creation is not yet suported."):
            ws.get_store_info(st_type, st_name)
            # TODO: Create the store if it does not exist.

        # Then we store the file.
        ext = web.ctx.env.get('CONTENT_TYPE', '').split("/")[-1]
        path = tools.mk_st_data_path(ws_name, st_type, st_name, st_name + (".%s" % ext) if ext else "")
        with open(path, "w") as f:
            f.write(data)

        # We also unzip it if its ziped.
        ctype = web.ctx.env.get('CONTENT_TYPE', None)
        if ctype == "application/zip":
            z = zipfile.ZipFile(path)
            for f in z.namelist():
                fp = tools.mk_st_data_path(ws_name, st_type, st_name, f)

                # If the file has the correct target we might want it.
                if format and fp.endswith(format) and not tools.is_hidden(fp):
                    path = fp

                z.extract(f, path=tools.get_st_data_path(ws_name, st_type, st_name))

        # Set new connection parameters:
        ws.update_store(st_type, st_name, {"ConnectionParameters":{"path":path}})
        ws.save()

        # Finally we might have to configure it.
        params = web.input(configure="none")
        if params.configure == "first":
            raise NotImplemented()
        elif params.configure == "none":
            pass
        elif params.configure == "all":
            raise NotImplemented()
        else:
            raise webapp.BadRequest(message="configure must be one of first, none or all.")


class styles(object):
    @HTTPCompatible()
    def GET(self, map_name, format):
        mf = get_mapfile(map_name)

        return {"styles": [{
                    "name": os.path.basename(os.path.basename(s_name)),
                    "href": "%s/maps/%s/styles/%s.%s" % (web.ctx.home, map_name, os.path.basename(s_name), format)
                    } for s_name in tools.iter_styles(mf)]
                }

    def POST(self, map_name, format):
        mf = get_mapfile(map_name)

        params = web.input(name=None)
        name = params.name
        if name == None:
            raise webapp.BadRequest(message="no parameter 'name' given.")
        with webapp.mightConflict("style", mapfile=map_name):
            if name in tools.iter_styles(mf):
                raise webapp.KeyExists(name)

        data = web.data()
        path = tools.mk_style_path(name)

        with open(path, "w") as f:
            f.write(data)


class style(object):
    @HTTPCompatible(authorize=["sld"])
    def GET(self, map_name, s_name, format):
        mf = get_mapfile(map_name)

        if format == "sld":
            # We look for styles on disk and in the mapfiles.
            try:
                return open(tools.get_style_path(s_name)).read()
            except IOError, OSError:
                with webapp.mightNotFound("style", mapfile=map_name):
                    return mf.get_style_sld(s_name)

        # We still need to check if this actually exists...
        with webapp.mightNotFound("style", mapfile=map_name):
            if not os.path.exists(tools.get_style_path(s_name)) and not s_name in mf.iter_styles():
                raise KeyError(s_name)

        return {
            "name": s_name,
            "sldVersions": [
                #TODO: Return the correct value...
                "1.0.0"
                ],
            "filename": s_name + ".sld",
            "href": "%s/maps/%s/styles/%s.sld" % (web.ctx.home, map_name, s_name)
            }

    def PUT(self, map_name, s_name, format):
        path = tools.get_style_path(s_name)
        try:
            os.remove(path)
        except OSError:
            mf = get_mapfile(map_name)
            if s_name in mf.iter_styles():
                raise webapp.NotImplemented(message="Updating manually added styles is not implemented.")
            else:
                raise webapp.NotFound("style '%s' not found in mapfile '%s'." % (s_name, map_name))

        data = web.data()
        with open(path, "w") as f:
            f.write(data)


    def DELETE(self, map_name, s_name, format):

        path = tools.get_style_path(s_name)
        try:
            os.remove(path)
        except OSError:
            mf = get_mapfile(map_name)
            if s_name in mf.iter_styles():
                raise webapp.NotImplemented(message="Deleting manually added styles is not implemented.")
            else:
                raise webapp.NotFound("style '%s' not found in mapfile '%s'." % (s_name, map_name))


class layers(object):
    @HTTPCompatible()
    def GET(self, map_name, format):
        mf = get_mapfile(map_name)
        return {"layers": [{
                    "id": layer.ms.index,
                    "name": layer.ms.name,
                    "type": layer.get_type_name(),
                    "href": "%s/maps/%s/layers/%s.%s" % (web.ctx.home, map_name, layer.ms.name, format),
                    # Do we implement styler or not ?
                    # "styler_href": "%s/styler/?namespace=%s&layer=%s" % (
                    #     web.ctx.home, map_name, layer.name),
                    } for layer in mf.iter_layers()]
                }

    def POST(self, map_name, format):
        data = get_data(name="layer", mandatory=["name", "resource"])

        l_name = data.pop("name")
        l_enabled = data.pop("enabled", True)

        # This means we can have one mapfile for each workspace
        # and if eveything uses urls it should work *almost* as is.
        url = urlparse.urlparse(data["resource"]["href"])
        if url.path.startswith(web.ctx.homepath):
            path = url.path[len(web.ctx.homepath):]
        else:
            raise webapp.BadRequest(message="Resource href is not handled by MRA.")

        _, _, map_name, _, ws_name, st_type, st_name, r_type, r_name = path.split("/")

        r_name = r_name.rsplit(".", 1)[0]

        mf, ws = get_mapfile_workspace(map_name, ws_name)
        with webapp.mightNotFound(r_type, workspace=ws_name):
            try:
                model = ws.get_model(r_name, r_type[:-1], st_name)
            except ValueError:
                webapp.NotFound("Invalid layer model '%s'" % r_type[:-1])

        with webapp.mightConflict("layer", mapfile=map_name):
            model.create_layer(ws, mf, l_name, l_enabled)
        mf.save()

        webapp.Created("%s/maps/%s/layers/%s" % (web.ctx.home, map_name, l_name))


class layer(object):
    @HTTPCompatible()
    def GET(self, map_name, l_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layer", mapfile=map_name):
            layer = mf.get_layer(l_name)

        data_type, store_type = {
            "featuretype": ("featuretype", "datastore"),
            "coverage": ("coverage", "coveragestore")
            }[layer.get_mra_metadata("type")]

        return {"layer" : ({
                    "id": layer.ms.index,
                    "name": l_name,
                    "path": "/",
                    "type": layer.get_type_name(),
                    "defaultStyle": {
                        "name": layer.ms.classgroup,
                        "href": "%s/maps/%s/styles/%s.%s" % (web.ctx.home, map_name, layer.ms.classgroup, format),
                        },
                    "styles": [{
                            "name": s_name,
                            "href": "%s/maps/%s/styles/%s.%s" % (web.ctx.home, map_name, s_name, format),
                            } for s_name in layer.iter_styles()],
                    "resources": {
                        "name": layer.get_mra_metadata("name"),
                        "@class": data_type,
                        "href": "%s/maps/%s/workspaces/%s/%ss/%s/%ss/%s.%s" % (
                            web.ctx.home, map_name, layer.get_mra_metadata("workspace"),
                            store_type, layer.get_mra_metadata("storage"), data_type, layer.get_mra_metadata("name"), format),
                        },
                    "enabled": bool(layer.ms.status),
                    "attributions": {"logoWidth": 10, "logoHeight": 10}
                    })
                }

    def PUT(self, map_name, l_name, format):
        mf = get_mapfile(map_name)

        data = get_data(name="layer", mandatory=["name", "resource"])
        if l_name != data.pop("name"):
            raise webapp.Forbidden("Can't change the name of a layer.")

        l_enabled = data.pop("enabled", True)

        # This means we can have one mapfile for each workspace
        # and if eveything uses urls it should work *almost* as is.
        r_href = data["resource"]["href"]
        _, _, map_name, _, ws_name, st_type, st_name, r_type, r_name = r_href.split("/")
        r_name = r_name.rsplit(".", 1)[0]

        ws = mf.get_workspace(ws_name)
        with webapp.mightNotFound(r_type, workspace=ws_name):
            try:
                model = ws.get_model(r_name, st_type, st_name)
            except ValueError:
                webapp.NotFound("Invalid layer model '%s'" % st_type)

        with webapp.mightNotFound("layer", mapfile=map_name):
            model.configure_layer(ws, mf, l_name, l_enabled)
        mf.save()


    def DELETE(self, map_name, l_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layer", mapfile=map_name):
            mf.delete_layer(l_name)
        mf.save()


class layerstyles(object):
    @HTTPCompatible()
    def GET(self, map_name, l_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layer", mapfile=map_name):
            layer = mf.get_layer(l_name)

        if format == "sld":
            return layer.getSLD()

        return {"styles": [{
                    "name": s_name,
                    "href": "%s/maps/%s/styles/%s.%s" % (web.ctx.home, map_name, s_name, format),
                    } for s_name in layer.iter_styles()],
                }

    def POST(self, map_name, l_name, format):
        data = get_data(name="style", mandatory=["resource"])

        url = urlparse.urlparse(data["resource"]["href"])
        if url.path.startswith(web.ctx.homepath):
            path = url.path[len(web.ctx.homepath):]
        else:
            raise webapp.BadRequest(message="Resource href (%s) is not handled by MRA." % url.path)

        _, _, map_name, _, s_name = path.split("/")

        s_name = s_name.rsplit(".", 1)[0]

        # Get the new style.
        mf = get_mapfile(map_name)

        try:
            style = open(tools.get_style_path(s_name)).read()
        except IOError, OSError:
            with webapp.mightNotFound("style", mapfile=map_name):
                style = mf.get_style_sld(s_name)

        with webapp.mightNotFound("layer", mapfile=map_name):
            layer = mf.get_layer(l_name)

        layer.add_style_sld(mf, s_name, style)
        mf.save()

        webapp.Created("%s/maps/%s/layers/%s/layerstyles/%s" % (web.ctx.home, map_name, l_name, s_name))


class layerstyle(object):
    def DELETE(self, map_name, l_name, s_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layer", mapfile=map_name):
            layer = mf.get_layer(l_name)
        with webapp.mightNotFound("style", layer=l_name):
            layer.remove_style(s_name)
        mf.save()


class layerfields(object):
    @HTTPCompatible()
    def GET(self, map_name, l_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layer", mapfile=map_name):
            layer = mf.get_layer(l_name)

        return {"fields": [{
                    "name": layer.get_metadata("gml_%s_alias" % field, None),
                    "fieldtype": layer.get_metadata("gml_%s_type" % field, None),
                    } for field in layer.iter_fields(mf)]
                }


class layergroups(object):
    @HTTPCompatible()
    def GET(self, map_name, format):
        mf = get_mapfile(map_name)

        return {"layergroups" : [{
                    "name": lg.name,
                    "href": "%s/maps/%s/layergroups/%s.%s" % (web.ctx.home, map_name, lg.name, format)
                    } for lg in mf.iter_layergroups()]
                }

    def POST(self, map_name, format):
        mf = get_mapfile(map_name)

        data = get_data(name="layergroup", mandatory=["name"])
        lg_name = data.pop("name")
        layers = data.pop("layers", [])

        with webapp.mightConflict("layergroup", mapfile=map_name):
            lg = mf.create_layergroup(lg_name, data)
        lg.add(*layers)

        mf.save()

        webapp.Created("%s/maps/%s/layergroups/%s" % (web.ctx.home, map_name, lg.name))


class layergroup(object):

    @HTTPCompatible()
    def GET(self, map_name, lg_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layergroup", mapfile=map_name):
            lg = mf.get_layergroup(lg_name)

        extent = lg.get_extent()

        return {"layergroup": ({
                    "name": lg.name,
                    "layers": [{
                            "id": layer.ms.index,
                            "name": layer.ms.name,
                            "type": layer.ms.type,
                            "href": "%s/maps/%s/layers/%s.%s" % (web.ctx.home, map_name, layer.ms.name, format),
                            # Do we implement styler or not ?
                            # "styler_href": "%s/styler/?namespace=%s&layer=%s" % (
                            #     web.ctx.home, map_name, layer.name),
                            } for layer in lg.iter_layers()],
                    "bounds": {
                        "minx": extent.minX(),
                        "miny": extent.minY(),
                        "maxx": extent.maxX(),
                        "maxy": extent.maxY(),
                        },
                    })
                }

    def PUT(self, map_name, lg_name, format):
        mf = get_mapfile(map_name)

        with webapp.mightNotFound("layergroup", mapfile=map_name):
            lg = mf.get_layergroup(lg_name)

        data = get_data(name="layergroup", mandatory=["name"])
        if lg_name != data.pop("name"):
            raise webapp.Forbidden("Can't change the name of a layergroup.")

        layers = data.pop("layers", [])
        lg.clear()
        lg.add(*layers)

        mf.save()

    def DELETE(self, map_name, lg_name, format):
        mf = get_mapfile(map_name)
        with webapp.mightNotFound("layergroup", mapfile=map_name):
            mf.delete_layergroup(lg_name)


# Index:
urlmap(index, "")

# Styler: TODO
#urlmap(styler, format = False)

# Mapfiles:
urlmap(mapfiles, "maps")
urlmap(named_mapfile, "maps", ())

# Workspaces:
urlmap(workspaces, "maps", (), "workspaces")
urlmap(workspace, "maps", (), "workspaces", ())

# Datastores:
urlmap(datastores, "maps", (), "workspaces", (), "datastores")
urlmap(datastore, "maps", (), "workspaces", (), "datastores", ())
# Featuretypes:
urlmap(featuretypes, "maps", (), "workspaces", (), "datastores", (), "featuretypes")
urlmap(featuretype, "maps", (), "workspaces", (), "datastores", (), "featuretypes", ())

# Coveragestores:
urlmap(coveragestores, "maps", (), "workspaces", (), "coveragestores")
urlmap(coveragestore, "maps", (), "workspaces", (), "coveragestores", ())
# Coverages:
urlmap(coverages, "maps", (), "workspaces", (), "coveragestores", (), "coverages")
urlmap(coverage, "maps", (), "workspaces", (), "coveragestores", (), "coverages", ())

# Files:
urlmap(files, "maps", (), "workspaces", (), "(datastores|coveragestores)", (), "(file|url|external)")

# Styles:
urlmap(styles, "maps", (), "styles")
urlmap(style, "maps", (), "styles", ())

# Layers, layer styles and data fields:
urlmap(layers, "maps", (), "layers")
urlmap(layer, "maps", (), "layers", ())
urlmap(layerstyles, "maps", (), "layers", (), "styles")
urlmap(layerstyle, "maps", (), "layers", (), "styles", ())
urlmap(layerfields, "maps", (), "layers", (), "fields")

# Layergroups:
urlmap(layergroups, "maps", (), "layergroups")
urlmap(layergroup, "maps", (), "layergroups", ())

urls = tuple(urlmap)

if get_config("debug")["web_debug"]:
    web.config.debug = True
if get_config("logging")["web_logs"]:
    HTTPCompatible.return_logs = True

app = web.application(urls, globals())

if __name__ == "__main__":
    app.run()

application = app.wsgifunc()
