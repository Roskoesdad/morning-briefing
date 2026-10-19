async function updateWeather() {
  const c = document.getElementById('weather-forecast-list');
  if (!c) return;
  try {
    const u = 'https://api.open-meteo.com/v1/forecast?latitude=32.7448&longitude=-116.9989&daily=weathercode,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum&temperature_unit=fahrenheit&precipitation_unit=inch&timezone=America%2FLos_Angeles&forecast_days=14';
    const r = await fetch(u);
    const d = await r.json();
    let h = '';
    const codes = {
      0: '☀️ Clear',
      1: '🌤️ Mostly Clear',
      2: '⛅ Pt Cloudy',
      3: '☁️ Overcast',
      45: '🌫️ Fog',
      48: '🌫️ Fog',
      51: '🌦️ Light Drizzle',
      53: '🌦️ Drizzle',
      55: '🌧️ Heavy Drizzle',
      61: '🌧️ Light Rain',
      63: '🌧️ Rain',
      65: '🌧️ Heavy Rain',
      80: '🌦️ Showers',
      81: '🌧️ Heavy Showers',
      95: '⛈️ Storm'
    };
    for (let i = 0; i < d.daily.time.length; i++) {
      const dt = new Date(d.daily.time[i] + 'T12:00:00');
      const day = i === 0 ? 'Today' : dt.toLocaleDateString('en-US', { weekday: 'short' });
      const md = (dt.getMonth() + 1) + '/' + dt.getDate();
      const max = Math.round(d.daily.temperature_2m_max[i]);
      const min = Math.round(d.daily.temperature_2m_min[i]);
      const code = d.daily.weathercode[i];
      const prob = d.daily.precipitation_probability_max ? d.daily.precipitation_probability_max[i] : 0;
      const inch = d.daily.precipitation_sum ? d.daily.precipitation_sum[i] : 0;
      let desc = codes[code] || '🌤️ Fair';
      if (prob >= 35 || inch >= 0.02) {
        if (!desc.includes('Rain') && !desc.includes('Drizzle') && !desc.includes('Showers')) {
          desc = '🌦️ Rain (' + prob + '%)';
        } else {
          desc += ' (' + prob + '%)';
        }
      }
      h += '<div style="display:flex;justify-content:space-between;align-items:center;padding:14px 6px;border-bottom:1px solid #f1f5f9;font-size:14px;"><div><strong>' + day + '</strong> <span style="font-size:11px;color:#94a3b8;">' + md + '</span></div><span style="color:#64748b;font-size:13px;">' + desc + '</span><strong>' + max + '° <span style="font-weight:400;color:#94a3b8;font-size:12px;">/ ' + min + '°</span></strong></div>';
    }
    c.innerHTML = h;
  } catch (e) {
    c.innerHTML = '<div style="color:#94a3b8;">Weather syncing...</div>';
  }
}

async function updatePadres() {
  const b = document.getElementById('padres-live-box');
  if (!b) return;
  try {
    const u = 'https://statsapi.mlb.com/api/v1/schedule?' +
      'sportId=1&teamId=135&hydrate=linescore';
    const r = await fetch(u);
    const d = await r.json();
    if (!d.dates || !d.dates[0] || !d.dates[0].games[0]) {
      b.innerHTML = '⚾ <strong>Padres:</strong> Offseason / No game scheduled today.';
      return;
    }
    const g = d.dates[0].games[0];
    const s = g.status.abstractGameState;
    const a = g.teams.away.team.name;
    const h = g.teams.home.team.name;
    const as = g.teams.away.score || 0;
    const hs = g.teams.home.score || 0;
    if (s === 'Live') {
      b.innerHTML = '🔴 <span style="color:#dc2626;font-weight:700;">LIVE:</span> ' + a + ' ' + as + ' @ ' + h + ' ' + hs;
    } else if (s === 'Final') {
      b.innerHTML = '🏁 <strong>FINAL:</strong> ' + a + ' ' + as + ' - ' + h + ' ' + hs;
    } else {
      b.innerHTML = '⚾ <strong>Upcoming:</strong> ' + a + ' @ ' + h;
    }
  } catch (e) {
    b.innerHTML = 'Padres live feed standby.';
  }
}

updateWeather();
updatePadres();
setInterval(updatePadres, 30000);