"""
Looks up which curling games were in progress at a given time,
using Rock Creek's draw API.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

API_URL = "https://rockcreekcurling.com/api/draw/leagues-at"
DENVER = ZoneInfo("America/Denver")


def get_games_at(t):
    """
    Return a list of games in progress at time t (a datetime with a time zone).

    Each game is a dictionary like:
        {"league": "Monday Open", "sheet": "B",
         "team1": "...", "team2": "...",
         "start": datetime(...), "end": datetime(...)}
    """
    # Send the time in ISO 8601 format, e.g. 2026-10-26T19:00:00-06:00.
    # requests builds the ?t=... part of the URL and handles encoding.
    response = requests.get(API_URL, params={"t": t.isoformat()}, timeout=10)

    # Stop with a clear error if the server reports a problem (e.g. 400)
    response.raise_for_status()

    data = response.json()  # JSON text -> Python dictionaries and lists

    # The API nests games inside leagues, with start/end on the league.
    # Copy those times onto each game so every game is self-contained.
    games = []
    for league in data.get("leagues", []):
        start = datetime.fromisoformat(league["start"])
        end = datetime.fromisoformat(league["end"])

        for game in league.get("games", []):
            games.append({
                "league": league["league"],
                "sheet": game["sheet"],
                "team1": game["team1"],
                "team2": game["team2"],
                "start": start,
                "end": end,
            })

    return games


if __name__ == "__main__":
    t = datetime(2026, 10, 26, 19, 0, tzinfo=DENVER)
    for game in get_games_at(t):
        print(game["league"], "| sheet", game["sheet"], "|",
              game["team1"], "vs", game["team2"], "|",
              game["start"].strftime("%H:%M"), "-", game["end"].strftime("%H:%M"))