"""Unit tests for AnimeClick episode-title enrichment (no network)."""
from app.services.animeclick_service import (
    build_title_map,
    detect_offset,
    parse_episodes,
    strip_season_suffix,
)

# Minimal AnimeClick /episodi fragment: continuous numbering + a special (12.5).
_HTML = """
<tr><td class="col-md-2">Ep.&nbsp;01</td>
<td><a href="/episodio/1/come-una-spada">Come una spada solitaria</a></td></tr>
<tr><td class="col-md-2">Ep.&nbsp;03</td>
<td><a href="/episodio/3/order">Order &amp; Watcher</a></td></tr>
<tr><td class="col-md-2">Ep.&nbsp;12.5</td>
<td><a href="/episodio/125/speciale">Episodio speciale riepilogativo</a></td></tr>
<tr><td class="col-md-2">Ep.&nbsp;13</td>
<td><a href="/episodio/13/barriera">Il giorno della barriera</a></td></tr>
<tr><td class="col-md-2">Ep.&nbsp;18</td>
<td><a href="/episodio/18/fioritura">La prima fioritura</a></td></tr>
"""


def test_parse_episodes_handles_specials_and_entities():
    eps = parse_episodes(_HTML)
    assert ("01", "Come una spada solitaria") in eps
    assert ("12.5", "Episodio speciale riepilogativo") in eps
    assert ("03", "Order & Watcher") in eps  # HTML entity decoded


def test_strip_season_suffix():
    assert strip_season_suffix("Tsue to Tsurugi no Wistoria 2") == "Tsue to Tsurugi no Wistoria"
    assert strip_season_suffix("Wistoria: Wand and Sword Season 2") == "Wistoria: Wand and Sword"
    assert strip_season_suffix("Some Anime 2nd Season") == "Some Anime"
    # No trailing season -> unchanged
    assert strip_season_suffix("Mob Psycho 100") == "Mob Psycho"  # bare-number heuristic


def test_detect_offset_from_italian_anchor():
    ac = parse_episodes(_HTML)
    # Source (season 2) numbers restart at 1; ep1 already has the IT title.
    source = [(1, "Il giorno della barriera"), (6, "1080p CR")]
    assert detect_offset(source, ac) == 12  # ac ep13 - source ep1


def test_detect_offset_ignores_junk_only():
    ac = parse_episodes(_HTML)
    source = [(1, "1080p CR"), (2, "720p WEB-DL")]
    assert detect_offset(source, ac) is None


def test_build_title_map_fills_missing_title_for_sequel():
    ac = parse_episodes(_HTML)
    source = [(1, "Il giorno della barriera"), (6, "1080p CR")]
    mapping = build_title_map(source, ac, is_sequel=True)
    assert mapping[6] == "La prima fioritura"  # ep6 -> ac ep18 via offset 12


def test_build_title_map_season_one_direct():
    ac = parse_episodes(_HTML)
    source = [(1, "1080p CR"), (3, "junk")]
    mapping = build_title_map(source, ac, is_sequel=False)
    # offset defaults to 0 for a single cour -> direct numbering
    assert mapping[1] == "Come una spada solitaria"
    assert mapping[3] == "Order & Watcher"


def test_build_title_map_sequel_without_anchor_is_empty():
    ac = parse_episodes(_HTML)
    source = [(1, "1080p CR"), (6, "720p")]
    assert build_title_map(source, ac, is_sequel=True) == {}
