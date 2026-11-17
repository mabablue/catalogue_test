# catalogue_test

A catalogue of the I-ADOPT variables that are published as nanopublications, built with [iadopt-catalogue](https://github.com/sirkos/iadopt-catalogue) and served on GitHub Pages.

Every night, the workflow in `.github/workflows/gh-pages.yml` runs `scripts/export_nanopubs.py`, which mirrors the current (not retracted or superseded) nanopublications of type `https://w3id.org/iadopt/ont/Variable` into `Nanopublications/`, commits the changes, and rebuilds the site. For each nanopublication, named after its artifact code, the folder holds:

- `<code>.ttl`: the assertion graph as plain Turtle, which the catalogue pages are built from;
- `<code>.trig`: the complete signed nanopublication, as published.

The list comes from the query [`get-nanopubs-by-type`](https://router.knowledgepixels.com/query/api/RAE35dYJQlpnqim7VeKuu07E9I1LQUZpkdYQR4RvU3KMU/get-nanopubs-by-type.csv?type=https%3A%2F%2Fw3id.org%2Fiadopt%2Font%2FVariable). The workflow can also be started by hand under *Actions*.

To publish the site, set *Settings → Pages → Source* to *GitHub Actions*.
