import logging
import os
import urllib
from flask import Flask, render_template, request, jsonify, Response, session

from svviz import export
logging.getLogger('werkzeug').setLevel(logging.ERROR)

dataHub = None


# Initialize the Flask application
app = Flask(__name__,
    static_folder=os.path.join(os.path.dirname(__file__), "static"),
    template_folder=os.path.join(os.path.dirname(__file__), "templates")
    )
app.secret_key = '\xfd{H\xe5<\x95\xf9\xe3\x96.5\xd1\x01O<!\xd5\xa2\xa0\x9fR"\xa1\xa8'


def getport():
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


@app.route('/')
def index():
    if not "last_format" in session:
        session["last_format"] = "svg"

    try:
        variantDescription = str(dataHub.variant).replace("::", " ").replace("-", "&ndash;")
        return render_template('index.html',
            samples=dataHub.samples.keys(), 
            results_table=dataHub.getCounts(),
            insertSizeDistributions=[sample.name for sample in dataHub if sample.insertSizePlot], 
            variantDescription=variantDescription)
    except Exception as e:
        logging.error("ERROR:{}".format(e))
        raise

@app.route('/<path:path>')
def static_proxy(path):
    # send_static_file will guess the correct MIME type
    return app.send_static_file(path)
   
@app.route('/_export', methods=["POST"])
def do_export():
    format = request.form.get("format", "svg").lower()
    session["last_format"] = format

    filename = "export.{}".format(format)

    svg = dataHub.trackCompositor.render()

    if format == "svg":
        mimetype = "image/svg+xml"
        data = svg
    elif format == "png":
        mimetype = "image/png"
        data = export.convertSVG(svg, "png")
    elif format == "pdf":
        mimetype = "application/pdf"
        data = export.convertSVG(svg, "pdf")
    else:
        raise Exception("unknown format")

    response = Response(data,
                        mimetype=mimetype,
                        headers={"Content-Disposition": "attachment;filename={}".format(filename)})

    return response

   
@app.route('/_haspdfexport')
def _hasPDFExport():
    if export.canConvertSVGToPDF():
        return jsonify({"haspdfexport":True})
    return jsonify({"haspdfexport":False})

def _getsvg(track):
    track.render()
    svgText = track.svg.asString("web")
    return svgText

@app.route('/_disp')
def display():
    req = request.args.get('req', 0)

    if req == "progress":
        return jsonify(result="done")

    if req in ["alt", "ref", "amb"]:
        results = []
        for name, sample in dataHub.samples.iteritems():
            # svg = open("{}.{}.svg".format(req, name)).read()
            track = sample.tracks[req]
            svg = _getsvg(track)
            results.append({"name":name, "svg":svg})

        allele = req
        if allele == "amb": allele = "ref"
        axisSVG = _getsvg(dataHub.alleleTracks[allele]["axis"])
        # axisSVG = _getsvg(track.getAxis())
        results.append({"name":"axis", "svg":axisSVG})
        return jsonify(results=results)


    if req == "counts":
        return jsonify(result=dataHub.getCounts())

    return jsonify(result="unknown request: {}".format(req))


@app.route('/_info')
def info():
    import alignment
    readid = urllib.unquote(request.args.get('readid', 0))

    alnSet = dataHub.getAlignmentSetByName(readid)
    if alnSet:
        reads = alnSet.getAlignments()
        result = []
        for read in reads:
            html = "{}<br/>".format(alignment.getBlastRepresentation(read).replace("\n", "<br/>"))
            html = html.replace(" ", ".")
            result.append(html)

        result.append("<br/>Total length={}".format(len(alnSet)))
        result.append(" &nbsp; Reason={}".format(alnSet.parentCollection.why))
        # result.append(" &nbsp; Log odds={:.3g}".format(float(READ_INFO[readid].prob)))
        result = "".join(result)
        result = "<div style='font-family:Courier;'>" + result + "</div>"
        result = jsonify(result=result)
        return result
    else:
        logging.debug("NOT FOUND:{}".format(readid))

@app.route('/_isizes/<name>')
def displayIsizes(name):
    if not dataHub.samples[name].insertSizePlot:
        return None

    return Response(dataHub.samples[name].insertSizePlot, mimetype="image/svg+xml")

# def load():
#     import remap
#     global RESULTS, READ_INFO

#     results, refalns, altalns, ambalns = remap.main()
#     RESULTS.update(results)

#     READ_INFO = {}

#     for readset in refalns + altalns + ambalns:
#         READ_INFO[readset.getAlignments()[0].name] = readset

#     # RESULTS = {"AltCount":523345, "RefCount":23522, "AmbCount":9999}



def run():
    import webbrowser, threading
    port = getport()

    # load()
    url = "http://127.0.0.1:{}/".format(port)
    logging.info("Starting browser at {}".format(url))
    # webbrowser.open_new(url)

    threading.Timer(1.25, lambda: webbrowser.open(url) ).start()

    app.run(
        port=port#,
        # debug=True
    )

if __name__ == '__main__':
    pass