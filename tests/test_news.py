"""Tests for top-stories ranking (no network)."""

import datetime as dt

from services.news import Article, _best_image, _tokens, rank_stories

NOW = dt.datetime(2026, 11, 18, 12, tzinfo=dt.timezone.utc)


def art(outlet, title, rank=0, days_ago=1.0, img="https://img.example/x.jpg"):
    return Article(outlet=outlet, title=title, link=f"https://{outlet}/{rank}/{title[:8]}",
                   summary="", img=img, pub=NOW - dt.timedelta(days=days_ago), rank=rank,
                   tokens=_tokens(title))


def test_cross_outlet_story_ranks_first():
    arts = [
        art("NYT", "Local bakery wins regional award", rank=0),
        art("NYT", "Federal Reserve holds interest rates steady as inflation cools", rank=3),
        art("Guardian", "Fed holds interest rates steady while inflation cools", rank=5),
        art("BBC", "US Federal Reserve keeps interest rates steady, inflation cools", rank=6),
    ]
    top = rank_stories(arts, NOW)
    assert set(top[0].outlets) == {"NYT", "Guardian", "BBC"}
    assert len(top) == 2  # the three Fed articles collapse into one story


def test_old_and_imageless_stories_are_dropped():
    arts = [
        art("NYT", "Oil prices jump after OPEC surprise cut", days_ago=9),
        art("BBC", "Retail sales slump in October", img=None),
        art("Guardian", "Pound rallies after budget statement"),
    ]
    top = rank_stories(arts, NOW)
    assert [s.lead.title for s in top] == ["Pound rallies after budget statement"]


def test_at_most_eight():
    words = ["apple", "boeing", "copper", "dollar", "euro", "fed", "gold", "housing", "intel",
             "jobs", "kraft", "lithium", "mortgage", "nvidia", "opec", "pfizer", "quarter",
             "rupee", "steel", "tesla"]
    arts = [art("NYT", f"{w.title()} {w[::-1]} outlook", rank=i) for i, w in enumerate(words)]
    assert len(rank_stories(arts, NOW)) == 8


def test_bbc_thumbnail_upgraded_and_largest_image_chosen():
    class E:
        media_thumbnail = [{"url": "https://ichef.bbci.co.uk/ace/standard/240/cpsprodpb/abc.jpg", "width": "240"}]
    assert "/976/" in _best_image(E())

    class G:
        media_content = [{"url": "https://i.guim.co.uk/a.jpg?width=140", "width": "140"},
                         {"url": "https://i.guim.co.uk/a.jpg?width=460", "width": "460"}]
    assert _best_image(G()).endswith("width=460")
