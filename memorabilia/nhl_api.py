"""
NHL API client for fetching team schedules.
Used locally during population report import to get per-game data.
"""

import json
import urllib.request

# Map from MeiGray tag team name (lowercase) to NHL API team abbreviation.
# Includes historical/relocated teams that appear in older population reports.
TEAM_CODE_MAP = {
    # Current teams
    'anaheim ducks': 'ANA',
    'arizona coyotes': 'ARI',
    'boston bruins': 'BOS',
    'buffalo sabres': 'BUF',
    'calgary flames': 'CGY',
    'carolina hurricanes': 'CAR',
    'chicago blackhawks': 'CHI',
    'colorado avalanche': 'COL',
    'columbus blue jackets': 'CBJ',
    'dallas stars': 'DAL',
    'detroit red wings': 'DET',
    'edmonton oilers': 'EDM',
    'florida panthers': 'FLA',
    'los angeles kings': 'LAK',
    'minnesota wild': 'MIN',
    'montreal canadiens': 'MTL',
    'nashville predators': 'NSH',
    'new jersey devils': 'NJD',
    'new york islanders': 'NYI',
    'new york rangers': 'NYR',
    'ottawa senators': 'OTT',
    'philadelphia flyers': 'PHI',
    'pittsburgh penguins': 'PIT',
    'san jose sharks': 'SJS',
    'seattle kraken': 'SEA',
    'st. louis blues': 'STL',
    'tampa bay lightning': 'TBL',
    'toronto maple leafs': 'TOR',
    'utah hockey club': 'UTA',
    'vancouver canucks': 'VAN',
    'vegas golden knights': 'VGK',
    'washington capitals': 'WSH',
    'winnipeg jets': 'WPG',
    # Historical / relocated
    'mighty ducks of anaheim': 'ANA',
    'atlanta thrashers': 'ATL',
    'phoenix coyotes': 'PHX',
    'minnesota north stars': 'MNS',
    'hartford whalers': 'HFD',
    'quebec nordiques': 'QUE',
    'atlanta flames': 'AFM',
    # Name variants seen in MeiGray files
    'new york islanders ': 'NYI',
    'new york rangers ': 'NYR',
}


def _season_api_code(season):
    """Convert '2002-03' or '2024-25' to '20022003' or '20242025'."""
    parts = season.split('-')
    year1 = int(parts[0])
    suffix = parts[1]
    year2 = year1 + 1 if len(suffix) == 2 else int(suffix)
    return f'{year1}{year2:04d}'


def fetch_team_schedule(team_code, season):
    """
    Fetch all games for a team in a season from the NHL API.
    Returns list of dicts: {date, opponent, home_away ('H'|'A'), game_type (1|2|3)}.
    Returns [] on any error (network failure, team not found, etc.).
    """
    season_code = _season_api_code(season)
    url = f'https://api-web.nhle.com/v1/club-schedule-season/{team_code}/{season_code}'
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except Exception:
        return []

    games = []
    for game in data.get('games', []):
        home = game.get('homeTeam', {})
        away = game.get('awayTeam', {})
        is_home = home.get('abbrev', '').upper() == team_code.upper()
        opp = away if is_home else home
        opponent_name = (
            opp.get('placeName', {}).get('default', '')
            + ' '
            + opp.get('commonName', {}).get('default', '')
        ).strip()
        games.append({
            'date': game.get('gameDate', ''),
            'opponent': opponent_name,
            'home_away': 'H' if is_home else 'A',
            'game_type': game.get('gameType', 2),
        })
    return sorted(games, key=lambda g: g['date'])
