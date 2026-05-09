import { useMemo } from 'react';

const LOCATION_COORDS: Record<string, { top: string; left: string }> = {
  // Countries
  'united states': { top: '40%', left: '28%' },
  usa:             { top: '40%', left: '28%' },
  america:         { top: '40%', left: '28%' },
  india:           { top: '58%', left: '76%' },
  canada:          { top: '25%', left: '28%' },
  uk:              { top: '23%', left: '45%' },
  england:         { top: '23%', left: '45%' },
  germany:         { top: '24%', left: '50%' },
  australia:       { top: '74%', left: '90%' },
  brazil:          { top: '62%', left: '55%' },
  mexico:          { top: '50%', left: '24%' },
  france:          { top: '27%', left: '48%' },
  italy:           { top: '30%', left: '53%' },
  spain:           { top: '33%', left: '44%' },
  nigeria:         { top: '45%', left: '58%' },
  china:           { top: '45%', left: '85%' },
  japan:           { top: '33%', left: '93%' },

  // US states (common demo locations)
  california:      { top: '52%', left: '18%' },
  texas:           { top: '60%', left: '35%' },
  'new york':      { top: '38%', left: '40%' },
  florida:         { top: '65%', left: '42%' },
  illinois:        { top: '49%', left: '38%' },
  washington:      { top: '28%', left: '16%' },
  arizona:         { top: '60%', left: '21%' },
  nevada:          { top: '55%', left: '20%' },
  georgia:         { top: '63%', left: '42%' },
  ohio:            { top: '47%', left: '43%' },

  // India regions
  kerala:          { top: '68%', left: '78%' },
  mumbai:          { top: '61%', left: '75%' },
  delhi:           { top: '54%', left: '77%' },
  bangalore:       { top: '67%', left: '78%' },
  kolkata:         { top: '60%', left: '82%' },
};

const LOCATION_ALIAS: Record<string, string> = {
  us: 'united states',
  'u.s.': 'united states',
  'u.s.a.': 'united states',
  'united states of america': 'united states',
  america: 'united states',
  uk: 'uk',
  'u.k.': 'uk',
  britain: 'uk',
  england: 'uk',
  china: 'china',
  prc: 'china',
};

function normalizeLocation(raw: string) {
  const cleaned = raw
    .toLowerCase()
    .replace(/\./g, '')
    .replace(/\s+\(.*\)/, '')
    .replace(/[^a-z0-9 ]+/g, ' ')
    .trim();

  if (!cleaned) return '';
  if (LOCATION_ALIAS[cleaned]) {
    return LOCATION_ALIAS[cleaned];
  }
  return cleaned;
}

function LocationMap({ genomes }: { genomes: any[] }) {
  const { pins, topLocations, unknownLocations } = useMemo(() => {
    const counts: Record<string, number> = {};
    const rawLocations: string[] = [];

    for (const genome of genomes) {
      const extracted = genome.entities?.locations || [];
      const proxy = genome.geo?.subreddit_geo_proxy;
      const all = [...extracted];
      if (proxy) all.push(proxy);

      for (const raw of all) {
        const location = normalizeLocation(raw);
        if (!location) continue;
        rawLocations.push(location);
        counts[location] = (counts[location] || 0) + 1;
      }
    }

    const pins = Object.entries(counts)
      .map(([location, count]) => ({ location, count, coord: LOCATION_COORDS[location] }))
      .filter(pin => pin.coord)
      .sort((a, b) => b.count - a.count);

    const unknownLocations = Object.keys(counts)
      .filter(location => !LOCATION_COORDS[location])
      .sort();

    const topLocations = Object.entries(counts)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([location, count]) => ({ location, count, mapped: !!LOCATION_COORDS[location] }));

    return { pins, topLocations, unknownLocations };
  }, [genomes]);

  const total = topLocations.reduce((sum, item) => sum + item.count, 0);
  const hasData = pins.length > 0 || topLocations.length > 0;

  if (!hasData) {
    return (
      <div className="panel" style={{ marginTop: 18 }}>
        <div className="panel-hdr">
          <div>
            <div className="panel-kicker">Geospatial</div>
            <div className="panel-title">Signal location tracker</div>
          </div>
        </div>
        <div className="empty-state">
          No geographic signal has been extracted yet.
        </div>
      </div>
    );
  }

  return (
    <div className="panel" style={{ marginTop: 18 }}>
      <div className="panel-hdr">
        <div>
          <div className="panel-kicker">Geospatial</div>
          <div className="panel-title">Signal location tracker</div>
        </div>
      </div>

      <div className="geo-board">
        {pins.map(pin => (
          <div
            key={pin.location}
            className="geo-pin warn-pin"
            style={{ top: pin.coord.top, left: pin.coord.left }}>
            <strong>{pin.count}</strong>
            <span>{pin.location}</span>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginTop: 12 }}>
        <div>
          <div className="panel-kicker" style={{ marginBottom: 8 }}>Top mapped regions</div>
          <div className="detail-row" style={{ flexDirection: 'column', gap: 6 }}>
            {topLocations.map(item => (
              <div key={item.location} style={{ display: 'flex', justifyContent: 'space-between', gap: 12 }}>
                <span>{item.location}</span>
                <span style={{ color: item.mapped ? 'var(--success)' : 'var(--faint)' }}>
                  {item.count} signal{item.count > 1 ? 's' : ''}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div>
          <div className="panel-kicker" style={{ marginBottom: 8 }}>Unmapped locations</div>
          {unknownLocations.length > 0 ? (
            <div style={{ display: 'grid', gap: 6 }}>
              {unknownLocations.map(loc => (
                <span key={loc} className="entity-chip location" style={{ cursor: 'default' }}>{loc}</span>
              ))}
            </div>
          ) : (
            <div className="empty-state" style={{ margin: 0, padding: 10 }}>
              All extracted locations are mapped to known states/countries.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default LocationMap;
