#!/usr/bin/env python3
"""Mirror the I-ADOPT variable nanopublications from the nanopub network into this repository.

For every current (not retracted or superseded) nanopublication of type iop:Variable, the
script keeps two files in OUT_DIR, both named after the nanopublication's artifact code:

  <code>.ttl   the assertion graph as plain Turtle, which the catalogue builds its pages from
  <code>.trig  the complete signed nanopublication, as published

A nanopublication never changes, so a file that exists is never fetched again; only new
nanopublications are downloaded, and the files of those that have been retracted or superseded
are removed.

Requires rdflib (pip install rdflib).
"""

import csv
import io
import re
import sys
import time
import urllib.request
from pathlib import Path

from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import Namespace

# All current nanopublications of type iop:Variable (columns np, label, pubkey, date).
# The router redirects to a query instance that is currently up.
LIST_URL = (
    "https://router.knowledgepixels.com/query/api/"
    "RAE35dYJQlpnqim7VeKuu07E9I1LQUZpkdYQR4RvU3KMU/get-nanopubs-by-type.csv"
    "?type=https%3A%2F%2Fw3id.org%2Fiadopt%2Font%2FVariable"
)
# A single nanopublication as TriG, from a registry that is currently up.
NANOPUB_URL = "https://router.knowledgepixels.com/registry/np/{code}.trig"

OUT_DIR = Path(__file__).resolve().parent.parent / "Nanopublications"

# Refuse to delete files when the list has shrunk by more than this fraction since the last run:
# a query instance that is still loading can answer with an incomplete list.
MAX_SHRINK = 0.2

NP = Namespace("http://www.nanopub.org/nschema#")
IOP = Namespace("https://w3id.org/iadopt/ont/")
COMPONENT_PREDICATES = [IOP.hasProperty, IOP.hasObjectOfInterest, IOP.hasMatrix,
                        IOP.hasContextObject, IOP.hasStatisticalModifier, IOP.hasConstraint,
                        IOP.constrains]

# Prefixes for the Turtle files, as the hand-written I-ADOPT files use them; many nanopubs
# declare none for these namespaces.
PREFIXES = {
    "iop": "https://w3id.org/iadopt/ont/",
    "iopp": "https://w3id.org/iadopt/pattern/",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "dcterms": "http://purl.org/dc/terms/",
    "owl": "http://www.w3.org/2002/07/owl#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "prov": "http://www.w3.org/ns/prov#",
    "sosa": "http://www.w3.org/ns/sosa/",
}
USER_AGENT = "iadopt-catalogue-export"


def fetch(url, accept, attempts=4):
    request = urllib.request.Request(url, headers={"Accept": accept, "User-Agent": USER_AGENT})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read().decode("utf-8")
        except Exception as e:
            if attempt == attempts:
                raise
            print(f"  retry {attempt} for {url}: {e}", file=sys.stderr)
            time.sleep(5 * attempt)


def list_nanopubs():
    rows = list(csv.DictReader(io.StringIO(fetch(LIST_URL, "text/csv"))))
    codes = {}
    for row in rows:
        uri = row["np"].strip()
        code = uri.rstrip("/").rsplit("/", 1)[-1]
        if code.startswith("RA") and len(code) == 45:
            codes[code] = uri
    return codes


def text_components(ttl):
    """Return the components given as plain text where I-ADOPT expects an entity.

    The catalogue turns every component into a link, and a link made from a text value points
    to a page that does not exist, which fails the whole build.
    """
    graph = Graph().parse(data=ttl, format="turtle")
    return [f"{p.split('/')[-1]} \"{o}\"" for p in COMPONENT_PREDICATES
            for o in graph.objects(None, p) if isinstance(o, Literal)]


def assertion_turtle(trig):
    ds = Dataset()
    ds.parse(data=trig, format="trig")
    assertion = None
    for graph in ds.graphs():
        for _, _, a in graph.triples((None, NP.hasAssertion, None)):
            assertion = a
    if not isinstance(assertion, URIRef):
        raise ValueError("no assertion graph found")
    out = Graph()
    for prefix, namespace in PREFIXES.items():
        out.bind(prefix, namespace, override=True, replace=True)
    for prefix, namespace in ds.namespaces():
        # skip the names rdflib makes up (ns1, ns2, ...) and the nanopub's own prefixes
        if re.fullmatch(r"ns\d+", prefix) or prefix in ("", "this", "np", "npx", "nt"):
            continue
        out.bind(prefix, namespace, override=False)
    for triple in ds.graph(assertion):
        out.add(triple)
    if len(out) == 0:
        raise ValueError("assertion graph is empty")
    return out.serialize(format="turtle")


def main():
    OUT_DIR.mkdir(exist_ok=True)
    current = list_nanopubs()
    if not current:
        sys.exit("The query returned no nanopublications; leaving the files as they are.")

    existing = {p.stem for p in OUT_DIR.glob("*.ttl")} | {p.stem for p in OUT_DIR.glob("*.trig")}
    gone = existing - set(current)
    if existing and len(gone) > MAX_SHRINK * len(existing):
        sys.exit(f"The list would remove {len(gone)} of {len(existing)} variables; "
                 "this looks like an incomplete answer, so nothing is changed.")

    added, skipped, failed = 0, 0, 0
    for code in sorted(current):
        ttl_file, trig_file = OUT_DIR / f"{code}.ttl", OUT_DIR / f"{code}.trig"
        if ttl_file.exists() and trig_file.exists():
            continue
        try:
            # a .ttl file that is missing is made again from the saved nanopub
            if trig_file.exists():
                trig = trig_file.read_text(encoding="utf-8")
            else:
                trig = fetch(NANOPUB_URL.format(code=code), "application/trig")
            ttl = assertion_turtle(trig)
        except Exception as e:
            print(f"  could not export {code}: {e}", file=sys.stderr)
            failed += 1
            continue
        trig_file.write_text(trig, encoding="utf-8")
        problems = text_components(ttl)
        if problems:
            # keep the nanopub, but leave it out of the catalogue
            print(f"  not in the catalogue: {code} ({', '.join(problems)})")
            skipped += 1
            continue
        ttl_file.write_text(ttl, encoding="utf-8")
        added += 1

    for code in sorted(gone):
        for suffix in (".ttl", ".trig"):
            (OUT_DIR / f"{code}{suffix}").unlink(missing_ok=True)

    print(f"{len(current)} current nanopublications: {added} written, {skipped} left out of the "
          f"catalogue, {len(gone)} removed, {failed} failed.")
    if failed:
        print("The failed ones are tried again on the next run.")


if __name__ == "__main__":
    main()
