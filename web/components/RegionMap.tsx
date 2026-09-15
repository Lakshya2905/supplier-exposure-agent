'use client';
/**
 * Where the suppliers are. The one chart in this application that is not Carbon.
 *
 * WHY PLOTLY HERE AND CARBON EVERYWHERE ELSE. The map's geometry carries a
 * decision this repository has already made, written down and tested: India is
 * drawn INCLUDING its full claimed territory, from a boundary vendored under CC
 * BY 4.0, because Natural Earth's `IND` polygon follows a different convention
 * and stops around 35.5N. Carbon Charts' choropleth would need world geometry
 * supplied from somewhere, and re-sourcing that is how a decision like this gets
 * silently lost: nothing would fail, the map would simply draw a smaller India.
 * `tests/test_map_geometry.py` asserts the reach of the shape and can only see
 * the one copy, which the API serves.
 *
 * So this uses the same library the tested implementation uses, with the same
 * geometry and the same layer decisions, and everything else on every surface is
 * Carbon. Loaded on demand, so the other four routes do not carry it.
 *
 * COLOURS ARE CARBON TOKENS, read once at mount rather than hardcoded. The scale
 * must start ABOVE the land colour: if the least-exposed region and "not a region
 * at all" render alike, a count and a question the data does not answer look the
 * same. Blue against grey separates them by hue as well as by lightness, which
 * survives greyscale better than the blue-on-blue it replaces.
 */
import dynamic from 'next/dynamic';
import { useEffect, useMemo, useState } from 'react';
import { API_BASE } from '@/lib/api';
import type { ScoreResult } from '@/lib/types';

const Plot = dynamic(() => import('react-plotly.js'), {
  ssr: false,
  loading: () => (
    <div className="sea-chart__absent">
      <span>Drawing the map.</span>
    </div>
  ),
});

const INDIA = 'IND';

/** Carbon's own tokens, resolved from the live document. */
function token(name: string, fallback: string) {
  if (typeof window === 'undefined') return fallback;
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(name).trim();
  return value || fallback;
}

export function RegionMap({ result }: { result: ScoreResult }) {
  const [india, setIndia] = useState<object | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let live = true;
    fetch(`${API_BASE}/api/assets/india-claimed.geojson`)
      .then((response) => (response.ok ? response.json()
                                       : Promise.reject(response.status)))
      .then((shape) => { if (live) setIndia(shape); })
      // STATED, NOT SILENT. Without the vendored boundary the built-in shape
      // would draw a smaller India and nothing on screen would say so, which is
      // the one failure mode this asset exists to prevent.
      .catch(() => { if (live) setFailed(true); });
    return () => { live = false; };
  }, []);

  const colours = useMemo(() => ({
    scale: [
      [0, token('--cds-blue-30', '#a6c8ff')],
      [0.5, token('--cds-blue-50', '#4589ff')],
      [1, token('--cds-blue-70', '#0043ce')],
    ] as Array<[number, string]>,
    land: token('--cds-layer-accent-01', '#e0e0e0'),
    ocean: token('--cds-layer-01', '#ffffff'),
    coast: token('--cds-border-strong-01', '#8d8d8d'),
    border: token('--cds-border-subtle-01', '#c6c6c6'),
    ink: token('--cds-text-primary', '#161616'),
  }), []);

  const rows = result.overview.map_rows;
  const base = rows.filter((row) => row.country !== INDIA);
  const indiaRow = rows.find((row) => row.country === INDIA);

  const hover = (row: typeof rows[number]) =>
    `<b>${row.name}</b><br>region: ${row.region_label}`
    + `<br>suppliers: ${row.suppliers}<br>parts: ${row.parts}`
    + `<br>single-source parts: ${row.exposed_parts}<extra></extra>`;

  const data: Array<Record<string, unknown>> = [{
    type: 'choropleth',
    locationmode: 'ISO-3',
    locations: base.map((row) => row.country),
    z: base.map((row) => row.exposed_parts),
    text: base.map(hover),
    hovertemplate: '%{text}',
    coloraxis: 'coloraxis',
    marker: { line: { color: colours.coast, width: 0.4 } },
  }];

  // INDIA IS DRAWN LAST, SO IT SITS ON TOP. The claimed areas that the built-in
  // geometry assigns to its neighbours are covered rather than left showing a
  // border through them.
  if (india && indiaRow) {
    data.push({
      type: 'choropleth',
      geojson: india,
      featureidkey: 'id',
      locations: [INDIA],
      z: [indiaRow.exposed_parts],
      text: [hover(indiaRow)],
      hovertemplate: '%{text}',
      // The SHARED colour axis, so India takes the fill the scale gives every
      // other region rather than a second palette nobody declared.
      coloraxis: 'coloraxis',
      marker: { line: { color: colours.coast, width: 0.4 } },
    });
  }

  return (
    <div className="sea-chart">
      <div className="sea-chart__title">Where the suppliers are</div>
      <div className="sea-chart__unit">single-source parts per region</div>
      <p className="sea-section__note">
        This dataset has four regions and no coordinates. The countries are a
        drawing convention for those regions, not a claim that any supplier is
        in a particular country. Land with no fill is not a region here, which
        is a question the data does not answer rather than a count of zero.
      </p>
      {failed && (
        <p className="sea-section__note">
          The vendored India boundary did not load, so India is drawn from the
          chart library&rsquo;s own geometry, which stops short of the claimed
          territory. Said here rather than drawn silently.
        </p>
      )}
      <Plot
        data={data as never}
        layout={{
          height: 420,
          margin: { l: 8, r: 8, t: 8, b: 8 },
          paper_bgcolor: 'rgba(0,0,0,0)',
          plot_bgcolor: 'rgba(0,0,0,0)',
          font: { color: colours.ink, size: 12,
                  family: 'IBM Plex Sans, sans-serif' },
          showlegend: false,
          coloraxis: {
            colorscale: colours.scale,
            colorbar: { title: { text: 'single-source<br>parts' },
                        thickness: 10, len: 0.7,
                        tickfont: { size: 11 } },
          },
          geo: {
            // THE GEO SUBPLOT PAINTS A WHITE RECTANGLE BY DEFAULT, and neither
            // paper_bgcolor nor plot_bgcolor covers it.
            bgcolor: 'rgba(0,0,0,0)',
            showframe: false,
            // THE REST OF THE WORLD HAS TO BE ASKED FOR. `landcolor` without
            // `showland` draws nothing, and the Streamlit version shipped once
            // with nineteen filled countries floating in an empty rectangle: no
            // Africa, no South America, no Australia. A map missing four
            // continents is not a style, it is a map that says the world ends
            // at the edge of the dataset.
            showland: true, landcolor: colours.land,
            showocean: true, oceancolor: colours.ocean,
            showcoastlines: true, coastlinecolor: colours.coast,
            coastlinewidth: 0.4,
            showcountries: true, countrycolor: colours.border,
            countrywidth: 0.4,
            showlakes: false,
            projection: { type: 'natural earth' },
            lataxis: { range: [-58, 84] },
          },
        } as never}
        // scrollZoom off: a geo plot captures the wheel, so scrolling the page
        // over the map zooms the map and the page stays put.
        config={{ displayModeBar: false, scrollZoom: false,
                  responsive: true } as never}
        style={{ width: '100%' }}
      />
      <p className="sea-chart__unit" style={{ marginBottom: 0 }}>
        India is drawn including its full claimed territory, from a boundary
        published by Data&#123;Meet&#125; under CC BY 4.0 and simplified for this
        map. The chart library&rsquo;s built-in country shapes follow a different
        convention. See assets/README.md.
      </p>
    </div>
  );
}
