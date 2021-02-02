import os
import requests
from urllib.parse import urlencode
from datetime import datetime
from bottle import abort
import config
import json
import zipfile
import io


class App():
    def __init__(self, *args, **kwargs):
        # set up output dir
        if not os.path.exists(config.APP_CONFIG["OUTPUT_DIR"]):
            os.makedirs(config.APP_CONFIG["OUTPUT_DIR"])

    def get_data(self, request):
        # check for params
        if request.query.get("source_id") is None:
            abort(400, "missing required parameter (source_id)")

        # pull out parameters from the request
        program = request.query.get("program") if request.query.get("program") else "*"
        datasource = request.query.get("datasource") if request.query.get("datasource") else "*"
        project = request.query.get("project") if request.query.get("project") else datasource
        if program == "*" and project == "*":
            abort(400, "missing required parameter (program or datasource)")
        source_id = request.query.get("source_id") if request.query.get("source_id") else "NONE"
        if "*" in source_id:
            abort(400, "Invalid source_id")
        output_format = request.query.get("format") if request.query.get("format") else config.APP_CONFIG["DEFAULT_FORMAT"]
        lat_max = float(request.query.get("lat_max")) if request.query.get("lat_max") else 90
        lat_min = float(request.query.get("lat_min")) if request.query.get("lat_min") else -90
        lon_max = float(request.query.get("lon_max")) if request.query.get("lon_max") else 180
        lon_min = float(request.query.get("lon_min")) if request.query.get("lon_min") else -180
        start_date = request.query.get("start_date") if request.query.get("start_date") else "*"
        end_date = request.query.get("end_date") if request.query.get("end_date") else datetime.datetime.now().replace(microsecond=0).isoformat()+'Z'
        depth_min = float(request.query.get("depth_min")) if request.query.get("depth_min") else "*"
        depth_max = float(request.query.get("depth_max")) if request.query.get("depth_max") else "*"

        # get filenames
        filename = self._build_filename(program if program !="*" else project, source_id, lat_min, lat_max, lon_min, lon_max, start_date, end_date, depth_min, depth_max)
        csv_filename = filename + ".csv"
        json_filename = filename + ".json"
        zip_filename = filename + ".zip"

        # get the metadata if it's not cached
        if not os.path.isfile(json_filename):
            url = self._build_metadata_url(program, project, source_id)
            self._download_file(url, json_filename)
        with open(json_filename, "r") as f:
            metadata = json.load(f)
            # convert variables to field names
            variables = self._fix_variables(metadata.get("variables"))
            # get project if not defined earlier
            if project == "*":
                project = metadata.get("datasource")

        # return data into the right format
        if "csv" in output_format:
            # download csv data
            if not os.path.isfile(csv_filename):
                url = self._build_data_url(project, source_id, lat_min, lat_max, lon_min, lon_max, start_date, end_date, depth_min, depth_max, variables)
                self._download_file(url, csv_filename)
            output_format = config.APP_CONFIG["AVAILABLE_FORMATS"]["csv"]
            with open(csv_filename, "r") as f:
                data = f.read()
            filename = csv_filename
        elif "json" in output_format:
            output_format = config.APP_CONFIG["AVAILABLE_FORMATS"]["json"]
            with open(json_filename, "r") as f:
                data = f.read()
            filename = json_filename
        elif "zip" in output_format:
            # download both
            if not os.path.isfile(csv_filename):
                url = self._build_data_url(project, source_id, lat_min, lat_max, lon_min, lon_max, start_date, end_date, depth_min, depth_max, variables)
                self._download_file(url, csv_filename)
            output_format = config.APP_CONFIG["AVAILABLE_FORMATS"]["zip"]
            data = self._zip_data(csv_filename, json_filename, project)
            # add project back to filename if not provided earlier
            filename = zip_filename.split("/")[1] if project in zip_filename else project + "_" + zip_filename.split("/")[1].split("_", 1)[1]

        # clear cached data
        if not config.APP_CONFIG["CACHE_FILES"] and os.path.isfile(csv_filename):
            os.remove(csv_filename)
        if not config.APP_CONFIG["CACHE_FILES"] and os.path.isfile(json_filename):
            os.remove(json_filename)

        return (output_format, filename, data)

    def _fix_variables(self, variables):
        output = []
        for variable in variables:
            var = variable.lower().replace(' ','_') + '_d'
            output.append(var)
        return output

    def _build_data_url(self, project, source_id, lat_min, lat_max, lon_min, lon_max, start_date, end_date, depth_min, depth_max, variables=["*_d"]):
        query = {
            "wt": "csv",
            "rows": "10000000",
            "sort": "measurement_date_time ASC",
            "fl": "measurement_date_time,lon,lat,depth,%s" % (",".join(variables)),
            "q": "datatype:data AND project:%s AND source_id: %s AND lat:[%s TO %s] AND lon:[%s TO %s] AND measurement_date_time:[%s TO %s] AND depth:[%s TO %s]" % (project, source_id, lat_min, lat_max, lon_min, lon_max, start_date, end_date, depth_min, depth_max)
        }
        return config.APP_CONFIG["SOLR_URL"] + "?" + urlencode(query)

    def _build_metadata_url(self, program, project, source_id):
        query = {
            "wt": "json",
            "q": "datatype:track AND program:%s* AND project:%s AND source_id: %s" % (program, project, source_id)
        }
        return config.APP_CONFIG["SOLR_URL"] + "?" + urlencode(query)

    def _build_filename(self, project, source_id, lat_min, lat_max, lon_min, lon_max, start_date, end_date, depth_min="*", depth_max="*"):
        if start_date == "*":
            start_date = ""
        else:
            start_date = start_date + "_"
        depth = ""
        if depth_min != "*":
            depth = depth + "__" + "{:.2f}".format(depth_min)
        if depth_max != "*":
            if depth_min == "*":
                depth = depth + "__0"
            depth = depth + "_" + "{:.2f}".format(depth_max)

        filename = "{}_{}{}__{:.2f}_{:.2f}_{:.2f}_{:.2f}__{}{}".format(project, source_id, depth, lon_min, lon_max, lat_min, lat_max, start_date.replace(":", "").replace("-", "").replace("T", "").replace("Z", ""), end_date.replace(":", "").replace("-", "").replace("T", "").replace("Z", ""))
        return str(config.APP_CONFIG["OUTPUT_DIR"]) + "/" + "".join([c for c in filename if c.isalpha() or c.isdigit() or c == ' ' or c == '_' or c == "-"]).rstrip()

    def _download_file(self, url, filename):
        r = requests.get(url)
        if ".json" in filename:
            # transform the json response
            try:
                doc = r.json().get("response").get("docs")[0]
            except Exception:
                abort(400, "Data not available")

            metadata = {
                    "variables": doc.get("variables"),
                    "variables_units": doc.get("variables_units"),
                    "description": doc.get("description"),
                    "instrument": doc.get("instrument"),
                    "datasource": doc.get("project"),
                    "program": doc.get("program"),
                    "platform": doc.get("platform"),
                    "mission": doc.get("mission"),
                    "source_id": doc.get("source_id"),
                    "title": doc.get("title")
            }
            with open(filename, "w") as f:
                f.write(json.dumps(metadata, indent=4, sort_keys=True))
        else:
            with open(filename, "wb") as f:
                f.write(r.content)

        return filename

    def _zip_data(self, csv_filename, json_filename, project):
        # zip up the data and metadata files for response
        data = io.BytesIO()
        with zipfile.ZipFile(data, mode="w") as z:
            z.write(csv_filename, csv_filename.split("/")[1] if project in csv_filename else project + "_" + csv_filename.split("/")[1].split("_", 1)[1], compress_type = zipfile.ZIP_DEFLATED)
            os.remove(csv_filename)
            z.write(json_filename, json_filename.split("/")[1] if project in json_filename else project + "_" + json_filename.split("/")[1].split("_", 1)[1], compress_type = zipfile.ZIP_DEFLATED)
            os.remove(json_filename)
        data.seek(0)
        return data
