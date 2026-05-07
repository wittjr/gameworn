// Shared league/team datalist helpers used by collectible_form and collectible_bulk_edit.
// Exposed as window.TeamsDatalist = { fillTopOptionOnTab, populateTeams }.
(function (global) {
  // Completes the input to the best matching datalist option when Tab is pressed.
  // listEl: the <datalist> element. Returns true if a match was applied.
  function fillTopOptionOnTab(e, inputEl, listEl) {
    if (e.key !== 'Tab') return false;
    if (!listEl) return false;
    const opts = Array.from(listEl.querySelectorAll('option'));
    if (!opts.length) return false;
    const q = (inputEl.value || '').trim().toLowerCase();
    if (!q) return false;
    let match = opts.find(o => (o.value || '').toLowerCase().startsWith(q));
    if (!match) match = opts.find(o => (o.value || '').toLowerCase().includes(q));
    if (match) { inputEl.value = match.value; return true; }
    return false;
  }

  // Fetches teams for leagueVal and populates listEl (<datalist>).
  // teamsUrl: the base URL for the get_teams endpoint (pass window.TEAMS_URL).
  function populateTeams(leagueVal, listEl, teamsUrl) {
    if (!listEl) return;
    listEl.innerHTML = '';
    if (!leagueVal) return;
    const url = new URL(teamsUrl, window.location.origin);
    url.searchParams.set('league', leagueVal);
    fetch(url)
      .then(r => r.json())
      .then(data => {
        (data.teams || []).forEach(name => {
          const opt = document.createElement('option');
          opt.value = name;
          listEl.appendChild(opt);
        });
      })
      .catch(() => {});
  }

  global.TeamsDatalist = { fillTopOptionOnTab, populateTeams };
})(window);
