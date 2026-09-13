#!/usr/bin/env python3
"""Regression checks for realistic search URL shapes."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    (
        "Amazon supports canonical /s?k= search",
        "sites/amazon/app.py",
        ["@app.route('/s')", "request.args.get('k')"],
    ),
    (
        "Amazon search UI emits k= on /s",
        "sites/amazon/templates/base.html",
        ['action="/s"', 'name="k"'],
    ),
    (
        "Booking supports canonical /searchresults.html?ss=",
        "sites/booking/app.py",
        ["@app.route('/searchresults.html')", "request.args.get('ss')"],
    ),
    (
        "Booking search UI emits ss=",
        "sites/booking/templates/index.html",
        ['action="/searchresults.html"', 'name="ss"'],
    ),
    (
        "Google Maps supports canonical /maps/search/<query>",
        "sites/google_map/app.py",
        ['@app.route("/maps/search/")', '@app.route("/maps/search/<path:maps_query>")'],
    ),
    (
        "Google Maps search UI emits path search",
        "sites/google_map/templates/_search_bar.html",
        ['action="/maps/search/"', 'data-path-search="maps"'],
    ),
    (
        "Google Maps path-search submit handler exists",
        "sites/google_map/static/js/main.js",
        ['form[data-path-search="maps"]', "'/maps/search/' + encodeURIComponent(query)"],
    ),
    (
        "ESPN supports canonical /search/_/q/<query>",
        "sites/espn/app.py",
        ["@app.route('/search/_/q/<path:espn_query>')"],
    ),
    (
        "ESPN search UI emits path search",
        "sites/espn/templates/search.html",
        ['action="/search/_/q/"', 'data-path-search="espn"'],
    ),
    (
        "ESPN path-search submit handler exists",
        "sites/espn/static/js/main.js",
        ['form[data-path-search="espn"]', "'/search/_/q/' + encodeURIComponent(query)"],
    ),
    (
        "Apple supports canonical /search/<query>",
        "sites/apple/app.py",
        ["@app.route('/search/<path:apple_query>')"],
    ),
    (
        "Apple search UI emits path search",
        "sites/apple/templates/search.html",
        ['action="/search/"', 'data-path-search="apple"'],
    ),
    (
        "Apple path-search submit handler exists",
        "sites/apple/static/js/main.js",
        ['form[data-path-search="apple"]', "'/search/' + encodeURIComponent(query)"],
    ),
    (
        "Coursera supports canonical query= search",
        "sites/coursera/app.py",
        ["request.args.get('query')"],
    ),
    (
        "Coursera search UI emits query=",
        "sites/coursera/templates/base.html",
        ['action="/search"', 'name="query"'],
    ),
    (
        "Hugging Face supports canonical full-text search",
        "sites/huggingface/app.py",
        ['@app.route("/search/full-text")'],
    ),
    (
        "Hugging Face search UI emits full-text path",
        "sites/huggingface/templates/base.html",
        ['action="/search/full-text"', 'name="q"'],
    ),
    (
        "Cambridge Dictionary supports direct search path",
        "sites/cambridge_dictionary/app.py",
        ["@app.route('/search/direct/')", "@app.route('/search/english/direct/')"],
    ),
    (
        "Cambridge Dictionary search UI emits direct path",
        "sites/cambridge_dictionary/templates/base.html",
        [
            'action="{{ \'/search/english-thesaurus/direct/\' if _is_thes else \'/search/direct/\' }}"',
            'name="datasetsearch"',
            "'english-thesaurus' if _is_thes else 'english'",
        ],
    ),
]

FORBIDDEN = [
    (
        "Amazon nav should not emit legacy q search",
        "sites/amazon/templates/base.html",
        ['action="{{ url_for(\'search\') }}"', 'name="q" placeholder="Search Amazon"'],
    ),
    (
        "Booking homepage should not emit legacy q search",
        "sites/booking/templates/index.html",
        ['action="{{ url_for(\'search\') }}"', 'name="q" placeholder="Where are you going?"'],
    ),
    (
        "Coursera nav should not emit legacy q search",
        "sites/coursera/templates/base.html",
        ['name="q" placeholder="What do you want to learn?"'],
    ),
]


def main():
    failed = False
    for label, rel, needles in REQUIRED:
        text = (ROOT / rel).read_text()
        for needle in needles:
            if needle not in text:
                print(f"{label}: missing {needle!r} in {rel}")
                failed = True

    for label, rel, needles in FORBIDDEN:
        text = (ROOT / rel).read_text()
        for needle in needles:
            if needle in text:
                print(f"{label}: forbidden {needle!r} in {rel}")
                failed = True

    if failed:
        raise SystemExit(1)
    print("Search URL realism checks passed")


if __name__ == "__main__":
    main()
